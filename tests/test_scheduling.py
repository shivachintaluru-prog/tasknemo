"""Unit tests for cmd_check (lightweight scheduling)."""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import cmd_check


def _make_task(task_id="TASK-001", state="open", score=50, created_days_ago=0,
               title="Test task"):
    created = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "id": task_id,
        "title": title,
        "sender": "Alice",
        "state": state,
        "score": score,
        "score_breakdown": {},
        "created": created,
        "updated": created,
        "times_seen": 1,
        "due_hint": "",
        "description": "",
        "state_history": [{"state": state, "reason": "test", "date": created}],
    }


def _setup(tmp_path, tasks=None, config_overrides=None):
    """Set up temp data files and monkey-patch paths."""
    import task_dashboard as td

    old_tasks = td.TASKS_PATH
    old_config = td.CONFIG_PATH

    td.TASKS_PATH = str(tmp_path / "tasks.json")
    td.CONFIG_PATH = str(tmp_path / "config.json")

    store = {"tasks": tasks or []}
    with open(td.TASKS_PATH, "w") as f:
        json.dump(store, f)

    config = {
        "vault_path": str(tmp_path),
        "dashboard_filename": "Dash.md",
        "full_sync_threshold_hours": 8,
        "stakeholders": {},
        "urgency_keywords": [],
    }
    if config_overrides:
        config.update(config_overrides)
    with open(td.CONFIG_PATH, "w") as f:
        json.dump(config, f)

    return old_tasks, old_config


def _teardown(old_tasks, old_config):
    import task_dashboard as td
    td.TASKS_PATH = old_tasks
    td.CONFIG_PATH = old_config


class TestCmdCheck:
    def test_prints_counts(self, tmp_path, capsys):
        tasks = [
            _make_task(task_id="T-1", state="open"),
            _make_task(task_id="T-2", state="open"),
            _make_task(task_id="T-3", state="closed"),
        ]
        old = _setup(tmp_path, tasks, {"last_run": datetime.now().isoformat()})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "3 total" in out
            assert "open" in out
        finally:
            _teardown(*old)

    def test_shows_last_sync_time(self, tmp_path, capsys):
        last = (datetime.now() - timedelta(hours=2)).isoformat()
        old = _setup(tmp_path, [], {"last_run": last})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "Last sync:" in out
            assert "2h ago" in out
        finally:
            _teardown(*old)

    def test_handles_never_synced(self, tmp_path, capsys):
        old = _setup(tmp_path, [])
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "never" in out
            assert "Full sync recommended" in out
        finally:
            _teardown(*old)

    def test_shows_focus_items(self, tmp_path, capsys):
        tasks = [
            _make_task(task_id="T-1", score=80, title="Important thing"),
            _make_task(task_id="T-2", score=75, title="Also important"),
            _make_task(task_id="T-3", score=50, title="Less important"),
        ]
        old = _setup(tmp_path, tasks, {"last_run": datetime.now().isoformat()})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "Focus now:" in out
            assert "Important thing" in out
            assert "Also important" in out
            assert "Less important" not in out
        finally:
            _teardown(*old)

    def test_recommends_sync_when_stale(self, tmp_path, capsys):
        stale_run = (datetime.now() - timedelta(hours=10)).isoformat()
        old = _setup(tmp_path, [], {"last_run": stale_run})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "Full sync recommended" in out
        finally:
            _teardown(*old)

    def test_no_sync_recommendation_when_fresh(self, tmp_path, capsys):
        fresh_run = (datetime.now() - timedelta(hours=1)).isoformat()
        old = _setup(tmp_path, [], {"last_run": fresh_run})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "Full sync recommended" not in out
        finally:
            _teardown(*old)

    def test_handles_empty_store(self, tmp_path, capsys):
        old = _setup(tmp_path, [], {"last_run": datetime.now().isoformat()})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "0 total" in out
        finally:
            _teardown(*old)

    def test_stale_items_count(self, tmp_path, capsys):
        tasks = [
            _make_task(task_id="T-1", state="open", created_days_ago=10),
            _make_task(task_id="T-2", state="needs_followup", created_days_ago=9),
        ]
        old = _setup(tmp_path, tasks, {"last_run": datetime.now().isoformat()})
        try:
            cmd_check()
            out = capsys.readouterr().out
            assert "Stale items: 2" in out
        finally:
            _teardown(*old)
