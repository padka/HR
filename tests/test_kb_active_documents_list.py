from __future__ import annotations

import pytest
from backend.core.ai.knowledge_base import list_active_documents, reindex_document
from backend.core.db import async_session
from backend.domain.ai.models import KnowledgeBaseDocument


@pytest.mark.asyncio
async def test_list_active_documents_returns_recent_titles():
    async with async_session() as session:
        doc = KnowledgeBaseDocument(
            title="Регламент тестовый",
            filename="reg.md",
            mime_type="text/markdown",
            content_text="Критерии оценки кандидатов: опыт в клиентском обслуживании.",
            is_active=True,
            created_by_type="admin",
            created_by_id=-1,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = int(doc.id)

    _ = await reindex_document(doc_id)
    docs = await list_active_documents(limit=10)
    assert any(int(d.get("id") or 0) == doc_id and (d.get("title") or "") == "Регламент тестовый" for d in docs)

