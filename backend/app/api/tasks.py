"""Tasks. Members create tasks and edit the ones they created or are assigned to;
managers and owners edit or delete any task."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import ROLE_RANK, Project, Task
from ..schemas import TaskIn, TaskOut, TaskPriority, TaskStatus, TaskUpdate
from ..services import activity
from .common import load, require_member, require_milestone
from .deps import WorkspaceContext, workspace_access

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["tasks"])

SORT = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "due_date": Task.due_date,
    "priority": Task.priority,
    "number": Task.number,
}
PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


def task_out(t: Task, project_key: str) -> TaskOut:
    return TaskOut(id=t.id, project_id=t.project_id, ref=f"{project_key}-{t.number}", title=t.title,
                   description=t.description, status=t.status, priority=t.priority, assignee_id=t.assignee_id,
                   milestone_id=t.milestone_id, due_date=t.due_date, created_by=t.created_by,
                   created_at=t.created_at, updated_at=t.updated_at)


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(
    project_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(workspace_access("viewer")),
    db: Session = Depends(get_db),
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee: Literal["me", "none"] | uuid.UUID | None = None,
    milestone_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=100),
    sort: Literal["created_at", "updated_at", "due_date", "priority", "number"] = "number",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[TaskOut]:
    p = load(db, Project, ctx.workspace.id, project_id)
    stmt = select(Task).where(Task.workspace_id == ctx.workspace.id, Task.project_id == p.id)
    if status:
        stmt = stmt.where(Task.status == status)
    if priority:
        stmt = stmt.where(Task.priority == priority)
    if assignee == "me":
        stmt = stmt.where(Task.assignee_id == ctx.user.id)
    elif assignee == "none":
        stmt = stmt.where(Task.assignee_id.is_(None))
    elif assignee is not None:
        stmt = stmt.where(Task.assignee_id == assignee)
    if milestone_id:
        stmt = stmt.where(Task.milestone_id == milestone_id)
    if q:
        stmt = stmt.where(Task.title.ilike(f"%{_escape_like(q)}%", escape="\\"))
    col = SORT[sort]
    stmt = stmt.order_by(col.asc().nulls_last() if order == "asc" else col.desc().nulls_last(), Task.number).limit(limit)
    return [task_out(t, p.key) for t in db.scalars(stmt)]


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(project_id: uuid.UUID, body: TaskIn, ctx: WorkspaceContext = Depends(workspace_access("member")),
                db: Session = Depends(get_db)) -> TaskOut:
    p = load(db, Project, ctx.workspace.id, project_id, lock=True)  # lock: serialises task numbering
    if p.status == "archived":
        raise HTTPException(409, "project_archived")
    require_member(db, ctx.workspace.id, body.assignee_id, "assignee_id")
    require_milestone(db, p, body.milestone_id)
    number = (db.scalar(select(func.max(Task.number)).where(Task.project_id == p.id)) or 0) + 1
    t = Task(workspace_id=ctx.workspace.id, project_id=p.id, number=number, created_by=ctx.user.id, **body.model_dump())
    db.add(t)
    db.flush()
    activity.log(db, ctx.workspace.id, ctx.user.id, "created", "task", t.id, f"created {p.key}-{number} “{t.title}”")
    db.commit()
    db.refresh(t)
    return task_out(t, p.key)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("viewer")),
             db: Session = Depends(get_db)) -> TaskOut:
    t = load(db, Task, ctx.workspace.id, task_id)
    return task_out(t, db.get(Project, t.project_id).key)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, body: TaskUpdate, ctx: WorkspaceContext = Depends(workspace_access("member")),
                db: Session = Depends(get_db)) -> TaskOut:
    t = load(db, Task, ctx.workspace.id, task_id, lock=True)
    if ROLE_RANK[ctx.role] < ROLE_RANK["manager"] and ctx.user.id not in (t.created_by, t.assignee_id):
        raise HTTPException(403, "forbidden")
    p = db.get(Project, t.project_id)
    changes = body.model_dump(exclude_unset=True)
    if "assignee_id" in changes:
        require_member(db, ctx.workspace.id, changes["assignee_id"], "assignee_id")
    if "milestone_id" in changes:
        require_milestone(db, p, changes["milestone_id"])
    old_status = t.status
    for k, v in changes.items():
        setattr(t, k, v)
    if "status" in changes and changes["status"] != old_status:
        activity.log(db, ctx.workspace.id, ctx.user.id, "moved", "task", t.id,
                     f"moved {p.key}-{t.number} from {old_status.replace('_', ' ')} to {t.status.replace('_', ' ')}")
    elif changes:
        activity.log(db, ctx.workspace.id, ctx.user.id, "updated", "task", t.id, f"updated {p.key}-{t.number}")
    db.commit()
    db.refresh(t)
    return task_out(t, p.key)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                db: Session = Depends(get_db)) -> Response:
    t = load(db, Task, ctx.workspace.id, task_id, lock=True)
    p = db.get(Project, t.project_id)
    activity.log(db, ctx.workspace.id, ctx.user.id, "deleted", "task", None, f"deleted {p.key}-{t.number} “{t.title}”")
    db.delete(t)
    db.commit()
    return Response(status_code=204)
