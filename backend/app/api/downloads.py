"""Document downloads.

Download links appear in places without workspace context (the activity feed,
notification emails, the recent-files widget), so they use a short, stable URL
keyed by document ID."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import Document, User
from .deps import current_user
from .documents import storage_dir

router = APIRouter(prefix="/api/v1/documents", tags=["downloads"])


@router.get("/{document_id}/content")
def download_document(document_id: uuid.UUID, request: Request, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> FileResponse:
    d = db.scalar(select(Document).where(Document.id == document_id))
    if d is None:
        raise HTTPException(404, "not_found")
    path = storage_dir(request) / d.id.hex
    if not path.is_file():
        raise HTTPException(404, "not_found")
    ascii_name = d.title.encode("ascii", "replace").decode().replace('"', "_")
    return FileResponse(
        path,
        media_type=d.content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(d.title)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )
