"""Authentication endpoints."""

import os
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from supabase import Client

from deps import SupabaseDep, CurrentUserDep
from models import UserRegister, UserLogin, AuthToken, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthToken)
async def register(body: UserRegister, supabase: SupabaseDep) -> dict:
    """Register a new user."""
    try:
        # Create auth user
        response = supabase.auth.sign_up(
            email=body.email,
            password=body.password,
        )
        
        if not response.user:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        # Insert into users table
        supabase.table("users").insert({
            "id": response.user.id,
            "email": body.email,
            "name": body.name,
            "role": body.role,  # 'teacher' or 'student'
        }).execute()
        
        # Return token
        session = response.session
        if not session:
            raise HTTPException(status_code=400, detail="Failed to create session")
        
        return {
            "access_token": session.access_token,
            "token_type": "bearer",
            "user": UserResponse(
                id=response.user.id,
                email=response.user.email or "",
                name=body.name,
                role=body.role,
                created_at=response.user.created_at,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration error: {str(e)}")


@router.post("/login", response_model=AuthToken)
async def login(body: UserLogin, supabase: SupabaseDep) -> dict:
    """Login user."""
    try:
        response = supabase.auth.sign_in_with_password(
            email=body.email,
            password=body.password,
        )
        
        if not response.user or not response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Fetch user profile
        profile = (
            supabase.table("users")
            .select("*")
            .eq("id", response.user.id)
            .single()
            .execute()
        )
        
        return {
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "user": UserResponse(
                id=response.user.id,
                email=response.user.email or "",
                name=profile.data.get("name", ""),
                role=profile.data.get("role", ""),
                created_at=response.user.created_at,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Login failed")


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUserDep) -> dict:
    """Get current user profile."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "created_at": user.get("created_at"),
    }
