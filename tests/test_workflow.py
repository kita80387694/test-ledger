from uuid import uuid4

import pytest
from sqlalchemy import func, select

from testledger.config import DemoSeedSettings
from testledger.models import Defect, Execution, TestPlan as Plan, User
from testledger.seed import seed_demo


def post_id(client, headers, path, body):
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def get_json(client, headers, path):
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def execution(client, headers, plan_id, result="failed"):
    return post_id(client, headers, f"/plans/{plan_id}/executions", {"case_key": "QA-1", "result": result})


def make_failure(client, headers, plan_name, titles):
    plan = post_id(client, headers, "/plans", {"name": plan_name})
    failed = execution(client, headers, plan)
    defects = [
        post_id(client, headers, f"/executions/{failed}/defects", {"title": title})
        for title in titles
    ]
    return plan, failed, defects


def set_status(client, headers, defect_id, status):
    return client.patch(f"/defects/{defect_id}/status", headers=headers, json={"status": status})


def close_defect(client, headers, defect_id):
    for status in ("in_progress", "resolved", "closed"):
        result = set_status(client, headers, defect_id, status)
        assert result.status_code == 200, result.text
        assert result.json()["status"] == status


def item_ids(page):
    return [item["id"] for item in page["items"]]


def counts(summary):
    return summary["failed_execution_count"], summary["open_defect_count"]


def test_counts_and_lists_across_two_plans_and_defect_closures(client, login):
    tester = login()
    plan, failed, defects = make_failure(client, tester, "Checkout", ["Wrong amount", "Missing total"])
    other, other_failed, other_defects = make_failure(client, tester, "Search", ["Empty result"])
    execution(client, tester, plan, result="passed")
    reader = login("viewer")

    for remaining in (defects, defects[1:], []):
        summary = get_json(client, reader, f"/plans/{plan}/summary")
        assert counts(summary) == (1, len(remaining))
        assert item_ids(get_json(client, reader, f"/plans/{plan}/failed-executions")) == [failed]
        assert item_ids(get_json(client, reader, f"/plans/{plan}/open-defects")) == sorted(remaining)
        assert counts(get_json(client, reader, f"/plans/{other}/summary")) == (1, 1)
        assert item_ids(get_json(client, reader, f"/plans/{other}/failed-executions")) == [other_failed]
        assert item_ids(get_json(client, reader, f"/plans/{other}/open-defects")) == other_defects
        if remaining:
            close_defect(client, tester, remaining[0])


def test_empty_plan_and_paginated_defects(client, login):
    headers = login()
    empty = post_id(client, headers, "/plans", {"name": "Empty"})
    assert counts(get_json(client, headers, f"/plans/{empty}/summary")) == (0, 0)
    assert item_ids(get_json(client, headers, f"/plans/{empty}/failed-executions")) == []
    plan, _, defects = make_failure(client, headers, "With pages", ["One", "Two"])
    path = f"/plans/{plan}/open-defects?limit=1"
    first = get_json(client, headers, path)
    second = get_json(client, headers, f"{path}&offset=1")
    assert item_ids(first) + item_ids(second) == sorted(defects)
    assert (first["has_more"], second["has_more"]) == (True, False)
    assert (first["offset"], second["offset"], second["limit"]) == (0, 1, 1)


def test_unauthenticated_write(client):
    response = client.post("/plans", json={"name": "Unauthorized"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"


def test_invalid_bearer_token(client):
    response = client.post("/plans", headers={"Authorization": "Bearer wrong"}, json={"name": "No"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("username", ["tester", "missing"])
def test_invalid_login_credentials(client, username):
    response = client.post(
        "/auth/token", data={"grant_type": "password", "username": username, "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid username or password."


def test_viewer_cannot_use_any_write_endpoint(client, login):
    viewer = login("viewer")
    target = uuid4()
    writes = [
        ("POST", "/plans", {"name": "forbidden"}),
        ("POST", f"/plans/{target}/executions", {"case_key": "QA-2", "result": "passed"}),
        ("POST", f"/executions/{target}/defects", {"title": "forbidden"}),
        ("PATCH", f"/defects/{target}/status", {"status": "in_progress"}),
    ]
    for method, path, body in writes:
        response = client.request(method, path, headers=viewer, json=body)
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "forbidden"


def test_passing_execution_cannot_have_defects(client, login):
    headers = login()
    plan = post_id(client, headers, "/plans", {"name": "All pass"})
    passed = execution(client, headers, plan, "passed")
    response = client.post(f"/executions/{passed}/defects", headers=headers, json={"title": "Invalid"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "execution_not_failed"
    assert counts(get_json(client, headers, f"/plans/{plan}/summary")) == (0, 0)


def test_status_conflict_and_admin_only_reopening(client, login):
    tester = login()
    plan, _, (defect,) = make_failure(client, tester, "Reopen", ["Regression"])
    response = set_status(client, tester, defect, "closed")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    close_defect(client, tester, defect)
    assert set_status(client, tester, defect, "in_progress").status_code == 403
    reopened = set_status(client, login("admin"), defect, "in_progress")
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "in_progress"
    assert counts(get_json(client, tester, f"/plans/{plan}/summary")) == (1, 1)


@pytest.mark.parametrize(
    ("method", "path", "body", "field"),
    [
        ("POST", "/plans", {"name": "   "}, "body.name"),
        ("GET", "/plans/no-uuid/summary", None, "path.plan_id"),
        ("GET", f"/plans/{uuid4()}/open-defects?limit=101", None, "query.limit"),
    ],
)
def test_validation_errors_use_shared_envelope(client, login, method, path, body, field):
    response = client.request(method, path, headers=login(), json=body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == field


def test_unknown_plan_returns_404(client, login):
    headers = login("viewer")
    for endpoint in ("summary", "failed-executions", "open-defects"):
        response = client.get(f"/plans/{uuid4()}/{endpoint}", headers=headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "plan_not_found"


def test_seed_is_repeatable(db):
    settings = DemoSeedSettings(
        demo_admin_password="test-seed-admin",
        demo_tester_password="test-seed-tester",
        demo_viewer_password="test-seed-viewer",
    )
    plan = seed_demo(db, settings)
    db.commit()
    assert seed_demo(db, settings) == plan
    db.commit()
    for entity, expected in ((User, 3), (Plan, 1), (Execution, 1), (Defect, 1)):
        assert db.scalar(select(func.count()).select_from(entity)) == expected
