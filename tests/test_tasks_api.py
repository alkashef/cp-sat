"""Tests for the /tasks CRUD API routes."""
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


def test_add_task_succeeds(client):
    response = client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    assert response.status_code == 201
    assert response.get_json() == {"name": "Write report", "duration_minutes": 90}
    assert client.get("/tasks").get_json() == [{"name": "Write report", "duration_minutes": 90}]


def test_add_task_duplicate_name_returns_409(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.post("/tasks", json={"name": "Write report", "duration_minutes": 30})

    assert response.status_code == 409


def test_add_task_invalid_duration_returns_400(client):
    response = client.post("/tasks", json={"name": "Write report", "duration_minutes": 20})

    assert response.status_code == 400


def test_edit_task_updates_name_and_duration(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.put("/tasks/Write report", json={"name": "Write memo", "duration_minutes": 45})

    assert response.status_code == 200
    assert response.get_json() == {"name": "Write memo", "duration_minutes": 45}
    assert client.get("/tasks").get_json() == [{"name": "Write memo", "duration_minutes": 45}]


def test_delete_task_removes_it(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.delete("/tasks/Write report")

    assert response.status_code == 204
    assert client.get("/tasks").get_json() == []


def test_task_list_persists_across_simulated_restart(client, tmp_path):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    reloaded = storage.load()

    assert reloaded["tasks"] == [{"name": "Write report", "duration_minutes": 90}]
