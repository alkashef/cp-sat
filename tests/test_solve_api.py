"""Tests for the /solve API route."""
import pytest

import storage
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setenv("TASKS_FILE", str(tasks_file))
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


def test_solve_with_feasible_tasks_returns_and_persists_schedule(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.post("/solve")

    assert response.status_code == 200
    body = response.get_json()
    assert body["schedule"][0]["name"] == "Write report"
    assert storage.load()["schedule"] == body["schedule"]


def test_solve_with_infeasible_tasks_returns_error_and_leaves_schedule_untouched(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})
    client.post("/solve")
    stored_schedule = storage.load()["schedule"]

    client.post("/tasks", json={"name": "Huge", "duration_minutes": 10095})
    response = client.post("/solve")

    assert response.status_code == 400
    assert "error" in response.get_json()
    assert storage.load()["schedule"] == stored_schedule


def test_add_edit_remove_task_does_not_trigger_solve(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})
    client.put("/tasks/Write report", json={"duration_minutes": 45})
    client.delete("/tasks/Write report")

    assert storage.load()["schedule"] is None
