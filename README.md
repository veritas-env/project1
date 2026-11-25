# ProjectFlow

Project management for teams: workspaces, projects, task boards, milestones, a shared
document library, team management with invitations, and an activity feed. Runs on
synthetic data only.

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic |
| Data | PostgreSQL 16, Redis 7 |
| Deploy | Docker Compose behind Nginx and the lab TLS gateway |

## Roles

| Role | Can |
|---|---|
| Viewer | read projects, tasks, milestones, documents, activity |
| Member | + create tasks, edit tasks they created or are assigned, upload documents |
| Manager | + create and edit projects and milestones, edit or delete any task, delete documents, invite viewers and members, remove members and viewers |
| Owner | + change roles, invite managers, delete projects, remove anyone (a workspace always keeps one owner) |

## Run the tests

```
cd backend
../.venv/Scripts/python.exe -m pytest -q
```

## Run with Docker

```
cp .env.example .env      # fill in every secret
make build up
docker compose -f deployment/compose.yaml --env-file .env run --rm backend \
    python -m app.cli seed-demo --passwords-out /data/uploads/../demo-passwords.json
```

The demo data contains two companies (Northwind Operations and Halcyon Labs) with
staff, projects, tasks, milestones and documents. Account passwords are generated at
seed time and written only to the file given by `--passwords-out`.

## Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/security-model.md](docs/security-model.md)
- [docs/test-plan.md](docs/test-plan.md)
- [docs/operations.md](docs/operations.md)
