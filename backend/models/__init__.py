"""Pydantic schemas for request/response bodies."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    name: str
    role: str  # 'teacher' or 'student'


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: Optional[datetime] = None


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ==================== Exams ====================


class ExamCreate(BaseModel):
    title: str
    subject: str
    grade_level: str  # 'SSC' or 'HSC'
    duration_minutes: int = 60


class ExamQuestion(BaseModel):
    id: str
    question_text: str
    question_type: str  # 'mcq', 'short', 'creative'
    bloom_level: str
    marks: int
    expected_answer_points: Optional[list[str]] = None


class ExamResponse(BaseModel):
    id: str
    exam_code: str
    title: str
    subject: str
    grade_level: str
    duration_minutes: int
    status: str  # 'draft', 'active', 'ended'
    questions: Optional[list[ExamQuestion]] = None
    session_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ExamActivate(BaseModel):
    pass


class ExamEnd(BaseModel):
    pass


# ==================== Sessions ====================


class StudentAnswer(BaseModel):
    question_id: str
    answer_text: str


class SubmitAnswers(BaseModel):
    answers: list[StudentAnswer]


class AnswerResult(BaseModel):
    id: str
    question_id: str
    question_text: str
    answer_text: Optional[str] = None
    ai_score: Optional[float] = None
    ai_justification: Optional[str] = None
    marks: int


class SessionResult(BaseModel):
    session_id: str
    total_score: Optional[float] = None
    answers: list[AnswerResult]


class SubmissionResponse(BaseModel):
    status: str
    message: str


# ==================== Documents ====================


class DocumentResponse(BaseModel):
    id: str
    filename: str
    subject: str
    grade_level: str
    upload_status: str
    created_at: Optional[datetime] = None


class DocumentStatus(BaseModel):
    status: str
    chunks_count: Optional[int] = None


# ==================== Analytics ====================


class QuestionAnalytic(BaseModel):
    question_id: str
    question_text: str
    avg_score: float
    avg_score_pct: float
    flagged_count: int
    bloom_level: str


class FlaggedAnswer(BaseModel):
    student_name: str
    question_text: str
    answer_text: Optional[str] = None
    ai_score: float
    session_id: str
    answer_id: str


class ExamAnalytics(BaseModel):
    total_students: int
    submitted_count: int
    graded_count: int
    score_distribution: list[dict[str, Any]]
    question_analytics: list[QuestionAnalytic]
    weak_topics: list[str]
    flagged_answers: list[FlaggedAnswer]


class OverrideScore(BaseModel):
    override_score: float
