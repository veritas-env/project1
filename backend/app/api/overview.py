"""Workspace dashboard and activity feed."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..models import TASK_STATUSES, Activity, Milestone, Project, Task, User
from ..schemas import ActivityOut, DashboardOut, MilestoneOut
from ..services.activity import link_for
from .deps import WorkspaceContext, workspace_access
from .tasks import task_out

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["overview"])


def _activity(db: Session, workspace_id, limit: int, before: int | None = None) -> list[ActivityOut]:
    stmt = (select(Activity, User.display_name)
            .outerjoin(User, User.id == Activity.actor_id)
            .where(Activity.workspace_id == workspace_id))
    if before:
        stmt = stmt.where(Activity.id < before)
    rows = db.execute(stmt.order_by(Activity.id.desc()).limit(limit)).all()
    # Task/milestone links need their project; look them up in one query.
    ids = [a.object_id for a, _ in rows if a.object_type in ("task", "milestone") and a.object_id]
    project_of = dict(db.execute(select(Task.id, Task.project_id).where(Task.id.in_(ids))).all()) if ids else {}
    if ids:
        project_of.update(dict(db.execute(select(Milestone.id, Milestone.project_id).where(Milestone.id.in_(ids))).all()))
    return [ActivityOut(id=a.id, at=a.at, actor_id=a.actor_id, actor_name=name, verb=a.verb, object_type=a.object_type,
                        object_id=a.object_id, summary=a.summary,
                        link=link_for(workspace_id, a.object_type, a.object_id, project_of.get(a.object_id)))
            for a, name in rows]


@router.get("/activity", response_model=list[ActivityOut])
def activity_feed(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db),
                  limit: int = Query(default=50, ge=1, le=200), before: int | None = Query(default=None, ge=1)) -> list[ActivityOut]:
    return _activity(db, ctx.workspace.id, limit, before)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(ctx: WorkspaceContext = Depends(workspace_access("viewer")), db: Session = Depends(get_db)) -> DashboardOut:
    ws = ctx.workspace.id
    today = date.today()
    active = db.scalar(select(func.count()).select_from(Project).where(Project.workspace_id == ws, Project.status == "active"))
    by_status = dict.fromkeys(TASK_STATUSES, 0)
    by_status.update(dict(db.execute(select(Task.status, func.count()).where(Task.workspace_id == ws).group_by(Task.status)).all()))
    overdue = db.scalar(select(func.count()).select_from(Task).where(
        Task.workspace_id == ws, Task.status != "done", Task.due_date < today))
    mine = db.execute(
        select(Task, Project.key).join(Project, Project.id == Task.project_id)
        .where(Task.workspace_id == ws, Task.assignee_id == ctx.user.id, Task.status != "done")
        .order_by(Task.due_date.asc().nulls_last(), Task.number).limit(10)
    ).all()
    upcoming = db.scalars(
        select(Milestone).where(Milestone.workspace_id == ws, Milestone.status == "open",
                                Milestone.due_date >= today, Milestone.due_date <= today + timedelta(days=45))
        .order_by(Milestone.due_date).limit(6)
    ).all()
    return DashboardOut(
        projects_active=active,
        tasks_by_status=by_status,
        overdue_tasks=overdue,
        my_open_tasks=[task_out(t, key) for t, key in mine],
        upcoming_milestones=[MilestoneOut(id=m.id, project_id=m.project_id, name=m.name, description=m.description,
                                          due_date=m.due_date, status=m.status) for m in upcoming],
        recent_activity=_activity(db, ws, 12),
    )
