from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


MODEL_NAME_MAP = {
    "paraphrase-multilingual-mpnet-base-v2": "multilingual-mpnet",
    "intfloat/multilingual-e5-large": "multilingual-e5-large",
    "l3cube-pune/bengali-sentence-bert-nli": "bengali-sentence-bert",
    "text-embedding-3-small": "openai-text-embedding-3-small",
}

OPENAI_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_ENDPOINT = "https://api.openai.com/v1/embeddings"


def load_golden_dataset(path: str) -> list[dict[str, str]]:
    path_obj = Path(path)
    if path_obj.exists():
        with path_obj.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        raise ValueError(f"Expected a list in {path}, got {type(data).__name__}")

    sample = [
        {
            "question": f"নমুনা প্রশ্ন {i} কী?",
            "relevant_chunk": f"এটি নমুনা চাঙ্কের বিষয়বস্তু {i}.",
            "subject": "General",
            "bloom_level": "understand",
        }
        for i in range(1, 11)
    ]
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("w", encoding="utf-8") as handle:
        json.dump(sample, handle, ensure_ascii=False, indent=2)
    print(f"Created sample golden dataset at {path_obj}")
    return sample


def load_corpus(path: str) -> list[str]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")
    with path_obj.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Corpus file must contain a JSON list of strings: {path}")
    return [str(item) for item in data]


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _openai_embed_texts(texts: list[str]) -> np.ndarray:
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {"model": OPENAI_MODEL, "input": texts}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = httpx.post(OPENAI_EMBEDDING_ENDPOINT, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    payload = response.json()
    embeddings = [item["embedding"] for item in payload["data"]]
    return np.asarray(embeddings, dtype=np.float32)


def embed_texts(texts: list[str], model_name: str) -> np.ndarray:
    if model_name == OPENAI_MODEL:
        return _openai_embed_texts(texts)

    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=False,
        show_progress_bar=True,
    )
    return np.asarray(embeddings, dtype=np.float32)


def embed_corpus(chunks: list[str], model_name: str) -> np.ndarray:
    if not chunks:
        return np.empty((0, 0), dtype=np.float32)
    return embed_texts(chunks, model_name)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(a, b) / denom)


def retrieve(query_embedding: np.ndarray, corpus_embeddings: np.ndarray, top_k: int = 3) -> list[int]:
    if corpus_embeddings.size == 0 or query_embedding.size == 0:
        return []
    query = query_embedding.reshape(-1)
    scores = corpus_embeddings @ query
    corpus_norms = np.linalg.norm(corpus_embeddings, axis=1)
    query_norm = np.linalg.norm(query)
    denom = corpus_norms * query_norm
    denom = np.where(denom <= 1e-12, 1e-12, denom)
    scores = scores / denom
    top_idxs = np.argsort(-scores)[:top_k]
    return top_idxs.tolist()


def _question_hit_and_rank(
    query_embedding: np.ndarray,
    corpus_chunks: list[str],
    corpus_embeddings: np.ndarray,
    relevant_chunk: str,
) -> tuple[bool, int | None]:
    retrieved_indices = retrieve(query_embedding, corpus_embeddings, top_k=3)
    relevant_norm = relevant_chunk.strip()
    for rank, idx in enumerate(retrieved_indices, start=1):
        candidate = corpus_chunks[idx].strip()
        if candidate == relevant_norm:
            return True, rank
        if cosine_similarity(query_embedding, corpus_embeddings[idx]) > 0.95:
            return True, rank
    return False, None


def evaluate_model(model_name: str, golden_dataset: list[dict[str, str]], corpus_chunks: list[str]) -> dict[str, Any]:
    print(f"Evaluating {model_name}...")
    model_display = MODEL_NAME_MAP.get(model_name, model_name)
    corpus_embeddings = embed_corpus(corpus_chunks, model_name)
    total_queries = len(golden_dataset)
    hits = 0
    hits_at_1 = 0
    reciprocal_ranks: list[float] = []
    total_latency_ms = 0.0

    if total_queries == 0:
        raise ValueError("Golden dataset is empty")

    for item in golden_dataset:
        question = item["question"]
        relevant_chunk = item["relevant_chunk"]
        start = time.perf_counter()
        query_embedding = embed_texts([question], model_name)[0]
        hit, rank = _question_hit_and_rank(query_embedding, corpus_chunks, corpus_embeddings, relevant_chunk)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        total_latency_ms += elapsed_ms

        if hit:
            hits += 1
            if rank == 1:
                hits_at_1 += 1
            reciprocal_ranks.append(1.0 / float(rank))
        else:
            reciprocal_ranks.append(0.0)

    recall_at_1 = hits_at_1 / total_queries
    recall_at_3 = hits / total_queries
    mrr = sum(reciprocal_ranks) / total_queries
    avg_latency_ms = total_latency_ms / total_queries

    return {
        "model": model_display,
        "recall@1": recall_at_1,
        "recall@3": recall_at_3,
        "mrr": mrr,
        "avg_latency_ms": avg_latency_ms,
    }


def print_results_table(results: list[dict[str, Any]]) -> None:
    headers = ["Model", "Recall@1", "Recall@3", "MRR", "Latency ms"]
    widths = [42, 10, 10, 10, 12]
    line = "┌" + "┬".join("─" * w for w in widths) + "┐"
    sep = "├" + "┼".join("─" * w for w in widths) + "┤"
    end = "└" + "┴".join("─" * w for w in widths) + "┘"
    print(line)
    print(
        "│"
        + f"{headers[0]:^{widths[0]}}"
        + "│"
        + f"{headers[1]:^{widths[1]}}"
        + "│"
        + f"{headers[2]:^{widths[2]}}"
        + "│"
        + f"{headers[3]:^{widths[3]}}"
        + "│"
        + f"{headers[4]:^{widths[4]}}"
        + "│"
    )
    print(sep)
    for row in results:
        print(
            "│"
            + f"{row['model'][:widths[0]]:^{widths[0]}}"
            + "│"
            + f"{row['recall@1']:.2f}".center(widths[1])
            + "│"
            + f"{row['recall@3']:.2f}".center(widths[2])
            + "│"
            + f"{row['mrr']:.2f}".center(widths[3])
            + "│"
            + f"{row['avg_latency_ms']:.1f}".center(widths[4])
            + "│"
        )
    print(end)

    best = max(results, key=lambda item: item["recall@3"])
    print(f"\nWinner: {best['model']} with Recall@3={best['recall@3']:.2f}")


def run_benchmark(golden_dataset_path: str, corpus_path: str) -> list[dict[str, Any]]:
    load_dotenv()
    golden_dataset = load_golden_dataset(golden_dataset_path)
    corpus_chunks = load_corpus(corpus_path)

    model_names = [
        "paraphrase-multilingual-mpnet-base-v2",
        "intfloat/multilingual-e5-large",
        "l3cube-pune/bengali-sentence-bert-nli",
    ]
    if _openai_api_key():
        model_names.append(OPENAI_MODEL)
    else:
        print("OPENAI_API_KEY not set; skipping OpenAI embedding benchmark.")

    results: list[dict[str, Any]] = []
    for model_name in model_names:
        try:
            result = evaluate_model(model_name, golden_dataset, corpus_chunks)
            results.append(result)
        except Exception as exc:
            print(f"Skipping {model_name} due to error: {exc}", file=sys.stderr)

    print_results_table(results)
    output_path = Path(__file__).resolve().parent / "benchmark_results.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    print(f"Saved benchmark results to {output_path}")
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run retrieval benchmark for Bangla educational chunk embeddings."
    )
    parser.add_argument(
        "--golden",
        default="golden_dataset.json",
        help="Path to the golden dataset JSON file.",
    )
    parser.add_argument(
        "--corpus",
        default="corpus_chunks.json",
        help="Path to the corpus JSON file containing chunk strings.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run_benchmark(args.golden, args.corpus)
    except Exception as exc:
        print(f"Benchmark failed: {exc}", file=sys.stderr)
        sys.exit(1)
