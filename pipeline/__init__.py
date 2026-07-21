"""
ShikhonAI PDF / Bangla NLP pipeline package.

Public entrypoints live in ``bangla_pipeline`` and ``ablation``.
"""

from .ablation import run_ablation_study
from .bangla_pipeline import (
    chunk_text,
    clean_bangla_text,
    embed_chunks,
    estimate_tokens,
    extract_digital,
    ingest_pdf,
    ocr_pdf,
    run_pipeline,
    store_chunks,
)

__all__ = [
    "chunk_text",
    "clean_bangla_text",
    "embed_chunks",
    "estimate_tokens",
    "extract_digital",
    "ingest_pdf",
    "ocr_pdf",
    "run_ablation_study",
    "run_pipeline",
    "store_chunks",
]
