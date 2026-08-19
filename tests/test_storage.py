"""Tests for storage.py's load/save round-trip behavior."""
import os

import storage


def test_save_then_load_round_trips_tasks(tmp_path, monkeypatch):
    tasks_file = tmp_path / "tasks.json"
    monkeypatch.setenv("TASKS_FILE", str(tasks_file))

    data = {"tasks": [{"name": "Write report", "duration_minutes": 90}], "schedule": None}
    storage.save(data)

    assert storage.load() == data


def test_load_missing_file_returns_empty_task_list(tmp_path, monkeypatch):
    tasks_file = tmp_path / "does_not_exist.json"
    monkeypatch.setenv("TASKS_FILE", str(tasks_file))

    assert storage.load() == {"tasks": [], "schedule": None}
