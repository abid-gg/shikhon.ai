"""Exam session endpoints for answer submission and results."""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

from deps import SupabaseDep, StudentDep
from models import SubmitAnswers, SubmissionResponse, SessionResult, AnswerResult
from services.grader import grade_session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/submit", response_model=SubmissionResponse)
async def submit_answers(
    session_id: str,
    body: SubmitAnswers,
    student: dict = Depends(StudentDep),
    supabase: SupabaseDep = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Submit exam answers (student only)."""
    try:
        # Verify session belongs to student
        session = (
            supabase.table("exam_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("student_id", student["id"])
            .single()
            .execute()
        )
        
        # Check exam is still active
        exam = (
            supabase.table("exams")
            .select("*")
            .eq("id", session.data["exam_id"])
            .single()
            .execute()
        )
        
        if exam.data["status"] != "active":
            raise HTTPException(status_code=403, detail="Exam is not active")
        
        # Insert all answers
        for answer in body.answers:
            supabase.table("student_answers").insert({
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "question_id": answer.question_id,
                "answer_text": answer.answer_text,
                "ai_score": None,
                "is_flagged": False,
            }).execute()
        
        # Update session
        supabase.table("exam_sessions").update({
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "submitted",
        }).eq("id", session_id).execute()
        
        # Trigger background grading
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if background_tasks and gemini_key:
            background_tasks.add_task(
                grade_session,
                session_id,
                supabase,
                gemini_key,
            )
        
        return {
            "status": "submitted",
            "message": "উত্তর জমা হয়েছে",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{session_id}/results", response_model=SessionResult)
async def get_results(
    session_id: str,
    student: dict = Depends(StudentDep),
    supabase: SupabaseDep = None,
) -> dict:
    """Get exam results (student only, only if graded)."""
    try:
        # Verify session belongs to student
        session = (
            supabase.table("exam_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("student_id", student["id"])
            .single()
            .execute()
        )
        
        if session.data["status"] != "graded":
            raise HTTPException(
                status_code=403,
                detail="Exam results not ready yet",
            )
        
        # Fetch all answers with question details
        answers_data = (
            supabase.table("student_answers")
            .select("*, exam_questions:question_id(question_text, marks)")
            .eq("session_id", session_id)
            .execute()
        )
        
        answers = []
        for answer in answers_data.data:
            answers.append(AnswerResult(
                id=answer["id"],
                question_id=answer["question_id"],
                question_text=answer["exam_questions"]["question_text"],
                answer_text=answer["answer_text"],
                ai_score=answer.get("ai_score") or answer.get("teacher_override_score"),
                ai_justification=answer.get("ai_justification"),
                marks=answer["exam_questions"]["marks"],
            ))
        
        return {
            "session_id": session_id,
            "total_score": session.data["total_score"],
            "answers": answers,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
