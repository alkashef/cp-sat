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


FLEXIBLE_DEFAULTS = {"schedule_mode": "flexible", "days": [], "hour": None}


def test_add_task_succeeds(client):
    response = client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    assert response.status_code == 201
    assert response.get_json() == {"name": "Write report", "duration_minutes": 90, **FLEXIBLE_DEFAULTS}
    assert client.get("/tasks").get_json() == [
        {"name": "Write report", "duration_minutes": 90, **FLEXIBLE_DEFAULTS}
    ]


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
    assert response.get_json() == {"name": "Write memo", "duration_minutes": 45, **FLEXIBLE_DEFAULTS}
    assert client.get("/tasks").get_json() == [
        {"name": "Write memo", "duration_minutes": 45, **FLEXIBLE_DEFAULTS}
    ]


def test_delete_task_removes_it(client):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    response = client.delete("/tasks/Write report")

    assert response.status_code == 204
    assert client.get("/tasks").get_json() == []


def test_task_list_persists_across_simulated_restart(client, tmp_path):
    client.post("/tasks", json={"name": "Write report", "duration_minutes": 90})

    reloaded = storage.load()

    assert reloaded["tasks"] == [{"name": "Write report", "duration_minutes": 90, **FLEXIBLE_DEFAULTS}]


@pytest.mark.parametrize(
    "schedule_mode, extra_fields",
    [
        ("fixed_hour", {"hour": 14}),
        ("fixed_days", {"days": ["Mon", "Wed"]}),
        ("fixed", {"days": ["Tue"], "hour": 9}),
    ],
)
def test_add_task_in_each_locked_mode_succeeds(client, schedule_mode, extra_fields):
    response = client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 15, "schedule_mode": schedule_mode, **extra_fields},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["schedule_mode"] == schedule_mode
    assert body["days"] == extra_fields.get("days", [])
    assert body["hour"] == extra_fields.get("hour")


def test_add_task_invalid_schedule_mode_returns_400(client):
    response = client.post(
        "/tasks", json={"name": "Standup", "duration_minutes": 15, "schedule_mode": "sometimes"}
    )

    assert response.status_code == 400


@pytest.mark.parametrize("schedule_mode", ["fixed_days", "fixed"])
def test_add_task_with_empty_days_for_a_day_locked_mode_returns_400(client, schedule_mode):
    response = client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 15, "schedule_mode": schedule_mode, "hour": 9, "days": []},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("schedule_mode", ["fixed_hour", "fixed"])
def test_add_task_missing_hour_for_an_hour_locked_mode_returns_400(client, schedule_mode):
    response = client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 15, "schedule_mode": schedule_mode, "days": ["Mon"]},
    )

    assert response.status_code == 400


def test_add_task_out_of_range_hour_returns_400(client):
    response = client.post(
        "/tasks", json={"name": "Standup", "duration_minutes": 15, "schedule_mode": "fixed_hour", "hour": 24}
    )

    assert response.status_code == 400


def test_add_task_duration_that_does_not_fit_in_a_day_returns_400(client):
    response = client.post(
        "/tasks",
        json={
            "name": "Marathon",
            "duration_minutes": 90,
            "schedule_mode": "fixed",
            "days": ["Mon"],
            "hour": 23,
        },
    )

    assert response.status_code == 400


def test_add_second_overlapping_fixed_task_returns_409(client):
    client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 30, "schedule_mode": "fixed", "days": ["Tue"], "hour": 9},
    )

    response = client.post(
        "/tasks",
        json={
            "name": "Planning",
            "duration_minutes": 30,
            "schedule_mode": "fixed",
            "days": ["Tue"],
            "hour": 9,
        },
    )

    assert response.status_code == 409
    assert [task["name"] for task in client.get("/tasks").get_json()] == ["Standup"]


def test_add_second_non_overlapping_fixed_task_succeeds(client):
    client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 30, "schedule_mode": "fixed", "days": ["Tue"], "hour": 9},
    )

    response = client.post(
        "/tasks",
        json={
            "name": "Planning",
            "duration_minutes": 30,
            "schedule_mode": "fixed",
            "days": ["Tue"],
            "hour": 10,
        },
    )

    assert response.status_code == 201


def test_edit_task_into_an_overlapping_fixed_slot_returns_409(client):
    client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 30, "schedule_mode": "fixed", "days": ["Tue"], "hour": 9},
    )
    client.post(
        "/tasks",
        json={
            "name": "Planning",
            "duration_minutes": 30,
            "schedule_mode": "fixed",
            "days": ["Wed"],
            "hour": 9,
        },
    )

    response = client.put("/tasks/Planning", json={"days": ["Tue"]})

    assert response.status_code == 409


def test_edit_that_keeps_a_fixed_tasks_own_slot_does_not_conflict_with_itself(client):
    client.post(
        "/tasks",
        json={"name": "Standup", "duration_minutes": 30, "schedule_mode": "fixed", "days": ["Tue"], "hour": 9},
    )

    response = client.put("/tasks/Standup", json={"duration_minutes": 30})

    assert response.status_code == 200
