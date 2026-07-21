"""Document upload and management endpoints."""

import uuid
import os

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends

from deps import SupabaseDep, TeacherDep
from models import DocumentResponse, DocumentStatus

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    subject: str = Form(...),
    grade_level: str = Form(...),
    teacher: dict = Depends(TeacherDep),
    supabase: SupabaseDep = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """Upload a PDF document (teacher only)."""
    try:
        # Validate file
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files allowed")
        
        # Upload to Supabase Storage
        contents = await file.read()
        file_path = f"{teacher['id']}/{uuid.uuid4()}_{file.filename}"
        
        supabase.storage.from_("documents").upload(file_path, contents)
        
        # Create document record
        doc_id = str(uuid.uuid4())
        doc_result = supabase.table("documents").insert({
            "id": doc_id,
            "teacher_id": teacher["id"],
            "filename": file.filename,
            "subject": subject,
            "grade_level": grade_level,
            "upload_status": "pending",
        }).execute()
        
        doc = doc_result.data[0]
        
        return {
            "id": doc["id"],
            "filename": doc["filename"],
            "subject": doc["subject"],
            "grade_level": doc["grade_level"],
            "upload_status": doc["upload_status"],
            "created_at": doc["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    teacher: dict = Depends(TeacherDep),
    supabase: SupabaseDep = None,
) -> list:
    """List all documents uploaded by teacher."""
    try:
        result = (
            supabase.table("documents")
            .select("*")
            .eq("teacher_id", teacher["id"])
            .order("created_at", desc=True)
            .execute()
        )
        
        return [
            {
                "id": doc["id"],
                "filename": doc["filename"],
                "subject": doc["subject"],
                "grade_level": doc["grade_level"],
                "upload_status": doc["upload_status"],
                "created_at": doc["created_at"],
            }
            for doc in result.data
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(
    document_id: str,
    supabase: SupabaseDep = None,
) -> dict:
    """Get document processing status."""
    try:
        doc = (
            supabase.table("documents")
            .select("upload_status")
            .eq("id", document_id)
            .single()
            .execute()
        )
        
        chunks_count = None
        if doc.data["upload_status"] == "done":
            chunks = (
                supabase.table("chunks")
                .select("id", count="exact")
                .eq("document_id", document_id)
                .execute()
            )
            chunks_count = chunks.count
        
        return {
            "status": doc.data["upload_status"],
            "chunks_count": chunks_count,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
