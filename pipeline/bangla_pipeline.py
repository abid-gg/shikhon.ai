"""
ShikhonAI — Bangla-specific PDF pre-processing pipeline.

This module implements a research-oriented ingestion path tuned for SSC/HSC
Bangla curriculum PDFs: scanned vs digital detection, OCR with Bangla+English,
Unicode-safe cleaning, script-aware segmentation, and Bangla sentence–first
chunking with controlled overlap for RAG.

Dependencies: PyMuPDF (fitz), pytesseract, Pillow, sentence-transformers,
supabase-py, numpy (for optional helpers / ablation imports).
"""

from __future__ import annotations

import io
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import logging
import re
import unicodedata
import uuid
from typing import Any, Iterable

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (Bangla / Indic typography & heuristics)
# ---------------------------------------------------------------------------

# Sentence boundary: Danda (U+0964) is widely used in Bangla print/PDFs.
DANDA = "\u0964"
# Double danda occasionally ends verses / blocks
DOUBLE_DANDA = "\u0965"
# Bengali virama (Hasanta) U+09CD — cluster repair in ``clean_bangla_text``
BENGALI_VIRAMA = "\u09cd"

# Formula / math symbols (count distinct categories for rule "2+")
FORMULA_SPECIAL_CHARS = frozenset("+=×÷^√∑∫*/()[]{}")
GREEK_RE = re.compile(r"[\u0370-\u03ff]")  # Greek and Coptic block

# Naive token bounds for smart prose chunker (Bangla-first)
TOKEN_TARGET_MIN = 400
TOKEN_TARGET_MAX = 600

# Scanned vs digital: average extracted chars per page threshold
SCANNED_AVG_CHAR_THRESHOLD = 50

# OCR confidence warning threshold (pytesseract 0–100)
OCR_CONFIDENCE_WARN = 60

# Rasterization DPI for OCR (print quality)
OCR_DPI = 300


# =============================================================================
# STEP 1 — PDF ingestion
# =============================================================================


def ingest_pdf(pdf_path: str) -> dict[str, Any]:
    """
    Classify PDF as scanned (image-heavy) vs digital (selectable text).

    Detection: PyMuPDF text extraction per page; if average UTF-8 text length
    across pages is below ``SCANNED_AVG_CHAR_THRESHOLD``, treat as scanned —
    typical for photocopied textbook pages where glyph outlines exist but
    no usable text layer is embedded.

    Returns:
        {"type": "scanned" | "digital", "page_count": int, "path": str}
    """
    doc = fitz.open(pdf_path)
    try:
        page_count = len(doc)
        if page_count == 0:
            logger.warning("PDF has zero pages: %s", pdf_path)
            return {"type": "digital", "page_count": 0, "path": pdf_path}

        total_chars = 0
        for page in doc:
            txt = page.get_text("text") or ""
            total_chars += len(txt.strip())

        avg = total_chars / page_count
        doc_type = "scanned" if avg < SCANNED_AVG_CHAR_THRESHOLD else "digital"
        logger.info(
            "ingest_pdf: %s → type=%s pages=%d avg_chars_per_page=%.1f",
            pdf_path,
            doc_type,
            page_count,
            avg,
        )
        return {"type": doc_type, "page_count": page_count, "path": pdf_path}
    finally:
        doc.close()


# =============================================================================
# STEP 2 — OCR for scanned PDFs
# =============================================================================


def ocr_pdf(pdf_path: str) -> list[str]:
    """
    Rasterize each page at 300 DPI and OCR with Bangla + English models.

    Uses ``lang='ben+eng'`` so Roman numerals, chemistry symbols, and English
    headings remain legible alongside Bangla body text.

    Warns (per page) when mean Tesseract confidence is below 60 — common when
    scan skew, bleed-through, or low DPI source images degrade recognition.
    """
    import pytesseract

    mat = fitz.Matrix(OCR_DPI / 72.0, OCR_DPI / 72.0)
    doc = fitz.open(pdf_path)
    pages_out: list[str] = []
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            data = pytesseract.image_to_data(
                img, lang="ben+eng", output_type=pytesseract.Output.DICT
            )
            confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit()]
            valid = [c for c in confs if c >= 0]
            if valid:
                mean_conf = float(np.mean(valid))
                if mean_conf < OCR_CONFIDENCE_WARN:
                    logger.warning(
                        "ocr_pdf: low mean OCR confidence on page %d: %.1f (< %d)",
                        i + 1,
                        mean_conf,
                        OCR_CONFIDENCE_WARN,
                    )

            text = pytesseract.image_to_string(img, lang="ben+eng") or ""
            pages_out.append(text)
            logger.debug("ocr_pdf: page %d chars=%d", i + 1, len(text))
    finally:
        doc.close()

    return pages_out


# =============================================================================
# STEP 3 — Digital text extraction
# =============================================================================


def extract_digital(pdf_path: str) -> list[str]:
    """
    Extract digital text page-by-page with reading order preserved.

    Uses PyMuPDF's structured ``get_text("text")`` which follows PDF content
    stream order — adequate for most curriculum PDFs; for two-column layouts,
    upstream layout analysis would be a future improvement.
    """
    doc = fitz.open(pdf_path)
    pages_out: list[str] = []
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            pages_out.append(text)
            logger.debug("extract_digital: page %d chars=%d", i + 1, len(text))
    finally:
        doc.close()
    return pages_out


# =============================================================================
# STEP 4 — Bangla-specific noise filter
# =============================================================================


def clean_bangla_text(text: str) -> str:
    """
    Reduce OCR/layout noise while preserving Bangla conjuncts and English runs.

    Steps:
    - Unicode NFC normalization (canonical composed clusters).
    - Remove stray pipe characters and obvious OCR junk in non-Latin runs.
    - Collapse repeated punctuation; trim decorative pipes.
    - Remove orphan *Hasanta* (virama) not followed by a Bengali consonant.
    - Preserve English / numeric / math-token runs (exam IDs, formulas).
    - Normalize whitespace: collapse spaces/tabs; keep single newlines as
      soft boundaries between lines/sentences where present.
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)

    # Preserve labeled English/numeric segments; clean "gaps" between them
    preserved = re.compile(
        r"[A-Za-z0-9\+\-\=\(\)\/\*\^]+(?:\s+[A-Za-z0-9\+\-\=\(\)\/\*\^]+)*"
    )

    def _clean_gap(gap: str) -> str:
        g = gap
        # Stray pipes (table OCR bleed) — remove isolated pipes, collapse runs
        g = re.sub(r"\|{3,}", " | | ", g)
        g = g.replace("|", " ")
        # Repeated punctuation (OCR shimmer)
        g = re.sub(r"([।.!?,\-:;])\1{2,}", r"\1", g)
        # Non-printable / replacement char
        g = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\uFFFD]", "", g)
        # Collapse horizontal whitespace (newlines handled outside)
        g = re.sub(r"[ \t\r\f\v]+", " ", g)
        return g

    parts: list[str] = []
    last = 0
    for m in preserved.finditer(text):
        parts.append(_clean_gap(text[last : m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(_clean_gap(text[last:]))
    merged = "".join(parts)

    # Orphan Hasanta (virama U+09CD): remove when not forming a consonant cluster
    # (single-pass fixed-width lookaround — avoids re.sub callback index drift).
    merged = re.sub(
        rf"(?<![\u0995-\u09b9\u09ce\u09dc\u09dd]){re.escape(BENGALI_VIRAMA)}(?![\u0995-\u09b9\u09ce\u09dc\u09dd])",
        "",
        merged,
    )

    # Newlines: collapse 3+ to double; collapse 2+ spaces around newlines
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    merged = re.sub(r"[ \t]*\n[ \t]*", "\n", merged)
    merged = re.sub(r" {2,}", " ", merged)
    return merged.strip()


# =============================================================================
# STEP 5 — Script / content type detector
# =============================================================================


def detect_segment_type(text: str) -> str:
    """
    Classify a text segment for downstream chunking policy.

    Priority: caption → formula → table → prose (default).

    - **caption**: short line + known figure/table prefixes (Bangla + English).
    - **formula**: multiple math operators / Greek / digit-operator-digit.
    - **table**: tabs, pipes, or column-like repeating whitespace.
    - **prose**: narrative body text.
    """
    t = text.strip()
    if not t:
        return "prose"

    # Caption heuristics (before length-heavy rules)
    if len(t) < 120:
        cap_prefixes = (
            "চিত্র",
            "ছক",
            "সারণি",
            "Figure",
            "Table",
        )
        if any(t.startswith(p) for p in cap_prefixes):
            return "caption"
        # Numbered caption: "১." / "2." style
        if re.match(r"^\s*[\d০-৯]+\.\s", t):
            return "caption"

    # Formula: count distinctive math symbols + Greek + simple arithmetic regex
    sym_score = sum(1 for c in t if c in FORMULA_SPECIAL_CHARS)
    sym_score += len(GREEK_RE.findall(t))
    if sym_score >= 2:
        return "formula"
    if re.search(r"\d+\s*[+\-×÷=]\s*\d+", t):
        return "formula"

    # Table: tabs, pipes, or 3+ columns of spaces (simplified grid heuristic)
    if t.count("\t") >= 3:
        return "table"
    if t.count("|") >= 3:
        return "table"
    # "Structured" whitespace: 3+ groups separated by 2+ spaces on a line
    lines = t.split("\n")
    for line in lines:
        chunks = re.split(r" {2,}", line.strip())
        if len([c for c in chunks if c]) >= 3 and len(line) > 20:
            return "table"

    return "prose"


# =============================================================================
# Token estimation (Bangla vs English / Latin)
# =============================================================================


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate for embedding / chunk budget.

    Rule of thumb (defense-friendly, fast):
    - Latin letters & digits: ~4 characters per token.
    - Everything else (Bangla abugida, punctuation, etc.): ~3 characters/token.
    """
    if not text:
        return 0
    total = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch.isdigit():
            j = i + 1
            while j < n:
                cj = text[j]
                if (
                    ("A" <= cj <= "Z")
                    or ("a" <= cj <= "z")
                    or cj.isdigit()
                    or cj in "+-*/=()^"
                ):
                    j += 1
                else:
                    break
            run = j - i
            total += max(1, (run + 3) // 4)
            i = j
        else:
            j = i + 1
            while j < n:
                cj = text[j]
                if ("A" <= cj <= "Z") or ("a" <= cj <= "z") or cj.isdigit():
                    break
                j += 1
            run = j - i
            total += max(1, (run + 2) // 3)
            i = j
    return total


# =============================================================================
# Heading / chapter detection (for chunk metadata)
# =============================================================================


_CHAPTER_NUM_RE = re.compile(
    r"(?:অধ্যায়|অধ্যায়|chapter)\s*[:：]?\s*([\d০-৯]+|[ivxlcdmIVXLCDM]+)",
    re.IGNORECASE,
)
_ALL_LATIN_CAPS_LINE = re.compile(r"^[A-Z0-9 \-]{4,}$")


def _maybe_heading_and_chapter(line: str) -> tuple[bool, str | None]:
    """
    Detect curriculum-style headings and return a human-readable chapter label.

    Heuristics:
    - Explicit ``অধ্যায় ৩`` / ``Chapter 2`` patterns.
    - Markdown bold markers ``**...**`` (some exports embed these).
    - ALL CAPS Latin line (international textbook sections).
    """
    s = line.strip()
    if not s:
        return False, None

    m = _CHAPTER_NUM_RE.search(s)
    if m:
        return True, s[:120]

    if s.startswith("**") and s.endswith("**") and len(s) > 4:
        return True, s.strip("*").strip()[:120]

    if _ALL_LATIN_CAPS_LINE.match(s) and len(s.split()) <= 12:
        return True, s[:120]

    # Numbered Bangla section: "৩.১" at line start (common in NCTB PDFs)
    if re.match(r"^\s*[\d০-৯]+\.[\d০-৯]*\s+\S", s):
        return True, s[:120]

    return False, None


def _split_prose_sentences(text: str) -> list[str]:
    """
    Split prose on Bangla danda / double danda; keep delimiters attached to LHS.

    Also splits on ASCII sentence ends when followed by space + capital/number,
    to handle English paragraphs inside Bangla books.
    """
    if not text.strip():
        return []

    # Normalize double danda to single boundary
    t = text.replace(DOUBLE_DANDA, DANDA + " ")
    parts = re.split(rf"(?<={re.escape(DANDA)})\s+", t)
    sentences: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Secondary split for English sentences
        sub = re.split(r"(?<=[.!?])\s+(?=[A-Z(0-9])", p)
        for s in sub:
            s = s.strip()
            if s:
                sentences.append(s)
    return sentences


def _merge_typed_blocks(page_text: str) -> list[tuple[str, str]]:
    """
    Split page into paragraphs, merge adjacent blocks of same non-prose type
    so tables/formulas stay physically contiguous in one chunk.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
    blocks: list[tuple[str, str]] = []
    for para in paragraphs:
        typ = detect_segment_type(para)
        if (
            blocks
            and typ == blocks[-1][0]
            and typ in ("table", "formula")
        ):
            prev_t, prev_s = blocks[-1]
            blocks[-1] = (prev_t, prev_s + "\n" + para)
        else:
            blocks.append((typ, para))
    return blocks


def _make_chunk_dict(
    *,
    document_id: str,
    subject: str,
    content: str,
    page_number: int,
    content_type: str,
    chapter: str,
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    body = clean_bangla_text(content)
    return {
        "id": cid,
        "document_id": document_id,
        "content": body,
        "subject": subject,
        "chapter": chapter or "",
        "page_number": page_number,
        "content_type": content_type,
        "token_estimate": estimate_tokens(body),
    }


def _exclusive_end_for_prose_window(sents: list[str], lo: int) -> int:
    """
    Return exclusive index ``hi`` such that ``sents[lo:hi]`` is the next prose chunk.

    Greedy growth under ``TOKEN_TARGET_MAX``, then optional extension toward
    ``TOKEN_TARGET_MIN`` while the next sentence still fits — never splits a
    sentence. A single sentence heavier than ``MAX`` is emitted alone.
    """
    n = len(sents)
    if lo >= n:
        return lo
    hi = lo
    while hi < n:
        nt = estimate_tokens(" ".join(sents[lo : hi + 1]))
        if nt > TOKEN_TARGET_MAX:
            break
        hi += 1
    if hi == lo:
        hi = lo + 1
    t = estimate_tokens(" ".join(sents[lo:hi]))
    while t < TOKEN_TARGET_MIN and hi < n:
        nt = estimate_tokens(" ".join(sents[lo : hi + 1]))
        if nt > TOKEN_TARGET_MAX:
            break
        hi += 1
        t = nt
    return hi


def _pack_prose_with_overlap(
    sents: list[str],
    *,
    document_id: str,
    subject: str,
    page_number: int,
    chapter: str,
) -> list[dict[str, Any]]:
    """
    Turn ordered prose sentences into overlapping chunks (research rule #5).

    Overlap policy: the last sentence of chunk *k* is repeated as the first
    sentence of chunk *k+1* **when** chunk *k* contained more than one sentence,
    so we never duplicate an entire one-sentence chunk ad infinitum.
    """
    out: list[dict[str, Any]] = []
    lo = 0
    while lo < len(sents):
        hi = _exclusive_end_for_prose_window(sents, lo)
        body = " ".join(sents[lo:hi]).strip()
        if body:
            out.append(
                _make_chunk_dict(
                    document_id=document_id,
                    subject=subject,
                    content=body,
                    page_number=page_number,
                    content_type="prose",
                    chapter=chapter,
                )
            )
        if hi >= len(sents):
            break
        if hi - lo > 1:
            lo = hi - 1
        else:
            lo = hi
    return out


def chunk_text(
    pages: list[str], document_id: str, subject: str
) -> list[dict[str, Any]]:
    """
    Smart Bangla-aware chunker (core contribution).

    Rules implemented:
    1. Primary split on Bangla ``।`` (Danda) via sentence tokenization.
    2. Target 400–600 *estimated* tokens per prose chunk.
    3. No mid-sentence cuts for prose.
    4. No mixing of different ``detect_segment_type`` labels in one chunk.
    5. One-sentence overlap between consecutive prose chunks on a page.
    6. Formula blocks: always one chunk (even if > max tokens).
    7. Table blocks: always one chunk.
    8. Rich metadata: ``chapter`` from nearby headings, ``page_number``, etc.

    ``pages`` should be ordered plain-text per page (already OCR'd or extracted);
    cleaning is applied idempotently inside emitted chunks.
    """
    out: list[dict[str, Any]] = []
    current_chapter = ""

    for page_idx, raw_page in enumerate(pages, start=1):
        page = clean_bangla_text(raw_page)
        if not page:
            continue

        lines = page.split("\n")
        # First pass: update chapter from heading lines; rebuild body without consuming headings as prose
        body_lines: list[str] = []
        for line in lines:
            is_h, chap = _maybe_heading_and_chapter(line)
            if is_h and chap:
                current_chapter = chap
                continue
            body_lines.append(line)

        page_body = "\n".join(body_lines).strip()
        if not page_body:
            continue

        blocks = _merge_typed_blocks(page_body)

        for typ, block in blocks:
            if typ in ("formula", "table", "caption"):
                out.append(
                    _make_chunk_dict(
                        document_id=document_id,
                        subject=subject,
                        content=block,
                        page_number=page_idx,
                        content_type=typ,
                        chapter=current_chapter,
                    )
                )
                continue

            # Prose: sentence-based packing with overlap
            sents = _split_prose_sentences(block)
            if not sents:
                continue
            out.extend(
                _pack_prose_with_overlap(
                    sents,
                    document_id=document_id,
                    subject=subject,
                    page_number=page_idx,
                    chapter=current_chapter,
                )
            )

    return out


# =============================================================================
# STEP 7 — Embedding generator
# =============================================================================


_EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Add ``embedding`` (768-d list[float]) to each chunk using multilingual MPNet.

    Batches encoder calls for throughput on CPU/GPU. Model is cached on the
    function object for repeated invocations within one worker process.
    """
    from sentence_transformers import SentenceTransformer

    if not chunks:
        return chunks

    if not hasattr(embed_chunks, "_model"):
        setattr(embed_chunks, "_model", SentenceTransformer(_EMBED_MODEL_NAME))
    model: Any = getattr(embed_chunks, "_model")

    texts = [c["content"] for c in chunks]
    vectors = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    for row, vec in zip(chunks, vectors, strict=True):
        row["embedding"] = [float(x) for x in vec.tolist()]
    return chunks


# =============================================================================
# STEP 8 — Supabase persistence
# =============================================================================


def _pgvector_literal(values: Iterable[float]) -> str:
    """Format a float list for PostgREST / pgvector text input."""
    return "[" + ",".join(f"{float(x):.8g}" for x in values) + "]"


# PostgREST / Supabase default statement timeouts are easy to hit when one
# request upserts hundreds of rows with 768-d floats + long text.
_DEFAULT_UPSERT_BATCH = 25


def store_chunks(
    chunks: list[dict[str, Any]],
    supabase_client: Any,
    *,
    upsert_batch_size: int = _DEFAULT_UPSERT_BATCH,
) -> int:
    """
    Upsert chunk rows (including embeddings) into ``public.chunks``.

    Uses the primary key ``id`` generated during chunking so re-runs can be
    idempotent at the row level. Embeddings are sent as pgvector-compatible
    bracket literals understood by Supabase + pgvector.

    Rows are upserted in batches (default ``upsert_batch_size``) to avoid
    ``statement timeout`` (PostgreSQL 57014) on large PDFs.
    """
    if not chunks:
        return 0

    batch_size = max(1, int(upsert_batch_size))

    rows: list[dict[str, Any]] = []
    for c in chunks:
        emb = c.get("embedding")
        if emb is None:
            raise ValueError("Chunk missing embedding; call embed_chunks first.")
        rows.append(
            {
                "id": c["id"],
                "document_id": c["document_id"],
                "content": c["content"],
                "subject": c["subject"],
                "chapter": c.get("chapter") or None,
                "page_number": c["page_number"],
                "content_type": c["content_type"],
                "embedding": _pgvector_literal(emb),
            }
        )

    total = len(rows)
    logger.info(
        "store_chunks: upserting %d rows in batches of %d (avoids DB statement timeout)",
        total,
        batch_size,
    )
    for start in range(0, total, batch_size):
        batch = rows[start : start + batch_size]
        supabase_client.table("chunks").upsert(batch, on_conflict="id").execute()
        logger.debug(
            "store_chunks: upserted rows %d–%d of %d",
            start + 1,
            min(start + batch_size, total),
            total,
        )

    return total


# =============================================================================
# STEP 9 — Orchestration
# =============================================================================


def run_pipeline(
    pdf_path: str,
    document_id: str,
    subject: str,
    supabase_client: Any,
) -> dict[str, Any]:
    """
    End-to-end runner: ingestion → OCR/text → clean → chunk → embed → store.

    Updates ``documents.upload_status`` to ``processing`` / ``done`` / ``failed``.
    On failure, the error string is returned for observability (Sentry / logs).
    """
    try:
        supabase_client.table("documents").update({"upload_status": "processing"}).eq(
            "id", document_id
        ).execute()

        meta = ingest_pdf(pdf_path)
        if meta["type"] == "scanned":
            pages = ocr_pdf(pdf_path)
        else:
            pages = extract_digital(pdf_path)

        pages = [clean_bangla_text(p) for p in pages]
        chunks = chunk_text(pages, document_id=document_id, subject=subject)
        chunks = embed_chunks(chunks)
        n = store_chunks(chunks, supabase_client)

        supabase_client.table("documents").update({"upload_status": "done"}).eq(
            "id", document_id
        ).execute()
        return {"status": "done", "chunks_stored": n, "error": None}
    except Exception as exc:  # noqa: BLE001 — surface pipeline failures to caller
        logger.exception("run_pipeline failed for document %s", document_id)
        try:
            supabase_client.table("documents").update({"upload_status": "failed"}).eq(
                "id", document_id
            ).execute()
        except Exception:
            logger.exception("Could not mark document %s as failed", document_id)
        return {"status": "failed", "chunks_stored": 0, "error": str(exc)}
