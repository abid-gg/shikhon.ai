"""
pgvector-backed chunk retrieval for RAG and question generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import numpy as np
from supabase import Client

logger = logging.getLogger(__name__)


def _embedding_to_rpc_param(vec: list[float]) -> str:
    """PostgREST often accepts vector parameters as a bracket literal string."""
    return "[" + ",".join(f"{float(x):.8g}" for x in vec) + "]"


async def retrieve_chunks(
    query: str,
    subject: str,
    top_k: int,
    supabase_client: Client,
    embedding_model: Any,
    *,
    chapter_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Embed ``query`` and run cosine-style similarity against ``chunks.embedding``.

    Preferred path: Supabase RPC ``match_chunks_by_subject`` (see ``schema.sql``).
    Fallback: fetch a bounded set of rows for ``subject`` and rank in Python
    (slower, but works before the RPC is deployed).
    """
    if top_k < 1:
        return []

    def _encode() -> np.ndarray:
        v = embedding_model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        return np.asarray(v[0], dtype=np.float64)

    query_vec = await asyncio.to_thread(_encode)
    emb_list = [float(x) for x in query_vec.tolist()]

    def _rpc() -> list[dict[str, Any]]:
        try:
            resp = supabase_client.rpc(
                "match_chunks_by_subject",
                {
                    "query_embedding": emb_list,
                    "filter_subject": subject,
                    "match_count": top_k,
                    "chapter_filter": chapter_filter or "",
                },
            ).execute()
            return list(resp.data or [])
        except Exception as e:
            logger.warning("match_chunks_by_subject RPC failed (%s); using Python fallback", e)
            return []

    rows = await asyncio.to_thread(_rpc)
    if rows:
        return rows

    def _fallback() -> list[dict[str, Any]]:
        q = (
            supabase_client.table("chunks")
            .select("id,document_id,content,subject,chapter,page_number,content_type,embedding,created_at")
            .eq("subject", subject)
            .not_.is_("embedding", "null")
            .limit(400)
            .execute()
        )
        data = q.data or []
        if chapter_filter:
            cf = chapter_filter.lower()
            data = [
                r
                for r in data
                if (r.get("chapter") or "").lower().find(cf) >= 0
            ]
        scored: list[tuple[float, dict[str, Any]]] = []
        for r in data:
            emb = r.get("embedding")
            if emb is None:
                continue
            if isinstance(emb, str):
                try:
                    emb = json.loads(emb)
                except json.JSONDecodeError:
                    continue
            va = np.asarray(emb_list, dtype=np.float64)
            vb = np.asarray(emb, dtype=np.float64)
            sim = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-12))
            rr = dict(r)
            rr["similarity"] = sim
            scored.append((sim, rr))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t[1] for t in scored[:top_k]]

    return await asyncio.to_thread(_fallback)
