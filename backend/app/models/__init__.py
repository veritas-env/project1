"""ProjectFlow data model. Every workspace-owned table carries workspace_id, and every
query for workspace data filters on it."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES = ("viewer", "member", "manager", "owner")
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}
TASK_STATUSES = ("todo", "in_progress", "review", "done")
TASK_PRIORITIES = ("low", "medium", "high", "urgent")
PROJECT_STATUSES = ("active", "on_hold", "completed", "archived")
MILESTONE_STATUSES = ("open", "closed")
DOCUMENT_CATEGORIES = ("general", "specification", "contract", "report", "meeting_notes", "design")


class Base(DeclarativeBase):
    pass


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _in(col: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(f"{col} IN ({', '.join(repr(v) for v in values)})", name=name)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid()
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    __table_args__ = (CheckConstraint("email = lower(email)", name="users_email_lowercase"),)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = _uuid()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = _now()


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _now()
    __table_args__ = (_in("role", ROLES, "memberships_role_valid"), Index("ix_memberships_user", "user_id"))


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = _uuid()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()
    __table_args__ = (
        _in("role", ("viewer", "member", "manager"), "invitations_role_valid"),
        CheckConstraint("email = lower(email)", name="invitations_email_lowercase"),
        Index("ix_invitations_workspace", "workspace_id"),
    )


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = _uuid()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        _in("status", PROJECT_STATUSES, "projects_status_valid"),
        Index("ix_projects_workspace", "workspace_id"),
        Index("uq_projects_workspace_key", "workspace_id", "key", unique=True),
    )


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[uuid.UUID] = _uuid()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = _now()
    __table_args__ = (_in("status", MILESTONE_STATUSES, "milestones_status_valid"), Index("ix_milestones_project", "project_id"))


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = _uuid()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("milestones.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (
        _in("status", TASK_STATUSES, "tasks_status_valid"),
        _in("priority", TASK_PRIORITIES, "tasks_priority_valid"),
        Index("ix_tasks_workspace", "workspace_id"),
        Index("ix_tasks_project", "project_id"),
        Index("uq_tasks_project_number", "project_id", "number", unique=True),
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = _uuid()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _now()
    __table_args__ = (_in("category", DOCUMENT_CATEGORIES, "documents_category_valid"), Index("ix_documents_workspace", "workspace_id"))


class Activity(Base):
    """Business activity feed shown to workspace members (separate from security_events)."""

    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _now()
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verb: Mapped[str] = mapped_column(String(32), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[uuid.UUID | None] = mapped_column()
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    __table_args__ = (Index("ix_activity_workspace_at", "workspace_id", "at"),)


class SecurityEvent(Base):
    """Append-only. A database trigger rejects UPDATE and DELETE (see migration)."""

    __tablename__ = "security_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _now()
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column()
    workspace_id: Mapped[uuid.UUID | None] = mapped_column()
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    __table_args__ = (Index("ix_security_events_type_at", "type", "at"),)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _now()
    rule: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("security_events.id"))
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('open','acknowledged')", name="alerts_status_valid"),)
