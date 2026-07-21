from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "golden_dataset.json"
BLOOM_CHOICES = ["remember", "understand", "apply", "analyze", "evaluate", "create"]


def _load_env() -> None:
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / "backend" / ".env")
    load_dotenv(root / ".env")
    load_dotenv()


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in the environment or backend/.env")
    return create_client(supabase_url, supabase_key)


def load_random_chunks(supabase: Client, limit: int = 200) -> list[dict[str, Any]]:
    response = (
        supabase.table("chunks")
        .select("id,content,subject")
        .not_.is_("content", "null")
        .limit(limit)
        .execute()
    )
    data = response.data or []
    if not data:
        raise RuntimeError("No chunks were returned from Supabase. Check your Supabase schema and service role key.")
    return data


def _build_question_pair(chunk: dict[str, Any]) -> dict[str, str]:
    return {
        "question": "",
        "relevant_chunk": chunk.get("content", "") or "",
        "subject": chunk.get("subject", "General") or "General",
        "bloom_level": "understand",
    }


def save_golden_dataset(items: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} golden dataset items to {path}")


def run_interactive(output_path: Path = DEFAULT_OUTPUT) -> None:
    _load_env()
    supabase = get_supabase_client()
    chunks = load_random_chunks(supabase)
    collected: list[dict[str, str]] = []

    print("Loaded chunks from Supabase. Type 'done' at any prompt to finish.")
    print("You will be shown random chunks. Create a question that the chunk should answer.")

    while True:
        chunk = random.choice(chunks)
        content = chunk.get("content", "")
        subject = chunk.get("subject", "General") or "General"

        print("\n---")
        print(f"Subject: {subject}")
        print("Chunk preview:")
        print(content[:500].strip())
        print("---")

        question = input("Question for this chunk (or type 'done'): ").strip()
        if question.lower() == "done":
            break
        if not question:
            print("Please enter a non-empty question or 'done'.")
            continue

        bloom_level = input(
            f"Bloom level [{'/'.join(BLOOM_CHOICES)}] (default understand): "
        ).strip().lower()
        if bloom_level == "done":
            break
        if bloom_level not in BLOOM_CHOICES:
            bloom_level = "understand"

        item = {
            "question": question,
            "relevant_chunk": content,
            "subject": subject,
            "bloom_level": bloom_level,
        }
        collected.append(item)
        print(f"Added item #{len(collected)}")

    if collected:
        save_golden_dataset(collected, output_path)
    else:
        print("No items collected. Nothing was saved.")


if __name__ == "__main__":
    run_interactive()
