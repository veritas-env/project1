"""Projects and their milestones."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import Milestone, Project, Task
from ..schemas import MilestoneIn, MilestoneOut, MilestoneUpdate, ProjectIn, ProjectOut, ProjectUpdate
from ..services import activity
from .common import load, require_member
from .deps import WorkspaceContext, workspace_access

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["projects"])


def _counts(db: Session, column, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not ids:
        return {}
    rows = db.execute(
        select(column, func.count().filter(Task.status != "done"), func.count().filter(Task.status == "done"))
        .where(column.in_(ids)).group_by(column)
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def _project_out(p: Project, counts: dict) -> ProjectOut:
    open_, done = counts.get(p.id, (0, 0))
    return ProjectOut(id=p.id, key=p.key, name=p.name, description=p.description, status=p.status, lead_id=p.lead_id,
                      start_date=p.start_date, target_date=p.target_date, open_tasks=open_, done_tasks=done,
                      created_at=p.created_at, updated_at=p.updated_at)


def _milestone_out(m: Milestone, counts: dict) -> MilestoneOut:
    open_, done = counts.get(m.id, (0, 0))
    return MilestoneOut(id=m.id, project_id=m.project_id, name=m.name, description=m.description,
                        due_date=m.due_date, status=m.status, open_tasks=open_, done_tasks=done)


# --- projects -------------------------------------------------------------------

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db),
                  include_archived: bool = False) -> list[ProjectOut]:
    stmt = select(Project).where(Project.workspace_id == ctx.workspace.id)
    if not include_archived:
        stmt = stmt.where(Project.status != "archived")
    order = case({"active": 0, "on_hold": 1, "completed": 2, "archived": 3}, value=Project.status)
    projects = list(db.scalars(stmt.order_by(order, Project.name)))
    counts = _counts(db, Task.project_id, [p.id for p in projects])
    return [_project_out(p, counts) for p in projects]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                   db: Session = Depends(get_db)) -> ProjectOut:
    require_member(db, ctx.workspace.id, body.lead_id, "lead_id")
    p = Project(workspace_id=ctx.workspace.id, created_by=ctx.user.id, **body.model_dump())
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "project_key_taken") from None
    activity.log(db, ctx.workspace.id, ctx.user.id, "created", "project", p.id, f"created project {p.key} · {p.name}")
    db.commit()
    db.refresh(p)
    return _project_out(p, {})


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("viewer")),
                db: Session = Depends(get_db)) -> ProjectOut:
    p = load(db, Project, ctx.workspace.id, project_id)
    return _project_out(p, _counts(db, Task.project_id, [p.id]))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: uuid.UUID, body: ProjectUpdate, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                   db: Session = Depends(get_db)) -> ProjectOut:
    p = load(db, Project, ctx.workspace.id, project_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if "lead_id" in changes:
        require_member(db, ctx.workspace.id, changes["lead_id"], "lead_id")
    for k, v in changes.items():
        setattr(p, k, v)
    if p.start_date and p.target_date and p.target_date < p.start_date:
        raise HTTPException(422, {"error": "validation_error", "fields": [{"loc": ["body", "target_date"], "msg": "before start_date"}]})
    if changes:
        what = f"changed status to {changes['status']}" if "status" in changes else "updated"
        activity.log(db, ctx.workspace.id, ctx.user.id, "updated", "project", p.id, f"{what} project {p.key}")
    db.commit()
    db.refresh(p)
    return _project_out(p, _counts(db, Task.project_id, [p.id]))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("owner")),
                   db: Session = Depends(get_db)) -> Response:
    p = load(db, Project, ctx.workspace.id, project_id, lock=True)
    activity.log(db, ctx.workspace.id, ctx.user.id, "deleted", "project", None, f"deleted project {p.key} · {p.name}")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# --- milestones -----------------------------------------------------------------

@router.get("/projects/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(project_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("viewer")),
                    db: Session = Depends(get_db)) -> list[MilestoneOut]:
    p = load(db, Project, ctx.workspace.id, project_id)
    ms = list(db.scalars(select(Milestone).where(Milestone.project_id == p.id)
                         .order_by(Milestone.due_date.asc().nulls_last(), Milestone.name)))
    counts = _counts(db, Task.milestone_id, [m.id for m in ms])
    return [_milestone_out(m, counts) for m in ms]


@router.post("/projects/{project_id}/milestones", response_model=MilestoneOut, status_code=201)
def create_milestone(project_id: uuid.UUID, body: MilestoneIn, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                     db: Session = Depends(get_db)) -> MilestoneOut:
    p = load(db, Project, ctx.workspace.id, project_id)
    m = Milestone(workspace_id=ctx.workspace.id, project_id=p.id, **body.model_dump())
    db.add(m)
    db.flush()
    activity.log(db, ctx.workspace.id, ctx.user.id, "created", "milestone", m.id, f"added milestone “{m.name}” to {p.key}")
    db.commit()
    return _milestone_out(m, {})


@router.patch("/milestones/{milestone_id}", response_model=MilestoneOut)
def update_milestone(milestone_id: uuid.UUID, body: MilestoneUpdate, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                     db: Session = Depends(get_db)) -> MilestoneOut:
    m = load(db, Milestone, ctx.workspace.id, milestone_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(m, k, v)
    if changes.get("status") == "closed":
        activity.log(db, ctx.workspace.id, ctx.user.id, "closed", "milestone", m.id, f"closed milestone “{m.name}”")
    db.commit()
    return _milestone_out(m, _counts(db, Task.milestone_id, [m.id]))


@router.delete("/milestones/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: uuid.UUID, ctx: WorkspaceContext = Depends(workspace_access("manager")),
                     db: Session = Depends(get_db)) -> Response:
    m = load(db, Milestone, ctx.workspace.id, milestone_id, lock=True)
    db.delete(m)
    db.commit()
    return Response(status_code=204)
