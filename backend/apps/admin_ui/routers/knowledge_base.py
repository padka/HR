from __future__ import annotations

import zipfile
from io import BytesIO
from datetime import timezone
from typing import Any, Optional
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from backend.apps.admin_ui.security import Principal, require_admin, require_csrf_token, require_principal
from backend.core.ai.knowledge_base import reindex_document
from backend.core.db import async_session
from backend.domain.ai.models import KnowledgeBaseChunk, KnowledgeBaseDocument


router = APIRouter(prefix="/api/kb", tags=["kb"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _iso(dt) -> Optional[str]:
    if not dt:
        return None
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            xml_bytes = zf.read("word/document.xml")
    except Exception:
        return ""

    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return ""

    paras: list[str] = []
    for p in root.iter():
        if not str(p.tag).endswith("}p"):
            continue
        parts: list[str] = []
        for t in p.iter():
            if str(t.tag).endswith("}t") and t.text:
                parts.append(str(t.text))
        line = "".join(parts).strip()
        if line:
            paras.append(line)
    return "\n".join(paras).strip()


def _extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF. Uses PyMuPDF (fitz) if available, otherwise returns empty."""
    # Preferred: pypdf (pure-python, lightweight)
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]

        reader = PdfReader(BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text and text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages).strip()
    except ImportError:
        pass
    except Exception:
        return ""

    try:
        import fitz  # PyMuPDF  # type: ignore[import-untyped]

        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            text = page.get_text("text")
            if text and text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages).strip()
    except ImportError:
        pass
    except Exception:
        return ""
    # Fallback: try pdfplumber
    try:
        import pdfplumber  # type: ignore[import-untyped]

        with pdfplumber.open(BytesIO(data)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
            return "\n\n".join(pages).strip()
    except ImportError:
        pass
    except Exception:
        pass
    return ""


def _decode_upload_to_text(*, data: bytes, filename: str, mime_type: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".docx") or (mime_type or "").lower() == _DOCX_MIME:
        extracted = _extract_docx_text(data)
        return extracted
    if name.endswith(".pdf") or (mime_type or "").lower() == "application/pdf":
        return _extract_pdf_text(data)
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("utf-8", errors="replace")


@router.get("/documents")
async def api_kb_documents_list(
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = principal
    async with async_session() as session:
        rows = await session.execute(
            select(
                KnowledgeBaseDocument.id,
                KnowledgeBaseDocument.title,
                KnowledgeBaseDocument.filename,
                KnowledgeBaseDocument.mime_type,
                KnowledgeBaseDocument.is_active,
                KnowledgeBaseDocument.created_at,
                KnowledgeBaseDocument.updated_at,
                func.count(KnowledgeBaseChunk.id).label("chunks_total"),
            )
            .outerjoin(KnowledgeBaseChunk, KnowledgeBaseChunk.document_id == KnowledgeBaseDocument.id)
            .group_by(
                KnowledgeBaseDocument.id,
                KnowledgeBaseDocument.title,
                KnowledgeBaseDocument.filename,
                KnowledgeBaseDocument.mime_type,
                KnowledgeBaseDocument.is_active,
                KnowledgeBaseDocument.created_at,
                KnowledgeBaseDocument.updated_at,
            )
            .order_by(KnowledgeBaseDocument.updated_at.desc(), KnowledgeBaseDocument.id.desc())
        )
        items = []
        for row in rows.fetchall():
            items.append(
                {
                    "id": int(row.id),
                    "title": row.title or "",
                    "filename": row.filename or "",
                    "mime_type": row.mime_type or "",
                    "is_active": bool(row.is_active),
                    "created_at": _iso(row.created_at),
                    "updated_at": _iso(row.updated_at),
                    "chunks_total": int(row.chunks_total or 0),
                }
            )
    return JSONResponse({"ok": True, "items": items})


@router.get("/documents/{document_id}")
async def api_kb_document_get(
    document_id: int,
    principal: Principal = Depends(require_principal),
) -> JSONResponse:
    _ = principal
    async with async_session() as session:
        doc = await session.get(KnowledgeBaseDocument, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail={"message": "Документ не найден"})
        chunks_total = int(
            await session.scalar(
                select(func.count(KnowledgeBaseChunk.id)).where(KnowledgeBaseChunk.document_id == doc.id)
            )
            or 0
        )
        payload = {
            "id": int(doc.id),
            "title": doc.title or "",
            "filename": doc.filename or "",
            "mime_type": doc.mime_type or "",
            "is_active": bool(doc.is_active),
            "created_at": _iso(doc.created_at),
            "updated_at": _iso(doc.updated_at),
            "chunks_total": chunks_total,
            "content_text": doc.content_text or "",
        }
    return JSONResponse({"ok": True, "document": payload})


@router.post("/documents")
async def api_kb_document_create(
    request: Request,
    principal: Principal = Depends(require_admin),
) -> JSONResponse:
    _ = await require_csrf_token(request)

    content_type = (request.headers.get("content-type") or "").lower()
    title = ""
    filename = ""
    mime_type = ""
    content_text = ""

    if "multipart/form-data" in content_type:
        form = await request.form()
        up = form.get("file")
        title = str(form.get("title") or "").strip()
        if up is None:
            raise HTTPException(status_code=400, detail={"message": "Файл не передан"})
        try:
            data = await up.read()
            filename = str(getattr(up, "filename", "") or "")
            mime_type = str(getattr(up, "content_type", "") or "")
        except Exception as exc:
            raise HTTPException(status_code=400, detail={"message": "Не удалось прочитать файл"}) from exc
        if data is None:
            raise HTTPException(status_code=400, detail={"message": "Файл пустой"})
        if len(data) > 6_000_000:
            raise HTTPException(status_code=400, detail={"message": "Файл слишком большой (лимит 6MB)"})
        content_text = _decode_upload_to_text(data=data, filename=filename, mime_type=mime_type)
        if not content_text.strip():
            raise HTTPException(
                status_code=400,
                detail={"message": "Не удалось извлечь текст из файла. Поддерживаются .txt/.md/.docx/.pdf."},
            )
        if not title:
            title = filename or "Документ"
    else:
        data = await request.json()
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})
        title = str(data.get("title") or "").strip()
        filename = str(data.get("filename") or "").strip()
        mime_type = str(data.get("mime_type") or "").strip()
        content_text = str(data.get("content_text") or "").strip()

    if not title:
        raise HTTPException(status_code=400, detail={"message": "Укажите заголовок"})
    if not content_text:
        raise HTTPException(status_code=400, detail={"message": "Текст документа пустой"})

    async with async_session() as session:
        doc = KnowledgeBaseDocument(
            title=title,
            filename=filename,
            mime_type=mime_type,
            content_text=content_text,
            is_active=True,
            created_by_type=principal.type,
            created_by_id=principal.id,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = int(doc.id)

    chunks_total = await reindex_document(doc_id)
    return JSONResponse({"ok": True, "document_id": doc_id, "chunks_total": int(chunks_total)})


@router.put("/documents/{document_id}")
async def api_kb_document_update(
    document_id: int,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> JSONResponse:
    _ = principal
    _ = await require_csrf_token(request)

    data = await request.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail={"message": "Ожидался JSON"})

    async with async_session() as session:
        doc = await session.get(KnowledgeBaseDocument, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail={"message": "Документ не найден"})

        content_changed = False
        if data.get("title") is not None:
            doc.title = str(data.get("title") or "").strip()
        if data.get("is_active") is not None:
            doc.is_active = bool(data.get("is_active"))
        if data.get("content_text") is not None:
            next_text = str(data.get("content_text") or "")
            if next_text != (doc.content_text or ""):
                doc.content_text = next_text
                content_changed = True
        await session.commit()

    chunks_total = None
    if content_changed:
        chunks_total = await reindex_document(document_id)
    return JSONResponse({"ok": True, "document_id": int(document_id), "chunks_total": chunks_total})


@router.delete("/documents/{document_id}")
async def api_kb_document_delete(
    document_id: int,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> JSONResponse:
    _ = principal
    _ = await require_csrf_token(request)

    async with async_session() as session:
        doc = await session.get(KnowledgeBaseDocument, document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail={"message": "Документ не найден"})
        doc.is_active = False
        await session.commit()
    return JSONResponse({"ok": True})


@router.post("/documents/{document_id}/reindex")
async def api_kb_document_reindex(
    document_id: int,
    request: Request,
    principal: Principal = Depends(require_admin),
) -> JSONResponse:
    _ = principal
    _ = await require_csrf_token(request)
    chunks_total = await reindex_document(document_id)
    return JSONResponse({"ok": True, "document_id": int(document_id), "chunks_total": int(chunks_total)})
