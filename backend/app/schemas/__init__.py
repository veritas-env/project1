"""Request and response bodies. Every input is length- and format-bounded and
unknown fields are rejected."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,189}\.[A-Za-z]{2,24}$")

Role = Literal["viewer", "member", "manager", "owner"]
InviteRole = Literal["viewer", "member", "manager"]
TaskStatus = Literal["todo", "in_progress", "review", "done"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
ProjectStatus = Literal["active", "on_hold", "completed", "archived"]
MilestoneStatus = Literal["open", "closed"]
DocumentCategory = Literal["general", "specification", "contract", "report", "meeting_notes", "design"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def normalize_email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v):
        raise ValueError("invalid email address")
    return v


# --- auth -----------------------------------------------------------------------

class LoginIn(StrictModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class PasswordChangeIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_platform_admin: bool


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


# --- workspaces, members, invitations ------------------------------------------

class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    role: str


class MemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    job_title: str | None
    role: str
    joined_at: datetime


class RoleIn(StrictModel):
    role: Role


class InvitationIn(StrictModel):
    email: str = Field(max_length=254)
    role: InviteRole = "member"

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return normalize_email(v)


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InvitationCreated(InvitationOut):
    invite_url: str  # shown once to the inviter; the token isn't stored in clear


class InvitationPreview(BaseModel):
    workspace_name: str
    email: str
    role: str
    account_exists: bool


class InvitationTokenIn(StrictModel):
    token: str = Field(min_length=20, max_length=100)


class InvitationRegisterIn(InvitationTokenIn):
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


# --- projects, milestones, tasks ------------------------------------------------

class ProjectIn(StrictModel):
    key: str = Field(min_length=2, max_length=8, pattern=r"^[A-Z][A-Z0-9]{1,7}$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=5000)
    lead_id: uuid.UUID | None = None
    start_date: date | None = None
    target_date: date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("target_date must not be before start_date")
        return self


class ProjectUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None
    lead_id: uuid.UUID | None = None
    start_date: date | None = None
    target_date: date | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    status: str
    lead_id: uuid.UUID | None
    start_date: date | None
    target_date: date | None
    open_tasks: int = 0
    done_tasks: int = 0
    created_at: datetime
    updated_at: datetime


class MilestoneIn(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    due_date: date | None = None


class MilestoneUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    status: MilestoneStatus | None = None


class MilestoneOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str
    due_date: date | None
    status: str
    open_tasks: int = 0
    done_tasks: int = 0


class TaskIn(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    assignee_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    ref: str
    title: str
    description: str
    status: str
    priority: str
    assignee_id: uuid.UUID | None
    milestone_id: uuid.UUID | None
    due_date: date | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# --- documents, activity, dashboard ----------------------------------------------

class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    project_id: uuid.UUID | None
    content_type: str
    size: int
    sha256: str
    uploader_id: uuid.UUID | None
    created_at: datetime
    download_url: str


class ActivityOut(BaseModel):
    id: int
    at: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None
    verb: str
    object_type: str
    object_id: uuid.UUID | None
    summary: str
    link: str | None


class DashboardOut(BaseModel):
    projects_active: int
    tasks_by_status: dict[str, int]
    overdue_tasks: int
    my_open_tasks: list[TaskOut]
    upcoming_milestones: list[MilestoneOut]
    recent_activity: list[ActivityOut]


# --- platform admin -------------------------------------------------------------

class EventOut(BaseModel):
    id: int
    at: datetime
    type: str
    severity: str
    actor_user_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    ip: str | None
    request_id: str | None
    detail: dict


class AlertOut(BaseModel):
    id: int
    at: datetime
    rule: str
    severity: str
    summary: str
    event_id: int | None
    status: str
