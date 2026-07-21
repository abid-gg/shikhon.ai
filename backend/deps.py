"""FastAPI dependencies: Supabase client, embedding model, settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import Depends
from supabase import Client, create_client

# Always load backend/.env regardless of process cwd (uvicorn may start elsewhere).
_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")

_EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "your-gemini-api-key",
        "your-service-role-key",
        "your-anon-key",
    }
)


def _require_key(name: str, value: str) -> str:
    v = (value or "").strip()
    if not v or v in _PLACEHOLDER_KEYS:
        raise RuntimeError(
            f"{name} is missing or still a placeholder. "
            f"Set it in backend/.env and restart uvicorn."
        )
    return v


@lru_cache
def _supabase_url() -> str:
    url = os.getenv("SUPABASE_URL", "").strip()
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    return url


@lru_cache
def _supabase_service_key() -> str:
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_KEY is not set")
    return key


_supabase_singleton: Client | None = None


def get_supabase_client() -> Client:
    """Service-role client (bypasses RLS; backend-only)."""
    global _supabase_singleton
    if _supabase_singleton is None:
        _supabase_singleton = create_client(_supabase_url(), _supabase_service_key())
    return _supabase_singleton


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_EMBED_MODEL_NAME)


def get_llm_api_key() -> str:
    key = os.getenv("LLM_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()
    return _require_key("LLM_API_KEY (or GEMINI_API_KEY)", key)


def get_llm_base_url() -> str:
    return os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip()


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", "openrouter/free").strip()


SupabaseDep = Annotated[Client, Depends(get_supabase_client)]
EmbedderDep = Annotated[Any, Depends(get_embedding_model)]
LLMKeyDep = Annotated[str, Depends(get_llm_api_key)]
LLMBaseUrlDep = Annotated[str, Depends(get_llm_base_url)]
LLMModelDep = Annotated[str, Depends(get_llm_model)]
