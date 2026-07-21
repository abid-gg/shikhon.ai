"""Exam management endpoints."""

import random
import string
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from supabase import Client

from deps import SupabaseDep, TeacherDep, StudentDep, CurrentUserDep
from models import ExamCreate, ExamResponse, ExamQuestion

router = APIRouter(prefix="/exams", tags=["exams"])


def generate_exam_code() -> str:
    """Generate 6-char alphanumeric code (no ambiguous chars)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No O, I, 1, 0
    return "".join(random.choice(chars) for _ in range(6))


@router.post("/create", response_model=ExamResponse)
async def create_exam(body: ExamCreate, teacher: dict = Depends(TeacherDep), supabase: SupabaseDep = None) -> dict:
    """Create a new exam (teacher only)."""
    exam_code = generate_exam_code()
    
    try:
        result = (
            supabase.table("exams")
            .insert({
                "id": str(uuid.uuid4()),
                "teacher_id": teacher["id"],
                "title": body.title,
                "subject": body.subject,
                "grade_level": body.grade_level,
                "exam_code": exam_code,
                "duration_minutes": body.duration_minutes,
                "status": "draft",
            })
            .execute()
        )
        
        exam = result.data[0]
        return {
            "id": exam["id"],
            "exam_code": exam["exam_code"],
            "title": exam["title"],
            "subject": exam["subject"],
            "grade_level": exam["grade_level"],
            "duration_minutes": exam["duration_minutes"],
            "status": exam["status"],
            "created_at": exam["created_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create exam: {str(e)}")


@router.post("/{exam_id}/activate", response_model=ExamResponse)
async def activate_exam(exam_id: str, teacher: dict = Depends(TeacherDep), supabase: SupabaseDep = None) -> dict:
    """Activate an exam (teacher only)."""
    try:
        # Verify ownership
        exam = (
            supabase.table("exams")
            .select("*")
            .eq("id", exam_id)
            .eq("teacher_id", teacher["id"])
            .single()
            .execute()
        )
        
        # Update status and record activated_at
        updated = (
            supabase.table("exams")
            .update({
                "status": "active",
            })
            .eq("id", exam_id)
            .execute()
        )
        
        exam = updated.data[0]
        return {
            "id": exam["id"],
            "exam_code": exam["exam_code"],
            "title": exam["title"],
            "subject": exam["subject"],
            "grade_level": exam["grade_level"],
            "duration_minutes": exam["duration_minutes"],
            "status": exam["status"],
            "created_at": exam["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exam_id}/end", response_model=ExamResponse)
async def end_exam(exam_id: str, teacher: dict = Depends(TeacherDep), supabase: SupabaseDep = None) -> dict:
    """End an exam and trigger grading (teacher only)."""
    try:
        # Verify ownership
        exam = (
            supabase.table("exams")
            .select("*")
            .eq("id", exam_id)
            .eq("teacher_id", teacher["id"])
            .single()
            .execute()
        )
        
        # Update status
        updated = (
            supabase.table("exams")
            .update({
                "status": "ended",
            })
            .eq("id", exam_id)
            .execute()
        )
        
        exam = updated.data[0]
        return {
            "id": exam["id"],
            "exam_code": exam["exam_code"],
            "title": exam["title"],
            "subject": exam["subject"],
            "grade_level": exam["grade_level"],
            "duration_minutes": exam["duration_minutes"],
            "status": exam["status"],
            "created_at": exam["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(exam_id: str, teacher: dict = Depends(TeacherDep), supabase: SupabaseDep = None) -> dict:
    """Get exam with all questions (teacher only)."""
    try:
        exam = (
            supabase.table("exams")
            .select("*")
            .eq("id", exam_id)
            .eq("teacher_id", teacher["id"])
            .single()
            .execute()
        )
        
        questions = (
            supabase.table("exam_questions")
            .select("*")
            .eq("exam_id", exam_id)
            .order("question_order")
            .execute()
        )
        
        return {
            "id": exam.data["id"],
            "exam_code": exam.data["exam_code"],
            "title": exam.data["title"],
            "subject": exam.data["subject"],
            "grade_level": exam.data["grade_level"],
            "duration_minutes": exam.data["duration_minutes"],
            "status": exam.data["status"],
            "questions": [
                ExamQuestion(
                    id=q["id"],
                    question_text=q["question_text"],
                    question_type=q["question_type"],
                    bloom_level=q["bloom_level"],
                    marks=q["marks"],
                    expected_answer_points=q.get("expected_answer_points"),
                )
                for q in questions.data
            ],
            "created_at": exam.data["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/join/{exam_code}", response_model=ExamResponse)
async def join_exam(exam_code: str, student: dict = Depends(StudentDep), supabase: SupabaseDep = None) -> dict:
    """Join exam by code (student only)."""
    try:
        # Look up exam by code
        exam_result = (
            supabase.table("exams")
            .select("*")
            .eq("exam_code", exam_code)
            .single()
            .execute()
        )
        
        exam = exam_result.data
        
        # Check if exam is active
        if exam["status"] != "active":
            raise HTTPException(
                status_code=403,
                detail="Exam is not active"
            )
        
        # Create or retrieve exam_session
        existing_session = (
            supabase.table("exam_sessions")
            .select("*")
            .eq("exam_id", exam["id"])
            .eq("student_id", student["id"])
            .execute()
        )
        
        if existing_session.data:
            session = existing_session.data[0]
        else:
            session_result = (
                supabase.table("exam_sessions")
                .insert({
                    "id": str(uuid.uuid4()),
                    "exam_id": exam["id"],
                    "student_id": student["id"],
                })
                .execute()
            )
            session = session_result.data[0]
        
        # Fetch questions (WITHOUT expected_answer_points for students)
        questions = (
            supabase.table("exam_questions")
            .select("*")
            .eq("exam_id", exam["id"])
            .order("question_order")
            .execute()
        )
        
        return {
            "id": exam["id"],
            "exam_code": exam["exam_code"],
            "title": exam["title"],
            "subject": exam["subject"],
            "grade_level": exam["grade_level"],
            "duration_minutes": exam["duration_minutes"],
            "status": exam["status"],
            "session_id": session["id"],
            "questions": [
                ExamQuestion(
                    id=q["id"],
                    question_text=q["question_text"],
                    question_type=q["question_type"],
                    bloom_level=q["bloom_level"],
                    marks=q["marks"],
                    expected_answer_points=None,  # Hidden from students
                )
                for q in questions.data
            ],
            "created_at": exam["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
