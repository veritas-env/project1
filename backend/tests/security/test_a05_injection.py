"""A05 Injection: SQL payloads are inert, sort fields are allow-listed, output is JSON,
validation errors don't reflect input, downloads are never rendered."""

from __future__ import annotations

import pytest

SQLI = [
    "' OR '1'='1",
    "'; DROP TABLE tasks; --",
    "\\' OR 1=1 --",
    "%' AND pg_sleep(3) IS NULL AND '%'='",
    "' UNION SELECT email, password_hash FROM users --",
    "%",
    "_",
]


def tasks_url(w):
    return w.url(f"/projects/{w.project_a}/tasks")


@pytest.mark.parametrize("payload", SQLI)
def test_task_search_is_parameterised(app, world, payload):
    r = world.alice.client.get(tasks_url(world), params={"q": payload})
    assert r.status_code == 200
    assert r.json() == []


def test_like_wildcards_are_literal(app, world):
    c = world.alice.client
    c.post(tasks_url(world), json={"title": "Reach 100% coverage"})
    titles = [t["title"] for t in c.get(tasks_url(world), params={"q": "%"}).json()]
    assert titles == ["Reach 100% coverage"]


@pytest.mark.parametrize("sort", ["title; DROP TABLE tasks", "(CASE WHEN 1=1 THEN title ELSE description END)",
                                  "description", "password_hash", "number desc"])
def test_sort_field_allow_list(app, world, sort):
    assert world.alice.client.get(tasks_url(world), params={"sort": sort}).status_code == 422


@pytest.mark.parametrize("order", ["asc; SELECT 1", "ASC NULLS FIRST", "desc,title"])
def test_order_allow_list(app, world, order):
    assert world.alice.client.get(tasks_url(world), params={"order": order}).status_code == 422


@pytest.mark.parametrize("param,value", [("status", "done' OR '1'='1"), ("priority", "high;--"), ("assignee", "me' OR 1=1--")])
def test_filters_are_typed(app, world, param, value):
    assert world.alice.client.get(tasks_url(world), params={param: value}).status_code == 422


def test_project_key_format_enforced(app, world):
    r = world.alice.client.post(world.url("/projects"), json={"key": "A'--", "name": "x"})
    assert r.status_code == 422


def test_html_is_stored_as_data_and_returned_as_json(app, world):
    payload = '<script>alert(1)</script><img src=x onerror=alert(1)>'
    c = world.alice.client
    r = c.post(tasks_url(world), json={"title": payload, "description": payload})
    assert r.status_code == 201 and r.headers["content-type"].startswith("application/json")
    got = c.get(world.url(f"/tasks/{r.json()['id']}"))
    assert got.json()["title"] == payload


def test_validation_errors_do_not_reflect_input(app, world):
    marker = "<svg/onload=alert('reflected')>"
    r = world.alice.client.get(tasks_url(world), params={"sort": marker})
    assert r.status_code == 422 and marker not in r.text and "onload" not in r.text


def test_html_upload_is_never_rendered(app, world):
    c = world.alice.client
    r = c.post(world.url("/documents"), files={"file": ("x.html", b"<html><script>alert(1)</script>", "text/html")})
    assert r.status_code == 201
    d = c.get(r.json()["download_url"])
    assert d.headers["content-type"].startswith("text/plain")
    assert d.headers["x-content-type-options"] == "nosniff"
    assert d.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in d.headers["content-security-policy"]


def test_header_injection_in_download_name(app, world):
    c = world.alice.client
    r = c.post(world.url("/documents"), files={"file": ('a"\r\nX-Evil: 1.txt', b"x", "text/plain")})
    assert "x-evil" not in c.get(r.json()["download_url"]).headers
