"""A06 Insecure Design: ProjectFlow's business rules (docs/security-model.md §3) are
enforced server-side."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.models import Invitation
from tests.conftest import make_client


# --- membership -----------------------------------------------------------------

def test_last_owner_cannot_be_demoted_or_removed(app, world):
    c = world.alice.client
    assert c.put(world.url(f"/members/{world.alice.id}"), json={"role": "manager"}).status_code == 409
    assert c.delete(world.url(f"/members/{world.alice.id}")).status_code == 409


def test_owner_can_hand_over_then_step_down(app, world):
    c = world.alice.client
    assert c.put(world.url(f"/members/{world.adam.id}"), json={"role": "owner"}).status_code == 200
    assert c.put(world.url(f"/members/{world.alice.id}"), json={"role": "manager"}).status_code == 200


def test_cannot_assign_unknown_role(app, world):
    assert world.alice.client.put(world.url(f"/members/{world.bob.id}"), json={"role": "superuser"}).status_code == 422


def test_removed_member_loses_access_and_assignments(app, world):
    world.alice.client.patch(world.url(f"/tasks/{world.task_a}"), json={"assignee_id": str(world.bob.id)})
    assert world.adam.client.delete(world.url(f"/members/{world.bob.id}")).status_code == 204
    assert world.bob.client.get(world.url("/projects")).status_code == 404
    assert world.alice.client.get(world.url(f"/tasks/{world.task_a}")).json()["assignee_id"] is None


# --- invitations ----------------------------------------------------------------

def test_invitation_is_single_use(app, world):
    anon = make_client(app)
    body = {"token": world.invite_token, "display_name": "Newcomer", "password": "Brand-new-Passphrase-42"}
    assert anon.post("/api/v1/invitations/register", json=body).status_code == 201
    assert make_client(app).post("/api/v1/invitations/register", json=body).status_code == 404
    assert make_client(app).post("/api/v1/invitations/preview", json={"token": world.invite_token}).status_code == 404


def test_registered_user_lands_in_the_right_workspace_with_the_invited_role(app, world):
    c = make_client(app)
    r = c.post("/api/v1/invitations/register", json={"token": world.invite_token, "display_name": "N",
                                                      "password": "Brand-new-Passphrase-42"})
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    ws = c.get("/api/v1/workspaces").json()
    assert [(w["id"], w["role"]) for w in ws] == [(str(world.ws_a), "member")]


def test_expired_invitation_rejected(app, world):
    with app.state.sessionmaker() as s:
        s.execute(update(Invitation).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        s.commit()
    assert make_client(app).post("/api/v1/invitations/preview", json={"token": world.invite_token}).status_code == 404


def test_revoked_invitation_rejected(app, world):
    assert world.adam.client.delete(world.url(f"/invitations/{world.invitation_a}")).status_code == 204
    assert make_client(app).post("/api/v1/invitations/preview", json={"token": world.invite_token}).status_code == 404


def test_reinviting_revokes_the_previous_link(app, world):
    world.alice.client.post(world.url("/invitations"), json={"email": "newcomer@lab.test", "role": "viewer"})
    assert make_client(app).post("/api/v1/invitations/preview", json={"token": world.invite_token}).status_code == 404


def test_cannot_invite_existing_member(app, world):
    assert world.alice.client.post(world.url("/invitations"), json={"email": "bob@lab.test"}).status_code == 409


def test_register_cannot_take_over_existing_account(app, world):
    world.alice.client.post(world.url("/invitations"), json={"email": "mallory@lab.test", "role": "viewer"})
    # Fetch the new token from the response instead:
    r = world.alice.client.post(world.url("/invitations"), json={"email": "mallory@lab.test", "role": "viewer"})
    token = r.json()["invite_url"].split("#", 1)[1]
    reg = make_client(app).post("/api/v1/invitations/register", json={"token": token, "display_name": "x",
                                                                       "password": "Brand-new-Passphrase-42"})
    assert reg.status_code == 409


def test_register_enforces_password_policy(app, world):
    r = make_client(app).post("/api/v1/invitations/register", json={"token": world.invite_token, "display_name": "N",
                                                                     "password": "password1234"})
    assert r.status_code == 422 and r.json()["error"] == "weak_password"


def test_invitation_preview_is_rate_limited(app, world):
    c = make_client(app)
    codes = [c.post("/api/v1/invitations/preview", json={"token": "x" * 43}).status_code for _ in range(21)]
    assert codes[-1] == 429


# --- projects and tasks -----------------------------------------------------------

def test_archived_project_accepts_no_new_tasks(app, world):
    world.adam.client.patch(world.url(f"/projects/{world.project_a}"), json={"status": "archived"})
    r = world.adam.client.post(world.url(f"/projects/{world.project_a}/tasks"), json={"title": "x"})
    assert r.status_code == 409


def test_project_keys_unique_per_workspace(app, world):
    assert world.alice.client.post(world.url("/projects"), json={"key": "PA", "name": "dup"}).status_code == 409
    # The same key is fine in another workspace.
    assert world.mallory.client.post(world.url("/projects", "b"), json={"key": "PA", "name": "ok"}).status_code == 201


def test_task_numbers_are_sequential_per_project(app, world):
    c = world.alice.client
    refs = [c.post(world.url(f"/projects/{world.project_a}/tasks"), json={"title": f"t{i}"}).json()["ref"] for i in range(3)]
    assert refs == ["PA-2", "PA-3", "PA-4"]


def test_project_dates_must_be_ordered(app, world):
    r = world.alice.client.post(world.url("/projects"), json={"key": "DT", "name": "x", "start_date": "2026-05-01",
                                                              "target_date": "2026-04-01"})
    assert r.status_code == 422


def test_milestone_must_belong_to_task_project(app, world):
    c = world.alice.client
    other = c.post(world.url("/projects"), json={"key": "OT", "name": "Other"}).json()["id"]
    r = c.post(world.url(f"/projects/{other}/tasks"), json={"title": "x", "milestone_id": str(world.milestone_a)})
    assert r.status_code == 422


# --- limits -----------------------------------------------------------------------

def test_page_size_is_capped(app, world):
    url = world.url(f"/projects/{world.project_a}/tasks")
    assert world.alice.client.get(url, params={"limit": 10_000}).status_code == 422
    assert world.alice.client.get(world.url("/activity"), params={"limit": 10_000}).status_code == 422


def test_field_lengths_are_capped(app, world):
    url = world.url(f"/projects/{world.project_a}/tasks")
    c = world.alice.client
    assert c.post(url, json={"title": "x" * 201}).status_code == 422
    assert c.post(url, json={"title": "x", "description": "y" * 10_001}).status_code == 422
    assert c.post(url, json={"title": "   "}).status_code == 422


def test_upload_limits(app, world, settings):
    c = world.alice.client
    big = b"a" * (settings.max_upload_bytes + 1)
    assert c.post(world.url("/documents"), files={"file": ("big.txt", big, "text/plain")}).status_code == 413
    exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    assert c.post(world.url("/documents"), files={"file": ("doc.pdf", exe, "application/pdf")}).status_code == 415
    assert c.post(world.url("/documents"), files={"file": ("e.txt", b"", "text/plain")}).status_code == 422
    assert c.post(world.url("/documents"), files={"file": ("x.txt", b"x", "text/plain")},
                  data={"category": "secret"}).status_code == 422
