"""A08 Software or Data Integrity Failures: the server computes what it trusts, and
clients can't set fields they shouldn't (mass assignment, CWE-915)."""

from __future__ import annotations

import hashlib

import pytest

from tests.conftest import make_client


def test_upload_hash_is_computed_by_server(app, world):
    data = b"exact bytes"
    r = world.alice.client.post(world.url("/documents"), files={"file": ("x.txt", data, "text/plain")},
                                data={"sha256": "0" * 64, "size": "1"})
    assert r.status_code == 201
    assert r.json()["sha256"] == hashlib.sha256(data).hexdigest() and r.json()["size"] == len(data)


def test_downloaded_bytes_match_recorded_hash(app, world):
    c = world.alice.client
    meta = c.get(world.url(f"/documents/{world.document_a}")).json()
    assert hashlib.sha256(c.get(meta["download_url"]).content).hexdigest() == meta["sha256"]


@pytest.mark.parametrize("extra", [
    {"workspace_id": "00000000-0000-0000-0000-000000000000"},
    {"project_id": "00000000-0000-0000-0000-000000000000"},
    {"number": 1},
    {"created_by": "00000000-0000-0000-0000-000000000000"},
    {"id": "00000000-0000-0000-0000-000000000000"},
    {"created_at": "2000-01-01T00:00:00Z"},
])
def test_task_rejects_server_owned_fields(app, world, extra):
    r = world.bob.client.post(world.url(f"/projects/{world.project_a}/tasks"), json={"title": "t", **extra})
    assert r.status_code == 422


@pytest.mark.parametrize("extra", [{"workspace_id": "00000000-0000-0000-0000-000000000000"}, {"key": "NEW"}, {"created_by": None}])
def test_project_update_rejects_server_owned_fields(app, world, extra):
    assert world.alice.client.patch(world.url(f"/projects/{world.project_a}"), json=extra).status_code == 422


def test_login_rejects_extra_fields(app, world):
    r = make_client(app).post("/api/v1/auth/login", json={"email": world.bob.email, "password": world.bob.password,
                                                          "is_platform_admin": True})
    assert r.status_code == 422


def test_invitation_role_and_email_come_from_the_invitation(app, world):
    r = make_client(app).post("/api/v1/invitations/register", json={
        "token": world.invite_token, "display_name": "N", "password": "Brand-new-Passphrase-42", "role": "owner"})
    assert r.status_code == 422


def test_role_body_cannot_smuggle_user(app, world):
    r = world.alice.client.put(world.url(f"/members/{world.bob.id}"), json={"role": "viewer", "user_id": str(world.vera.id)})
    assert r.status_code == 422
