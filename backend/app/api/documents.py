"""Workspace document library: upload, list, details, delete.

Files are stored under a random UUID with no extension; the title is display-only.
Type is decided by content sniffing against an allow-list; size is enforced while
streaming; the SHA-256 is computed by the server."""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import DOCUMENT_CATEGORIES, Document, Project
from ..schemas import DocumentOut
from ..services import activity, audit
from .common import load
from .deps import WorkspaceContext, workspace_access

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}/documents", tags=["documents"])

CHUNK = 64 * 1024


def sniff(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if b"\x00" not in head:
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            if e.start < len(head) - 4:  # a multibyte char cut at the window edge is fine
                return None
        return "text/plain"
    return None


def safe_title(name: str | None) -> str:
    name = unicodedata.normalize("NFKC", name or "document")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().lstrip(".")
    return name[:200] or "document"


def storage_dir(request: Request) -> Path:
    p = Path(request.app.state.settings.upload_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def document_out(d: Document) -> DocumentOut:
    return DocumentOut(id=d.id, title=d.title, category=d.category, project_id=d.project_id, content_type=d.content_type,
                       size=d.size, sha256=d.sha256, uploader_id=d.uploader_id, created_at=d.created_at,
                       download_url=f"/api/v1/documents/{d.id}/content")


@router.get("", response_model=list[DocumentOut])
def list_documents(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db),
                   project_id: uuid.UUID | None = None) -> list[DocumentOut]:
    stmt = select(Document).where(Document.workspace_id == ctx.workspace.id)
    if project_id:
        stmt = stmt.where(Document.project_id == project_id)
    return [document_out(d) for d in db.scalars(stmt.order_by(Document.created_at.desc()))]


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(default="general", max_length=32),
    project_id: uuid.UUID | None = Form(default=None),
    ctx: WorkspaceContext = Depends(workspace_access("member")),
    db: Session = Depends(get_db),
) -> DocumentOut:
    if category not in DOCUMENT_CATEGORIES:
        raise HTTPException(422, {"error": "validation_error", "fields": [{"loc": ["body", "category"], "msg": "unknown category"}]})
    if project_id is not None:
        load(db, Project, ctx.workspace.id, project_id)
    limit = request.app.state.settings.max_upload_bytes
    doc_id = uuid.uuid4()
    dest = storage_dir(request) / doc_id.hex
    digest, size, head = hashlib.sha256(), 0, b""
    try:
        with open(dest, "xb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, "file_too_large")
                if len(head) < 512:
                    head += chunk[: 512 - len(head)]
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "empty_file")
        ctype = sniff(head)
        if ctype is None:
            audit.record(request, "file.rejected", actor=ctx.user.id, workspace_id=ctx.workspace.id, severity="low",
                         detail={"reason": "type_not_allowed", "size": size})
            raise HTTPException(415, "file_type_not_allowed")
        d = Document(id=doc_id, workspace_id=ctx.workspace.id, project_id=project_id, uploader_id=ctx.user.id,
                     title=safe_title(file.filename), category=category, content_type=ctype, size=size,
                     sha256=digest.hexdigest())
        db.add(d)
        activity.log(db, ctx.workspace.id, ctx.user.id, "uploaded", "document", d.id, f"uploaded “{d.title}”")
        db.commit()
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    db.refresh(d)
    return document_out(d)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("viewer")),
                 db: Session = Depends(get_db)) -> DocumentOut:
    return document_out(load(db, Document, ctx.workspace.id, document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, request: Request, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                    db: Session = Depends(get_db)) -> Response:
    d = load(db, Document, ctx.workspace.id, document_id, lock=True)
    path = storage_dir(request) / d.id.hex
    activity.log(db, ctx.workspace.id, ctx.user.id, "deleted", "document", None, f"deleted “{d.title}”")
    db.delete(d)
    db.commit()
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    return Response(status_code=204)
