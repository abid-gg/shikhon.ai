"""
Ablation study: naive fixed-token windows vs Bangla-aware ``chunk_text``.

Metrics (defense-friendly):
- **Recall@3**: fraction of golden questions for which the correct passage
  appears in any of the top-3 cosine-similarity chunks.
- **MRR** (Mean Reciprocal Rank): mean of ``1 / rank`` of the first retrieved
  chunk that matches the golden passage (0 if none in the ranked list).

Golden file format (JSON):
``[{"question": str, "correct_chunk_content": str}, ...]``
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import numpy as np

try:
    from .bangla_pipeline import (
        chunk_text,
        clean_bangla_text,
        embed_chunks,
        estimate_tokens,
        extract_digital,
    )
except ImportError:
    from bangla_pipeline import (
        chunk_text,
        clean_bangla_text,
        embed_chunks,
        estimate_tokens,
        extract_digital,
    )

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _golden_hit(chunk_text_content: str, golden: str) -> bool:
    """
    Relaxed match: normalized substring either way, or high token Jaccard.

    Golden passages in real PDFs rarely match OCR verbatim; substring + Jaccard
    catches paraphrase-level alignment for evaluation.
    """
    c = _normalize(chunk_text_content)
    g = _normalize(golden)
    if not g:
        return False
    if g in c or c in g:
        return True
    ct = set(re.findall(r"\S+", c))
    gt = set(re.findall(r"\S+", g))
    if not gt:
        return False
    inter = len(ct & gt)
    union = len(ct | gt)
    j = inter / union if union else 0.0
    return j >= 0.55


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb) + 1e-12)
    return float(np.dot(va, vb) / denom)


def naive_fixed_token_chunks(full_text: str, target_tokens: int = 500) -> list[str]:
    """
    Baseline: hard windows of ~``target_tokens`` estimated tokens.

    Ignores Bangla ``।``, overlap, and segment type — strictly character-sliced
    greedily by ``estimate_tokens`` budget (research negative control).
    """
    t = clean_bangla_text(full_text)
    n = len(t)
    out: list[str] = []
    lo = 0
    while lo < n:
        hi = lo
        while hi < n:
            if estimate_tokens(t[lo : hi + 1]) > target_tokens:
                break
            hi += 1
        if hi == lo:
            hi = lo + 1
        out.append(t[lo:hi])
        lo = hi
    return out


def _chunks_dicts_from_strings(
    parts: list[str],
    *,
    document_id: str,
    subject: str,
    page_number: int = 1,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        cid = str(uuid.uuid4())
        rows.append(
            {
                "id": cid,
                "document_id": document_id,
                "content": p,
                "subject": subject,
                "chapter": "",
                "page_number": page_number,
                "content_type": "prose",
                "token_estimate": estimate_tokens(p),
            }
        )
    return rows


def _embed_questions(
    questions: list[str], model: Any
) -> list[list[float]]:
    vecs = model.encode(
        questions,
        batch_size=16,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [v.tolist() for v in vecs]


def _evaluate_retrieval(
    questions: list[str],
    question_embs: list[list[float]],
    chunks: list[dict[str, Any]],
    goldens: list[str],
) -> tuple[float, float]:
    """
    Return (recall_at_3, mrr) for the given chunk corpus and gold alignments.
    """
    hits_r3 = 0
    rr_sum = 0.0
    for q_emb, golden in zip(question_embs, goldens, strict=True):
        scored: list[tuple[float, int]] = []
        for idx, ch in enumerate(chunks):
            sim = _cosine(q_emb, ch["embedding"])
            scored.append((sim, idx))
        scored.sort(key=lambda x: x[0], reverse=True)
        rank_hit: int | None = None
        for r, (_, idx) in enumerate(scored, start=1):
            if _golden_hit(chunks[idx]["content"], golden):
                rank_hit = r
                break
        if rank_hit is not None and rank_hit <= 3:
            hits_r3 += 1
        if rank_hit is not None:
            rr_sum += 1.0 / rank_hit
    n = len(questions)
    if n == 0:
        return 0.0, 0.0
    return hits_r3 / n, rr_sum / n


def run_ablation_study(pdf_path: str, golden_qa_path: str) -> None:
    """
    Load a PDF + golden JSON, compare naive vs smart chunking under identical
    embedding / retrieval settings, and print a LaTeX-friendly ASCII table.
    """
    with open(golden_qa_path, encoding="utf-8") as f:
        gold_rows: list[dict[str, str]] = json.load(f)
    questions = [r["question"] for r in gold_rows]
    goldens = [r["correct_chunk_content"] for r in gold_rows]

    pages = extract_digital(pdf_path)
    full_text = "\n\n".join(pages)
    pages_clean = [clean_bangla_text(p) for p in pages]

    doc_smart = "00000000-0000-4000-8000-000000000001"
    doc_naive = "00000000-0000-4000-8000-000000000002"
    subject = "ablation"

    smart_chunks = chunk_text(pages_clean, document_id=doc_smart, subject=subject)
    naive_parts = naive_fixed_token_chunks(full_text, target_tokens=500)
    naive_chunks = _chunks_dicts_from_strings(
        naive_parts, document_id=doc_naive, subject=subject
    )

    smart_chunks = embed_chunks(smart_chunks)
    model = getattr(embed_chunks, "_model")
    naive_chunks = embed_chunks(naive_chunks)
    q_embs = _embed_questions(questions, model)

    r3_smart, mrr_smart = _evaluate_retrieval(questions, q_embs, smart_chunks, goldens)
    r3_naive, mrr_naive = _evaluate_retrieval(questions, q_embs, naive_chunks, goldens)

    print()
    print("=" * 72)
    print("ShikhonAI — Chunking ablation (naive 500-token windows vs Bangla-aware)")
    print("=" * 72)
    print(f"{'Method':<28} {'Recall@3':>12} {'MRR':>12}")
    print("-" * 72)
    print(f"{'Naive (500 tok windows)':<28} {r3_naive:>12.4f} {mrr_naive:>12.4f}")
    print(f"{'Smart (Bangla pipeline)':<28} {r3_smart:>12.4f} {mrr_smart:>12.4f}")
    print("=" * 72)
    print(f"Golden pairs: {len(gold_rows)}  |  PDF: {pdf_path}")
    print()

    logger.info(
        "ablation complete: naive R@3=%.4f MRR=%.4f | smart R@3=%.4f MRR=%.4f",
        r3_naive,
        mrr_naive,
        r3_smart,
        mrr_smart,
    )
