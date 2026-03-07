"""Unit tests for alerts / notifications."""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import render_alerts, write_alerts, finalize_sync


def _fresh_analytics():
    return {"response_times": {}, "escalation_history": {}, "user_pins": []}


def _make_task(task_id="TASK-001", sender="Alice", title="Test task",
               direction="inbound", state="open", created_days_ago=0):
    created = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "id": task_id,
        "title": title,
        "sender": sender,
        "direction": direction,
        "state": state,
        "created": created,
        "updated": created,
        "times_seen": 1,
        "due_hint": "",
        "description": "",
        "state_history": [{"state": state, "reason": "test", "date": created}],
    }


# ── Render Alerts ────────────────────────────────────────────────────────


class TestRenderAlerts:
    def test_header_present(self):
        md = render_alerts([], [], {})
        assert "# Task Alerts" in md

    def test_new_tasks_section(self):
        tasks = [_make_task(title="Fix bug", sender="Bob")]
        md = render_alerts([], tasks, {})
        assert "[!abstract] New Tasks" in md
        assert "Fix bug" in md
        assert "Bob" in md

    def test_state_changes_section(self):
        transitions = [("TASK-001", "open", "likely_done", "Completion signal")]
        md = render_alerts(transitions, [], {})
        assert "[!info] State Changes" in md
        assert "TASK-001" in md
        assert "open -> likely_done" in md

    def test_escalation_section(self):
        analytics = _fresh_analytics()
        analytics["escalation_history"] = {
            "TASK-002": [
                {"urgency": 1, "ts": "2026-01-01T00:00:00"},
                {"urgency": 3, "ts": "2026-01-02T00:00:00"},
            ]
        }
        md = render_alerts([], [], {}, analytics)
        assert "[!warning] Escalations" in md
        assert "TASK-002" in md

    def test_stale_items_section(self, tmp_path):
        import task_dashboard as td
        old_path = td.TASKS_PATH
        td.TASKS_PATH = str(tmp_path / "tasks.json")
        try:
            store = {"tasks": [_make_task(created_days_ago=10, state="open")]}
            with open(td.TASKS_PATH, "w") as f:
                json.dump(store, f)
            md = render_alerts([], [], {})
            assert "[!danger] Stale Items" in md
            assert "TASK-001" in md
            assert "10d old" in md
        finally:
            td.TASKS_PATH = old_path

    def test_empty_deltas(self):
        md = render_alerts([], [], {})
        assert "*No new tasks this sync.*" in md
        assert "*No state changes.*" in md

    def test_direction_arrows(self):
        inbound = _make_task(direction="inbound", title="Inbound task")
        outbound = _make_task(direction="outbound", title="Outbound task")
        md = render_alerts([], [inbound, outbound], {})
        assert "<-" in md
        assert "->" in md

    def test_stale_cap_at_10(self, tmp_path):
        import task_dashboard as td
        old_path = td.TASKS_PATH
        td.TASKS_PATH = str(tmp_path / "tasks.json")
        try:
            tasks = [
                _make_task(task_id=f"TASK-{i:03d}", created_days_ago=10, state="open")
                for i in range(15)
            ]
            store = {"tasks": tasks}
            with open(td.TASKS_PATH, "w") as f:
                json.dump(store, f)
            md = render_alerts([], [], {})
            assert "...and 5 more" in md
        finally:
            td.TASKS_PATH = old_path


# ── Write Alerts ─────────────────────────────────────────────────────────


class TestWriteAlerts:
    def test_writes_file(self, tmp_path):
        md = "# Test Alerts"
        path = write_alerts(md, str(tmp_path), "Test Alerts.md")
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == md

    def test_creates_dir(self, tmp_path):
        nested = str(tmp_path / "sub" / "dir")
        path = write_alerts("# Test", nested, "Alerts.md")
        assert os.path.exists(path)


# ── Finalize Sync with Alerts ────────────────────────────────────────────


class TestFinalizeSyncWithAlerts:
    def _setup_env(self, tmp_path):
        import task_dashboard as td
        old_tasks = td.TASKS_PATH
        old_run_log = td.RUN_LOG_PATH
        old_analytics = td.ANALYTICS_PATH
        td.TASKS_PATH = str(tmp_path / "tasks.json")
        td.RUN_LOG_PATH = str(tmp_path / "run_log.json")
        td.ANALYTICS_PATH = str(tmp_path / "analytics.json")

        store = {"tasks": [_make_task()]}
        with open(td.TASKS_PATH, "w") as f:
            json.dump(store, f)
        with open(td.RUN_LOG_PATH, "w") as f:
            json.dump({"runs": []}, f)
        with open(td.ANALYTICS_PATH, "w") as f:
            json.dump(_fresh_analytics(), f)

        return old_tasks, old_run_log, old_analytics

    def _teardown_env(self, old_tasks, old_run_log, old_analytics):
        import task_dashboard as td
        td.TASKS_PATH = old_tasks
        td.RUN_LOG_PATH = old_run_log
        td.ANALYTICS_PATH = old_analytics

    def test_backward_compat_no_transitions(self, tmp_path):
        import task_dashboard as td
        old = self._setup_env(tmp_path)
        try:
            vault = str(tmp_path / "vault")
            ctx = {
                "config": {"vault_path": vault, "dashboard_filename": "Dash.md"},
            }
            path = finalize_sync({"new_tasks": 0}, ctx)
            assert os.path.exists(path)
            # No alerts file should exist
            assert not os.path.exists(os.path.join(vault, "Task Alerts.md"))
        finally:
            self._teardown_env(*old)

    def test_with_transitions_writes_alerts(self, tmp_path):
        import task_dashboard as td
        old = self._setup_env(tmp_path)
        try:
            vault = str(tmp_path / "vault")
            ctx = {
                "config": {
                    "vault_path": vault,
                    "dashboard_filename": "Dash.md",
                    "alerts_filename": "Task Alerts.md",
                },
            }
            transitions = [("TASK-001", "open", "likely_done", "test")]
            path = finalize_sync(
                {"new_tasks": 0}, ctx,
                transitions=transitions, new_tasks=[],
            )
            assert os.path.exists(path)
            alerts_path = os.path.join(vault, "Task Alerts.md")
            assert os.path.exists(alerts_path)
            with open(alerts_path) as f:
                content = f.read()
            assert "TASK-001" in content
        finally:
            self._teardown_env(*old)
