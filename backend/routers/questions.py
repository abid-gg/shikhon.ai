"""
Exam question generation (Bloom-constrained) and CRUD for teacher workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import EmbedderDep, LLMKeyDep, LLMBaseUrlDep, LLMModelDep, SupabaseDep
from services.bloom_engine import generate_questions
from services.retrieval import retrieve_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/questions", tags=["questions"])


class GenerateQuestionsRequest(BaseModel):
    exam_id: UUID
    subject: str = Field(..., min_length=1)
    grade_level: Literal["SSC", "HSC"]
    question_type: Literal["mcq", "short", "creative"]
    total_questions: int = Field(..., ge=1, le=50)
    marks_per_question: int = Field(..., ge=1, le=100)
    chapter_filter: str | None = None


class QuestionUpdateRequest(BaseModel):
    question_text: str | None = Field(None, min_length=1)
    marks: int | None = Field(None, ge=1, le=100)
    expected_answer_points: list[Any] | dict[str, Any] | None = None


def _exam_row(supabase, exam_id: str) -> dict[str, Any]:
    r = (
        supabase.table("exams")
        .select("id,teacher_id,title,subject,grade_level,exam_code,status")
        .eq("id", exam_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Exam not found")
    return r.data[0]


def _next_question_order(supabase, exam_id: str) -> int:
    r = (
        supabase.table("exam_questions")
        .select("question_order")
        .eq("exam_id", exam_id)
        .order("question_order", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return 0
    return int(r.data[0]["question_order"]) + 1


def _normalize_expected_answer_points(q: dict[str, Any]) -> Any:
    """Keep list for short/creative; bundle MCQ extras into JSONB-friendly dict."""
    qt = str(q.get("question_type", "")).lower()
    base_points = q.get("expected_answer_points")
    if qt != "mcq":
        return base_points
    return {
        "rubric": base_points,
        "options": q.get("options"),
        "correct_option": q.get("correct_option"),
    }


def _question_to_row(
    exam_id: str,
    q: dict[str, Any],
    question_order: int,
) -> dict[str, Any]:
    return {
        "exam_id": exam_id,
        "question_text": q["question_text"],
        "question_type": str(q["question_type"]).lower(),
        "bloom_level": str(q["bloom_level"]).lower(),
        "marks": int(float(q["marks"])),
        "expected_answer_points": _normalize_expected_answer_points(q),
        "chunk_ids": q.get("chunk_ids") or [],
        "question_order": question_order,
    }


@router.post("/generate")
async def generate_exam_questions(
    body: GenerateQuestionsRequest,
    supabase: SupabaseDep,
    embedder: EmbedderDep,
    llm_api_key: LLMKeyDep,
    llm_base_url: LLMBaseUrlDep,
    llm_model: LLMModelDep,
) -> list[dict[str, Any]]:
    """
    Retrieve curriculum chunks, run Bloom-constrained Gemini generation, and
    persist rows into ``exam_questions``.
    """
    exam_id = str(body.exam_id)
    _exam_row(supabase, exam_id)

    chunks = await retrieve_chunks(
        query=f"{body.subject} {body.grade_level} curriculum exam content",
        subject=body.subject,
        top_k=max(15, body.total_questions * 3),
        supabase_client=supabase,
        embedding_model=embedder,
        chapter_filter=body.chapter_filter,
    )
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No chunks found for this subject (and chapter filter). Upload documents first.",
        )

    try:
        generated = await generate_questions(
            chunks=chunks,
            subject=body.subject,
            grade_level=body.grade_level,
            question_type=body.question_type,
            total_questions=body.total_questions,
            marks_per_question=body.marks_per_question,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            supabase_client=supabase,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"Model validation error: {e}") from e
    except RuntimeError as e:
        msg = str(e)
        if "placeholder" in msg.lower() or "missing" in msg.lower():
            raise HTTPException(status_code=503, detail=msg) from e
        raise HTTPException(status_code=502, detail=msg) from e
    except Exception as e:
        logger.exception("generate_questions failed")
        raise HTTPException(status_code=502, detail=str(e)) from e

    order_start = _next_question_order(supabase, exam_id)
    rows = [
        _question_to_row(exam_id, q, order_start + i)
        for i, q in enumerate(generated)
    ]

    ins = supabase.table("exam_questions").insert(rows).select().execute()
    return list(ins.data or [])


@router.get("/exam/{exam_id}")
def list_exam_questions(
    exam_id: UUID,
    supabase: SupabaseDep,
) -> list[dict[str, Any]]:
    """Teacher view: all questions for an exam including rubric JSON."""
    eid = str(exam_id)
    _exam_row(supabase, eid)
    r = (
        supabase.table("exam_questions")
        .select("*")
        .eq("exam_id", eid)
        .order("question_order")
        .execute()
    )
    return list(r.data or [])


@router.put("/{question_id}")
def update_question(
    question_id: UUID,
    body: QuestionUpdateRequest,
    supabase: SupabaseDep,
) -> dict[str, Any]:
    """Edit stem, marks, or rubric JSON for a single question."""
    qid = str(question_id)
    existing = (
        supabase.table("exam_questions")
        .select("id")
        .eq("id", qid)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Question not found")

    patch: dict[str, Any] = {}
    if body.question_text is not None:
        patch["question_text"] = body.question_text
    if body.marks is not None:
        patch["marks"] = body.marks
    if body.expected_answer_points is not None:
        patch["expected_answer_points"] = body.expected_answer_points
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")

    r = supabase.table("exam_questions").update(patch).eq("id", qid).select().limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Question not found after update")
    return r.data[0]
