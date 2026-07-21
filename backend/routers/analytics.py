"""Exam analytics endpoints."""

from fastapi import APIRouter, HTTPException, Depends

from deps import SupabaseDep, TeacherDep
from models import ExamAnalytics, QuestionAnalytic, FlaggedAnswer, OverrideScore

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/exam/{exam_id}", response_model=ExamAnalytics)
async def get_exam_analytics(
    exam_id: str,
    teacher: dict = Depends(TeacherDep),
    supabase: SupabaseDep = None,
) -> dict:
    """Get analytics for an exam (teacher only)."""
    try:
        # Verify exam ownership
        exam = (
            supabase.table("exams")
            .select("*")
            .eq("id", exam_id)
            .eq("teacher_id", teacher["id"])
            .single()
            .execute()
        )
        
        # Get all sessions for this exam
        sessions = (
            supabase.table("exam_sessions")
            .select("*")
            .eq("exam_id", exam_id)
            .execute()
        )
        
        total_students = len(sessions.data)
        submitted_count = sum(1 for s in sessions.data if s["status"] != "active")
        graded_count = sum(1 for s in sessions.data if s["status"] == "graded")
        
        # Calculate score distribution (0-20, 20-40, 40-60, 60-80, 80-100)
        score_dist = {}
        for s in sessions.data:
            if s["total_score"] is not None:
                pct = (s["total_score"] / 100) * 100  # Assuming max 100
                bucket = f"{int(pct // 20) * 20}-{int(pct // 20) * 20 + 20}"
                score_dist[bucket] = score_dist.get(bucket, 0) + 1
        
        score_distribution = [
            {"range": r, "count": score_dist.get(r, 0)}
            for r in ["0-20", "20-40", "40-60", "60-80", "80-100"]
        ]
        
        # Question analytics
        questions = (
            supabase.table("exam_questions")
            .select("*")
            .eq("exam_id", exam_id)
            .execute()
        )
        
        question_analytics = []
        weak_topics = []
        
        for q in questions.data:
            # Get all answers for this question
            answers = (
                supabase.table("student_answers")
                .select("ai_score, is_flagged")
                .eq("question_id", q["id"])
                .execute()
            )
            
            scores = [a["ai_score"] for a in answers.data if a.get("ai_score") is not None]
            avg_score = sum(scores) / len(scores) if scores else 0
            avg_score_pct = (avg_score / q["marks"]) * 100 if q["marks"] > 0 else 0
            flagged_count = sum(1 for a in answers.data if a.get("is_flagged"))
            
            qa = QuestionAnalytic(
                question_id=q["id"],
                question_text=q["question_text"],
                avg_score=avg_score,
                avg_score_pct=avg_score_pct,
                flagged_count=flagged_count,
                bloom_level=q["bloom_level"],
            )
            question_analytics.append(qa)
            
            if avg_score_pct < 50:
                weak_topics.append(q["question_text"])
        
        # Flagged answers
        all_flagged = (
            supabase.table("student_answers")
            .select("*, exam_sessions:session_id(student_id), exam_questions:question_id(question_text)")
            .eq("is_flagged", True)
            .execute()
        )
        
        flagged_answers = []
        for a in all_flagged.data:
            # Get student name
            if a.get("exam_sessions") and a["exam_sessions"].get("student_id"):
                student_id = a["exam_sessions"]["student_id"]
                try:
                    user = (
                        supabase.table("users")
                        .select("name")
                        .eq("id", student_id)
                        .single()
                        .execute()
                    )
                    student_name = user.data.get("name", "Unknown")
                except:
                    student_name = "Unknown"
            else:
                student_name = "Unknown"
            
            flagged_answers.append(FlaggedAnswer(
                student_name=student_name,
                question_text=a["exam_questions"]["question_text"],
                answer_text=a["answer_text"],
                ai_score=a.get("ai_score") or 0,
                session_id=a["session_id"],
                answer_id=a["id"],
            ))
        
        return {
            "total_students": total_students,
            "submitted_count": submitted_count,
            "graded_count": graded_count,
            "score_distribution": score_distribution,
            "question_analytics": question_analytics,
            "weak_topics": weak_topics,
            "flagged_answers": flagged_answers,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/answers/{answer_id}/override")
async def override_answer_score(
    answer_id: str,
    body: OverrideScore,
    teacher: dict = Depends(TeacherDep),
    supabase: SupabaseDep = None,
) -> dict:
    """Override an answer's score (teacher only)."""
    try:
        # Get the answer
        answer = (
            supabase.table("student_answers")
            .select("*")
            .eq("id", answer_id)
            .single()
            .execute()
        )
        
        # Update override score
        supabase.table("student_answers").update({
            "teacher_override_score": body.override_score,
        }).eq("id", answer_id).execute()
        
        # Recalculate session total_score
        session_id = answer.data["session_id"]
        all_answers = (
            supabase.table("student_answers")
            .select("ai_score, teacher_override_score")
            .eq("session_id", session_id)
            .execute()
        )
        
        total = 0
        for a in all_answers.data:
            score = a.get("teacher_override_score") or a.get("ai_score") or 0
            total += score
        
        # Update session
        updated_session = supabase.table("exam_sessions").update({
            "total_score": total,
        }).eq("id", session_id).execute()
        
        return updated_session.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
