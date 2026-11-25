"""Synthetic demo data for ProjectFlow: two companies, their people, projects, tasks,
milestones, documents and recent activity. Every name, company and figure is invented.

Used by `python -m app.cli seed-demo`. Dates are relative to the day it runs."""

from __future__ import annotations

import hashlib
import random
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.security import hash_password
from .models import Activity, Document, Membership, Milestone, Project, Task, User, Workspace

DOMAIN = "projectflow.lab"

WORKSPACES = [
    {
        "name": "Northwind Operations",
        "code": "NW",
        "description": "Logistics and distribution operations for the Northwind group.",
        "people": [
            ("priya.raman", "Priya Raman", "Head of Operations", "owner"),
            ("marcus.webb", "Marcus Webb", "Programme Manager", "manager"),
            ("elena.kovacs", "Elena Kovacs", "Systems Analyst", "member"),
            ("tom.okafor", "Tom Okafor", "Warehouse Engineer", "member"),
            ("scanner-a", "Alex Morgan", "Procurement Analyst", "member"),
            ("hannah.lindqvist", "Hannah Lindqvist", "Finance Partner", "viewer"),
        ],
        "projects": [
            ("WAR", "Warehouse Automation Rollout", "Conveyor, sortation and WMS integration for the Leeds and Bristol sites.", "active",
             ["Site survey sign-off", "Conveyor install – Leeds", "WMS cut-over"],
             ["Finalise conveyor layout for Leeds", "Confirm sorter throughput with vendor", "Map WMS pick-face locations",
              "Draft cut-over runbook", "Schedule weekend downtime with site leads", "Load-test label printers",
              "Train shift supervisors on new scanners", "Agree spare-parts stock levels", "Update fire-safety plan for new racking",
              "Review integration error queue", "Retire legacy RF terminals", "Post-go-live hypercare rota"]),
            ("VEN", "Vendor Consolidation 2026", "Reduce carrier and packaging suppliers from 23 to 9 without service loss.", "active",
             ["Shortlist approved", "Contracts signed"],
             ["Collect 12-month spend by supplier", "Score carriers on on-time delivery", "Request revised packaging quotes",
              "Prepare shortlist for steering group", "Run reference calls for shortlisted carriers", "Negotiate fuel-surcharge cap",
              "Legal review of master services agreement", "Plan exit notices for retiring suppliers"]),
            ("FLT", "Fleet Telematics Upgrade", "Replace in-cab units across 140 vehicles and move to the new tracking platform.", "on_hold",
             ["Pilot fleet live"],
             ["Select pilot depot", "Agree data-retention period with HR", "Install units on 10 pilot vehicles",
              "Driver privacy briefing", "Compare fuel data before and after pilot"]),
        ],
        "documents": [
            ("Vendor Shortlist Q3.md", "report", "VEN", "4471-K"),
            ("Carrier Scorecard – August.md", "report", "VEN", "5140-L"),
            ("Packaging Spend Analysis.txt", "report", "VEN", "4232-H"),
            ("Leeds Conveyor Layout Notes.md", "design", "WAR", "4164-D"),
            ("WMS Cut-over Runbook (draft).md", "specification", "WAR", "5789-R"),
            ("Steering Group Minutes 2026-10-14.md", "meeting_notes", None, "4896-E"),
            ("Steering Group Minutes 2026-11-11.md", "meeting_notes", None, "9202-A"),
            ("Telematics Pilot Proposal.md", "specification", "FLT", "5586-A"),
            ("Site Contacts.txt", "general", None, "9145-F"),
            ("Supplier Exit Checklist.md", "general", "VEN", "4133-S"),
        ],
    },
    {
        "name": "Halcyon Labs",
        "code": "HL",
        "description": "Research software and laboratory operations at Halcyon Labs.",
        "people": [
            ("scanner-b", "Jordan Blake", "Director of Research Engineering", "owner"),
            ("amara.osei", "Dr. Amara Osei", "Principal Scientist", "manager"),
            ("lucas.ferreira", "Lucas Ferreira", "Data Engineer", "member"),
            ("mei.chen", "Mei Chen", "Lab Systems Developer", "member"),
            ("yuki.tanaka", "Yuki Tanaka", "Quality Lead", "viewer"),
        ],
        "projects": [
            ("ASY", "Assay Platform v3", "Next version of the plate-reader analysis platform.", "active",
             ["Requirements frozen", "Beta with two labs"],
             ["Port curve-fitting module", "Add 384-well plate support", "Validate results against v2 on reference set",
              "Write user guide for new export formats", "Fix rounding in IC50 report", "Accessibility review of results view",
              "Set up nightly regression run", "Plan beta feedback sessions"]),
            ("CDP", "Clinical Data Pipeline", "Ingest, de-identify and catalogue study data for analysts.", "active",
             ["Ingest MVP", "De-identification audit"],
             ["Define study data contract", "Build SFTP ingest job", "Implement de-identification rules",
              "Catalogue datasets with owners", "Retention schedule review", "Dashboard for ingest failures",
              "Pen-test findings follow-up", "Runbook for weekend on-call"]),
            ("LSA", "Lab Safety Audit 2026", "Annual safety and compliance audit of all wet labs.", "completed",
             ["Audit report issued"],
             ["Schedule lab walk-throughs", "Collect chemical inventory", "Check fume-hood certificates",
              "Compile findings", "Issue final report"]),
        ],
        "documents": [
            ("Assay v3 Requirements.md", "specification", "ASY", "7366-F"),
            ("IC50 Rounding Investigation.md", "report", "ASY", "6431-L"),
            ("Study Data Contract v1.md", "contract", "CDP", "2921-C"),
            ("De-identification Rules.md", "specification", "CDP", "5265-T"),
            ("Lab Safety Audit Report 2026.md", "report", "LSA", "8694-G"),
            ("Fume Hood Certificates.txt", "report", "LSA", "4696-G"),
            ("Research Eng Weekly 2026-11-17.md", "meeting_notes", None, "2177-C"),
            ("On-call Runbook.md", "general", "CDP", "4278-Y"),
            ("Beta Lab Contacts.txt", "general", "ASY", "8170-V"),
        ],
    },
]

STATUSES = ["todo", "todo", "in_progress", "in_progress", "review", "done", "done", "done"]
PRIORITIES = ["low", "medium", "medium", "medium", "high", "high", "urgent"]


def _doc_body(title: str, workspace: str, code: str, ref: str, rnd: random.Random) -> str:
    lines = [f"# {title.rsplit('.', 1)[0]}", "", f"{workspace} · internal", f"Reference code: PF-{code}-{ref}", ""]
    if "Shortlist" in title:
        lines += [
            "## Recommended carriers", "",
            "| Rank | Carrier | On-time % | Cost index | Notes |",
            "|---|---|---|---|---|",
            "| 1 | Brightline Freight | 97.2 | 0.94 | Strong in the North; flexible on surcharges |",
            "| 2 | Corran Logistics | 96.1 | 0.97 | Good EV fleet roadmap |",
            "| 3 | Meridian Parcel | 95.4 | 1.00 | Incumbent; price review due |",
            "| 4 | Aldgate Express | 94.8 | 0.91 | Lowest cost, limited weekend cover |",
            "", "## Packaging", "",
            "Consolidate to two suppliers: Fenwick Board (corrugated) and Osprey Films (stretch wrap).",
            "Projected annual saving: £412k against FY25 baseline.", "",
            "## Next steps", "", "- Steering group approval on 9 December", "- Reference calls with ranks 1–3",
        ]
    elif "Minutes" in title or "Weekly" in title:
        lines += ["## Attendees", "", "Leads from operations, finance and IT.", "", "## Decisions", ""]
        lines += [f"- Decision {i + 1}: {rnd.choice(['approved', 'deferred to next meeting', 'approved with changes'])}" for i in range(3)]
        lines += ["", "## Actions", ""] + [f"- Action {i + 1} — owner to confirm by Friday" for i in range(4)]
    elif title.endswith(".txt"):
        lines += [f"Item {i + 1}: {rnd.choice(['confirmed', 'pending', 'n/a', 'see project board'])}" for i in range(12)]
    else:
        lines += ["## Summary", "", "This document is maintained by the project team. Comments go in the project board.", "",
                  "## Details", ""] + [f"{i + 1}. Point {i + 1} — {rnd.choice(['agreed', 'open', 'needs data', 'done'])}" for i in range(6)]
    return "\n".join(lines) + "\n"


def seed_demo(s: Session, upload_dir: str | Path, seed: int = 2026) -> dict[str, str]:
    """Create the demo data. Returns {email: password} for every account created."""
    if s.scalar(select(Workspace.id).limit(1)) is not None:
        raise RuntimeError("database already has workspaces; reset it first")
    rnd = random.Random(seed)
    today = date.today()
    now = datetime.now(timezone.utc)
    upload = Path(upload_dir)
    upload.mkdir(parents=True, exist_ok=True)
    passwords: dict[str, str] = {}

    def user(local: str, name: str, title: str | None, admin: bool = False) -> User:
        pw = "Lab-" + secrets.token_urlsafe(18)
        u = User(email=f"{local}@{DOMAIN}", display_name=name, job_title=title, password_hash=hash_password(pw),
                 is_platform_admin=admin)
        s.add(u)
        s.flush()
        passwords[u.email] = pw
        return u

    user("platform-admin", "Platform Administrator", "IT Security", admin=True)

    for spec in WORKSPACES:
        ws = Workspace(name=spec["name"], description=spec["description"])
        s.add(ws)
        s.flush()
        people = []
        for local, name, title, role in spec["people"]:
            u = user(local, name, title)
            s.add(Membership(workspace_id=ws.id, user_id=u.id, role=role))
            people.append((u, role))
        doers = [u for u, r in people if r != "viewer"]
        managers = [u for u, r in people if r in ("owner", "manager")]
        log: list[Activity] = []

        def act(days_ago: float, actor: User, verb: str, otype: str, oid, summary: str) -> None:
            log.append(Activity(workspace_id=ws.id, actor_id=actor.id, verb=verb, object_type=otype, object_id=oid,
                                summary=summary, at=now - timedelta(days=days_ago, minutes=rnd.randint(0, 600))))

        projects: dict[str, Project] = {}
        for key, name, desc, status, milestones, tasks in spec["projects"]:
            lead = rnd.choice(managers)
            start = today - timedelta(days=rnd.randint(40, 120))
            p = Project(workspace_id=ws.id, key=key, name=name, description=desc, status=status, lead_id=lead.id,
                        start_date=start, target_date=start + timedelta(days=rnd.randint(120, 240)), created_by=lead.id)
            s.add(p)
            s.flush()
            projects[key] = p
            act(rnd.uniform(30, 60), lead, "created", "project", p.id, f"created project {key} · {name}")
            ms = []
            for i, mname in enumerate(milestones):
                due = today + timedelta(days=-20 + i * 25 + rnd.randint(-5, 10))
                m = Milestone(workspace_id=ws.id, project_id=p.id, name=mname, due_date=due,
                              status="closed" if (status == "completed" or due < today - timedelta(days=7)) else "open")
                s.add(m)
                ms.append(m)
            s.flush()
            for n, title in enumerate(tasks, start=1):
                st = "done" if status == "completed" else rnd.choice(STATUSES)
                assignee = rnd.choice(doers + [None])
                creator = rnd.choice(doers)
                t = Task(workspace_id=ws.id, project_id=p.id, number=n, title=title,
                         description=f"{title}. See the {name} plan for context.",
                         status=st, priority=rnd.choice(PRIORITIES), assignee_id=assignee.id if assignee else None,
                         milestone_id=rnd.choice(ms).id if ms and rnd.random() < 0.7 else None,
                         due_date=today + timedelta(days=rnd.randint(-10, 45)) if rnd.random() < 0.8 else None,
                         created_by=creator.id)
                s.add(t)
                s.flush()
                act(rnd.uniform(2, 30), creator, "created", "task", t.id, f"created {key}-{n} “{title}”")
                if st != "todo":
                    act(rnd.uniform(0.1, 2), assignee or creator, "moved", "task", t.id,
                        f"moved {key}-{n} from to do to {st.replace('_', ' ')}")

        for title, category, pkey, ref in spec["documents"]:
            body = _doc_body(title, spec["name"], spec["code"], ref, rnd).encode("utf-8")
            uploader = rnd.choice(doers)
            d = Document(id=uuid.uuid4(), workspace_id=ws.id, project_id=projects[pkey].id if pkey else None,
                         uploader_id=uploader.id, title=title, category=category, content_type="text/plain",
                         size=len(body), sha256=hashlib.sha256(body).hexdigest())
            (upload / d.id.hex).write_bytes(body)
            s.add(d)
            s.flush()
            act(rnd.uniform(0.2, 20), uploader, "uploaded", "document", d.id, f"uploaded “{title}”")

        s.add_all(log)
    s.commit()
    return passwords
