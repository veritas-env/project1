"""Business activity feed. Written in the same transaction as the change it describes,
so a rolled-back change leaves no activity entry behind."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..models import Activity


def log(db: Session, workspace_id: uuid.UUID, actor_id: uuid.UUID | None, verb: str, object_type: str,
        object_id: uuid.UUID | None, summary: str) -> None:
    db.add(Activity(workspace_id=workspace_id, actor_id=actor_id, verb=verb, object_type=object_type,
                    object_id=object_id, summary=summary[:300]))


def link_for(workspace_id: uuid.UUID, object_type: str, object_id: uuid.UUID | None, project_id: uuid.UUID | None = None) -> str | None:
    """Where the activity feed should point for an entry."""
    if object_id is None:
        return None
    ws = f"/workspaces/{workspace_id}"
    if object_type == "project":
        return f"{ws}/projects/{object_id}"
    if object_type == "document":
        return f"/api/v1/documents/{object_id}/content"
    if object_type in ("task", "milestone") and project_id:
        return f"{ws}/projects/{project_id}"
    if object_type in ("member", "invitation"):
        return f"{ws}/members"
    return None
