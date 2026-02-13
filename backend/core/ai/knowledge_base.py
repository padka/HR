from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import delete, func, or_, select

from backend.core.db import async_session
from backend.domain.ai.models import KnowledgeBaseChunk, KnowledgeBaseDocument


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]{3,}")

# Minimal RU stopwords to keep keyword search stable/cost-effective.
_STOPWORDS = {
    "это",
    "как",
    "или",
    "для",
    "что",
    "чтобы",
    "при",
    "без",
    "так",
    "то",
    "же",
    "не",
    "нет",
    "да",
    "по",
    "на",
    "все",
    "всё",
    "про",
    "из",
    "мы",
    "вы",
    "он",
    "она",
    "они",
    "есть",
    "будет",
    "нужно",
}


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _clean_text(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    """Deterministic chunking by characters (works for RU/EN, markdown, etc.)."""

    src = _clean_text(text)
    if not src:
        return []

    src = re.sub(r"[ \t]+\n", "\n", src)
    src = re.sub(r"\n{3,}", "\n\n", src)

    chunks: list[str] = []
    i = 0
    n = len(src)
    size = max(200, int(chunk_size))
    ov = max(0, min(int(overlap), size // 2))
    while i < n:
        end = min(n, i + size)
        chunk = src[i:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        i = max(0, end - ov)
    return chunks


def extract_query_tokens(text: str, *, max_terms: int = 10) -> list[str]:
    raw = (text or "").lower()
    words = [w for w in _WORD_RE.findall(raw) if len(w) >= 4]
    terms: list[str] = []
    for w in words:
        if w.isdigit():
            continue
        if w in _STOPWORDS:
            continue
        if w not in terms:
            terms.append(w)
        if len(terms) >= max_terms:
            break
    return terms


async def reindex_document(document_id: int) -> int:
    """(Re)create chunks for a document. Returns chunks total."""

    async with async_session() as session:
        doc = await session.get(KnowledgeBaseDocument, document_id)
        if doc is None:
            return 0

        await session.execute(delete(KnowledgeBaseChunk).where(KnowledgeBaseChunk.document_id == doc.id))

        chunks = chunk_text(doc.content_text or "")
        now = datetime.now(timezone.utc)
        for idx, chunk in enumerate(chunks):
            session.add(
                KnowledgeBaseChunk(
                    document_id=int(doc.id),
                    chunk_index=int(idx),
                    content_text=chunk,
                    content_hash=_sha256(chunk),
                    created_at=now,
                )
            )

        # Touch updated_at so AI caches invalidate even if only chunks change.
        doc.updated_at = now
        await session.commit()
        return len(chunks)


async def _candidate_chunks_for_terms(terms: list[str], *, limit: int) -> list[KnowledgeBaseChunk]:
    if not terms:
        return []

    clauses = []
    for t in terms[:10]:
        pat = f"%{t}%"
        clauses.append(func.lower(KnowledgeBaseChunk.content_text).like(pat))

    async with async_session() as session:
        rows = (
            await session.execute(
                select(KnowledgeBaseChunk)
                .join(KnowledgeBaseDocument, KnowledgeBaseChunk.document_id == KnowledgeBaseDocument.id)
                .where(
                    KnowledgeBaseDocument.is_active.is_(True),
                    or_(*clauses),
                )
                .limit(int(limit))
            )
        ).scalars().all()
        return list(rows)


def _rank_chunks(chunks: Iterable[KnowledgeBaseChunk], terms: list[str]) -> list[KnowledgeBaseChunk]:
    terms_lc = [t.lower() for t in terms if t]

    def score(ch: KnowledgeBaseChunk) -> tuple[int, int]:
        txt = (ch.content_text or "").lower()
        hits = sum(1 for t in terms_lc if t in txt)
        return (hits, -len(txt))

    ranked = sorted(chunks, key=score, reverse=True)
    return ranked


async def search_excerpts(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return top KB excerpts for a query (anonymized; no PII expected)."""

    terms = extract_query_tokens(query, max_terms=10)
    # Fetch a bit more for ranking stability.
    candidates = await _candidate_chunks_for_terms(terms, limit=max(20, limit * 6))
    ranked = _rank_chunks(candidates, terms)

    # Fetch titles for returned docs.
    doc_ids = {int(ch.document_id) for ch in ranked[:limit]}
    titles: dict[int, str] = {}
    if doc_ids:
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(KnowledgeBaseDocument.id, KnowledgeBaseDocument.title).where(
                        KnowledgeBaseDocument.id.in_(doc_ids)
                    )
                )
            ).all()
            titles = {int(i): str(t or "") for (i, t) in rows}

    results: list[dict[str, Any]] = []
    for ch in ranked[:limit]:
        text = (ch.content_text or "").strip()
        if len(text) > 700:
            text = text[:700].rstrip() + "…"
        results.append(
            {
                "document_id": int(ch.document_id),
                "document_title": titles.get(int(ch.document_id), ""),
                "chunk_index": int(ch.chunk_index),
                "excerpt": text,
            }
        )
    return results


async def kb_state_snapshot() -> dict[str, Any]:
    async with async_session() as session:
        total = await session.scalar(
            select(func.count(KnowledgeBaseDocument.id)).where(KnowledgeBaseDocument.is_active.is_(True))
        )
        last = await session.scalar(
            select(func.max(KnowledgeBaseDocument.updated_at)).where(KnowledgeBaseDocument.is_active.is_(True))
        )
        last_iso: Optional[str] = None
        if last is not None:
            try:
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                last_iso = last.astimezone(timezone.utc).isoformat()
            except Exception:
                last_iso = None
    return {"active_documents_total": int(total or 0), "last_updated_at": last_iso}

