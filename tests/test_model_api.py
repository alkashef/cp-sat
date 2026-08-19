"""Tests for the /model API route."""
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


def test_model_describes_the_current_task_list(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.get("/model")

    assert response.status_code == 200
    body = response.get_json()
    assert [variable["name"] for variable in body["variables"]] == [
        "Write report",
        "Write report",
        "makespan",
    ]
    assert [constraint["type"] for constraint in body["constraints"]] == [
        "AddNoOverlap",
        "AddMaxEquality",
    ]
    assert body["objective"]["expression"] == "makespan"
    assert "no_overlap" in body["raw_proto"]


def test_model_with_no_tasks_returns_an_empty_description(client):
    response = client.get("/model")

    assert response.status_code == 200
    assert response.get_json() == {
        "variables": [],
        "constraints": [],
        "objective": None,
        "raw_proto": "",
    }


def test_model_does_not_solve_or_persist_a_schedule(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    client.get("/model")

    assert storage.load()["schedule"] is None
