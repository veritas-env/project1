# Architecture

See the trust-boundary diagram in `security-model.md` §1.

- **Frontend**: Next.js App Router. Pages: workspaces, overview dashboard, projects,
  project board (tasks by status, milestones, project documents), documents, team &
  invitations, activity, and an invitation landing page (`/invite#<token>`).
- **Backend**: FastAPI app factory (`app.main:create_app`). Routers: `auth`, `workspaces`
  (members), `invitations`, `projects` (and milestones), `tasks`, `documents`,
  `downloads`, `overview` (dashboard, activity), `admin` (security events, alerts).
- **Data model**: `workspaces` → `memberships(role)`, `invitations`, `projects` →
  `milestones`, `tasks`; `documents`; `activity` (business feed); `security_events`
  (append-only) and `alerts`.
- **Roles**: viewer < member < manager < owner (see README). Platform admins see
  security events and alerts only.
- **Downloads**: document files are served from `/api/v1/documents/{id}/content`, a
  stable link used by the document library, project pages and the activity feed.
- **Demo data**: `python -m app.cli seed-demo` (see `app/demo_data.py`).
