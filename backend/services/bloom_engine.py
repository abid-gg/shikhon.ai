"""
Bloom's Taxonomy constraint engine for ShikhonAI.

PART A: empirical board-exam distributions from ``board_questions``.
PART B: Gemini-backed question generation with per-level quotas and chunk-aware prompts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any

import httpx
from supabase import Client

logger = logging.getLogger(__name__)

BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate")

BLOOM_DEFINITIONS: dict[str, str] = {
    "remember": "recall of facts, terminology, definitions",
    "understand": "explain concepts in own words, give examples",
    "apply": "use knowledge in a new situation, solve a problem",
    "analyze": "break into parts, find patterns, compare/contrast",
    "evaluate": "make judgments, defend a position with evidence",
}

# ---------------------------------------------------------------------------
# PART A — Board distribution
# ---------------------------------------------------------------------------


def _default_distribution(subject: str, grade_level: str, question_type: str) -> dict[str, float]:
    """
    Hardcoded fallbacks when ``board_questions`` has no matching rows.

    Spec:
    - SSC MCQ: remember 50%, understand 30%, apply 20%
    - SSC short: remember 30%, understand 40%, apply 30%
    - HSC creative: apply 35%, analyze 35%, evaluate 30%
    Other combos: smooth prior leaning toward mid-taxonomy for that band.
    """
    _ = subject  # reserved for subject-specific priors later
    gl = (grade_level or "").strip().upper()
    qt = (question_type or "").strip().lower()

    if gl == "SSC" and qt == "mcq":
        return {
            "remember": 0.5,
            "understand": 0.3,
            "apply": 0.2,
            "analyze": 0.0,
            "evaluate": 0.0,
        }
    if gl == "SSC" and qt == "short":
        return {
            "remember": 0.3,
            "understand": 0.4,
            "apply": 0.3,
            "analyze": 0.0,
            "evaluate": 0.0,
        }
    if gl == "HSC" and qt == "creative":
        return {
            "remember": 0.0,
            "understand": 0.0,
            "apply": 0.35,
            "analyze": 0.35,
            "evaluate": 0.3,
        }

    # Generic board-shaped prior (no evaluate-heavy default without evidence)
    if qt == "mcq":
        return {
            "remember": 0.45,
            "understand": 0.35,
            "apply": 0.2,
            "analyze": 0.0,
            "evaluate": 0.0,
        }
    if qt == "short":
        return {
            "remember": 0.25,
            "understand": 0.4,
            "apply": 0.3,
            "analyze": 0.05,
            "evaluate": 0.0,
        }
    # creative / default
    return {
        "remember": 0.0,
        "understand": 0.1,
        "apply": 0.35,
        "analyze": 0.35,
        "evaluate": 0.2,
    }


def get_board_distribution(
    subject: str,
    grade_level: str,
    question_type: str,
    supabase_client: Client | None = None,
) -> dict[str, float]:
    """
    Load empirical Bloom shares from ``board_questions``, normalized to probabilities.

    If ``supabase_client`` is None, only fallbacks are used (e.g. unit tests).
    If no rows match, returns :func:`_default_distribution`.
    """
    base = {b: 0.0 for b in BLOOM_LEVELS}

    if supabase_client is None:
        out = _default_distribution(subject, grade_level, question_type)
        return {**base, **out}

    try:
        resp = (
            supabase_client.table("board_questions")
            .select("bloom_level")
            .eq("subject", subject)
            .eq("grade_level", grade_level.upper())
            .eq("question_type", question_type.lower())
            .execute()
        )
        rows = resp.data or []
    except Exception:
        logger.exception("board_questions query failed; using defaults")
        out = _default_distribution(subject, grade_level, question_type)
        return {**base, **out}

    if not rows:
        out = _default_distribution(subject, grade_level, question_type)
        logger.info(
            "No board_questions for subject=%s grade=%s type=%s — defaults",
            subject,
            grade_level,
            question_type,
        )
        return {**base, **out}

    counts: dict[str, int] = {b: 0 for b in BLOOM_LEVELS}
    for r in rows:
        bl = (r.get("bloom_level") or "").lower()
        if bl in counts:
            counts[bl] += 1
    total = sum(counts.values())
    if total == 0:
        out = _default_distribution(subject, grade_level, question_type)
        return {**base, **out}

    return {b: counts[b] / total for b in BLOOM_LEVELS}


def allocate_question_counts(
    distribution: dict[str, float], total_questions: int
) -> dict[str, int]:
    """
    Convert fractional targets into non-negative integers summing to ``total_questions``.

    Uses largest-remainder method so quotas respect the board prior closely.
    """
    if total_questions <= 0:
        return {b: 0 for b in BLOOM_LEVELS}

    raw = [max(0.0, distribution.get(b, 0.0)) * total_questions for b in BLOOM_LEVELS]
    floors = [int(math.floor(x)) for x in raw]
    assigned = sum(floors)
    remainder = total_questions - assigned
    frac_idx = sorted(
        range(len(BLOOM_LEVELS)),
        key=lambda i: raw[i] - floors[i],
        reverse=True,
    )
    out = {BLOOM_LEVELS[i]: floors[i] for i in range(len(BLOOM_LEVELS))}
    for k in range(remainder):
        out[BLOOM_LEVELS[frac_idx[k]]] += 1
    return out


# ---------------------------------------------------------------------------
# Chunk ranking by Bloom (heuristic; curriculum PDFs rarely label Bloom)
# ---------------------------------------------------------------------------

_REMEMBER_PAT = re.compile(
    r"মানে|সংজ্ঞা|কাকে বলে|কী\s|সংক্ষেপে|definition|means|হলো|হচ্ছে|পরিচিত",
    re.IGNORECASE,
)
_PROCESS_PAT = re.compile(
    r"কারণ|ফলে|ফলস্বরূপ|তুলনা|পার্থক্য|সাদৃশ্য|পদ্ধতি|ধাপ|প্রক্রিয়া|analyze|"
    r"compare|contrast|evaluate|justify|prove|সিদ্ধান্ত",
    re.IGNORECASE,
)


def _chunk_score_for_bloom(chunk: dict[str, Any], bloom_level: str) -> float:
    text = (chunk.get("content") or "")[:8000]
    ct = (chunk.get("content_type") or "prose").lower()
    sim = float(chunk.get("similarity") or 0.0)
    score = sim * 2.0

    if bloom_level == "remember":
        if ct == "prose":
            score += 0.5
        score += min(1.5, len(_REMEMBER_PAT.findall(text)) * 0.35)
        if len(text) < 400:
            score += 0.15
    elif bloom_level in ("apply", "analyze", "evaluate"):
        if ct in ("prose", "formula"):
            score += 0.25
        score += min(2.0, len(_PROCESS_PAT.findall(text)) * 0.3)
        if ct == "table" and bloom_level == "analyze":
            score += 0.35
    else:  # understand
        if ct == "prose":
            score += 0.35
        score += min(1.0, len(_REMEMBER_PAT.findall(text)) * 0.1)
        score += min(1.0, len(_PROCESS_PAT.findall(text)) * 0.15)

    return score


def rank_chunks_for_bloom(chunks: list[dict[str, Any]], bloom_level: str) -> list[dict[str, Any]]:
    """Sort retrieved chunks by suitability for a given Bloom level."""
    return sorted(
        chunks,
        key=lambda c: _chunk_score_for_bloom(c, bloom_level),
        reverse=True,
    )


def _pick_chunk_for_slot(
    ranked: list[dict[str, Any]], slot_index: int, fallback: list[dict[str, Any]]
) -> dict[str, Any]:
    pool = ranked if ranked else fallback
    if not pool:
        raise ValueError("No chunks available for question generation")
    return pool[slot_index % len(pool)]


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse first JSON object from model output (tolerates stray whitespace / fences)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(t[start : end + 1])


def _validate_question_payload(
    data: dict[str, Any],
    *,
    question_type: str,
    marks: int,
    bloom_level: str,
    chunk_id: str,
) -> None:
    # Auto-inject known metadata instead of failing if the model omitted them
    data["question_type"] = question_type.lower()
    data["bloom_level"] = bloom_level.lower()
    data["marks"] = int(marks)

    if "chunk_ids" not in data or not isinstance(data["chunk_ids"], list) or not data["chunk_ids"]:
        data["chunk_ids"] = [str(chunk_id)]
    else:
        # Ensure primary chunk id present
        cids = data["chunk_ids"]
        if str(chunk_id) not in [str(x) for x in cids]:
            data["chunk_ids"] = [str(chunk_id)] + [str(x) for x in cids if str(x) != str(chunk_id)]

    required = (
        "question_text",
        "expected_answer_points",
    )
    for k in required:
        if k not in data:
            raise ValueError(f"Missing key: {k}")

    pts = data.get("expected_answer_points")
    if not isinstance(pts, list) or len(pts) == 0:
        raise ValueError("expected_answer_points must be a non-empty list")

    if question_type.lower() == "mcq":
        opts = data.get("options")
        cor = data.get("correct_option")
        if not isinstance(opts, list) or len(opts) < 4:
            raise ValueError("MCQ requires options with at least 4 entries")
        
        cor_s = str(cor).strip() if cor else ""
        cor_s = cor_s[0] if cor_s and cor_s[0] in "কখগঘ" else cor_s
        
        mapping = {"A": "ক", "B": "খ", "C": "গ", "D": "ঘ", "1": "ক", "2": "খ", "3": "গ", "4": "ঘ"}
        if cor_s.upper() in mapping:
            cor_s = mapping[cor_s.upper()]
            
        if cor_s not in ("ক", "খ", "গ", "ঘ"):
            raise ValueError(f"MCQ requires correct_option in ক|খ|গ|ঘ, got: {cor_s}")
        data["correct_option"] = cor_s


_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)  # legacy; generation uses OpenAI-compatible _call_llm below


async def _call_llm(
    api_key: str,
    base_url: str,
    model: str,
    system_text: str,
    user_text: str,
    *,
    retry_invalid_json: bool,
) -> dict[str, Any]:
    """Call an OpenAI-compatible LLM and return parsed JSON object."""

    async def _post(payload: dict[str, Any]) -> dict[str, Any]:
        max_retries = 5
        base_delay = 5.0

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "ShikhonAI",
        }
        endpoint = f"{base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=120.0) as client:
            for attempt in range(max_retries + 1):
                r = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                )

                if r.status_code in (429, 500, 502, 503) and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "LLM API %d error. Retrying in %ss (attempt %d/%d)",
                        r.status_code, delay, attempt + 1, max_retries
                    )
                    await asyncio.sleep(delay)
                    continue

                if r.status_code >= 400:
                    detail = r.text[:800]
                    raise RuntimeError(
                        f"LLM API HTTP {r.status_code} ({endpoint}): {detail}"
                    )

                r.raise_for_status()
                return r.json()

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.35,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"}
    }

    for attempt in range(2 if retry_invalid_json else 1):
        body = await _post(payload)
        cand = body.get("choices", [{}])[0]
        if cand.get("finish_reason") not in (None, "stop", "length"):
            logger.warning(
                f"LLM finish_reason={cand.get('finish_reason')!r} body={repr(body)[:400]}"
            )
        message = cand.get("message", {})
        if not message:
            raise RuntimeError(f"Empty LLM response: {repr(body)[:500]}")
        text = message.get("content") or ""
        try:
            return _extract_json_object(text)
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 0 and retry_invalid_json:
                payload["messages"].append({"role": "assistant", "content": text})
                payload["messages"].append({"role": "user", "content": "Your previous response was not valid JSON. Return ONLY the JSON object."})
                logger.warning("LLM JSON parse failed; retrying once: %s", e)
                continue
            raise


def _build_user_prompt(
    *,
    question_type: str,
    bloom_level: str,
    bloom_definition: str,
    subject: str,
    grade_level: str,
    marks_per_question: int,
    chunk_content: str,
    chunk_id: str,
) -> str:
    # JSON example uses doubled braces for .format safety — use % formatting instead
    lines = [
        f"Generate exactly 1 {question_type} question at Bloom's Taxonomy Level: {bloom_level} "
        f"(definition: {bloom_definition}).",
        f"Subject: {subject}, Grade: {grade_level}, Marks: {marks_per_question}",
        "",
        "Use ONLY the following curriculum content as your source:",
        "---",
        chunk_content,
        "---",
        "",
        "Return a JSON object with these exact keys:",
        "{",
        '  "question_text": "the question in Bangla",',
        f'  "question_type": "{question_type}",',
        f'  "bloom_level": "{bloom_level}",',
        f'  "marks": {marks_per_question},',
        '  "expected_answer_points": ["point 1 in Bangla", "point 2 in Bangla", "point 3 in Bangla"],',
        f'  "chunk_ids": ["{chunk_id}"]',
        "}",
        "",
        "Rules:",
        "- Question must be answerable from the provided content only",
        '- For MCQ: include "options": ["ক) ...", "খ) ...", "গ) ...", "ঘ) ..."] and '
        '"correct_option": "ক"|"খ"|"গ"|"ঘ"',
        "- expected_answer_points must list the key facts/steps a student must mention to get full marks",
        "- Do not copy sentences verbatim; rephrase as a question",
    ]
    return "\n".join(lines)


async def generate_questions(
    chunks: list[dict[str, Any]],
    subject: str,
    grade_level: str,
    question_type: str,
    total_questions: int,
    marks_per_question: int,
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    supabase_client: Client | None = None,
) -> list[dict[str, Any]]:
    """
    Generate ``total_questions`` items respecting board-derived Bloom quotas.

    Each item is a dict aligned with ``exam_questions`` semantic fields plus
    MCQ ``options`` / ``correct_option`` when applicable (stored inside JSONB
    rubric by the router if needed).
    """
    if total_questions < 1:
        return []

    dist = get_board_distribution(subject, grade_level, question_type, supabase_client)
    alloc = allocate_question_counts(dist, total_questions)

    system = (
        "You are an expert question setter for Bangladesh SSC/HSC board exams. "
        "You generate questions strictly in Bangla. Return ONLY valid JSON, no markdown, "
        "no explanation."
    )

    fallback_pool = chunks[:]
    results: list[dict[str, Any]] = []
    slot = 0

    for bloom_level in BLOOM_LEVELS:
        n = alloc.get(bloom_level, 0)
        if n <= 0:
            continue
        ranked = rank_chunks_for_bloom(chunks, bloom_level)
        bloom_def = BLOOM_DEFINITIONS[bloom_level]

        for _ in range(n):
            ch = _pick_chunk_for_slot(ranked, slot, fallback_pool)
            slot += 1
            cid = str(ch.get("id", ""))
            chunk_body = ch.get("content") or ""
            user = _build_user_prompt(
                question_type=question_type,
                bloom_level=bloom_level,
                bloom_definition=bloom_def,
                subject=subject,
                grade_level=grade_level.upper(),
                marks_per_question=marks_per_question,
                chunk_content=chunk_body,
                chunk_id=cid,
            )
            data = await _call_llm(
                llm_api_key,
                llm_base_url,
                llm_model,
                system,
                user,
                retry_invalid_json=True,
            )
            _validate_question_payload(
                data,
                question_type=question_type,
                marks=marks_per_question,
                bloom_level=bloom_level,
                chunk_id=cid,
            )
            results.append(data)

    return results
