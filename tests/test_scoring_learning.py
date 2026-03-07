"""Unit tests for analytics-based scoring: response times, escalation, pins."""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    load_analytics,
    save_analytics,
    record_response_time,
    get_response_time_factor,
    record_mention,
    get_escalation_bonus,
    pin_task,
    unpin_task,
    get_pin_bonus,
    score_task,
    score_all_tasks,
    ANALYTICS_PATH,
)


def _fresh_analytics():
    """Return a clean analytics dict (no file I/O)."""
    return {"response_times": {}, "escalation_history": {}, "user_pins": []}


def _make_config():
    return {
        "stakeholders": {
            "alex morgan": {"name": "Alex Morgan", "weight": 8},
        },
        "urgency_keywords": ["urgent", "asap"],
    }


def _make_task(task_id="TASK-TEST", sender="Alex Morgan", title="Test task",
               created_days_ago=0, times_seen=1, state="open"):
    created = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "id": task_id,
        "title": title,
        "description": "",
        "sender": sender,
        "due_hint": "",
        "state": state,
        "times_seen": times_seen,
        "created": created,
        "updated": created,
        "state_history": [{"state": "open", "reason": "test", "date": created}],
    }


# ── Response Time Tracking ──────────────────────────────────────────────


class TestResponseTimeTracking:
    def test_first_entry(self):
        a = _fresh_analytics()
        record_response_time("Alice", 12.0, a)
        assert "alice" in a["response_times"]
        assert a["response_times"]["alice"]["avg"] == 12.0
        assert a["response_times"]["alice"]["count"] == 1

    def test_running_average(self):
        a = _fresh_analytics()
        record_response_time("Alice", 10.0, a)
        record_response_time("Alice", 20.0, a)
        entry = a["response_times"]["alice"]
        assert entry["count"] == 2
        assert abs(entry["avg"] - 15.0) < 0.01

    def test_factor_fast_responder(self):
        a = _fresh_analytics()
        a["response_times"]["alice"] = {"avg": 2.0, "count": 5}
        assert get_response_time_factor("Alice", a) == 0

    def test_factor_slow_responder(self):
        a = _fresh_analytics()
        a["response_times"]["alice"] = {"avg": 30.0, "count": 5}
        assert get_response_time_factor("Alice", a) == 10

    def test_factor_insufficient_data(self):
        a = _fresh_analytics()
        a["response_times"]["alice"] = {"avg": 30.0, "count": 1}
        assert get_response_time_factor("Alice", a) == 0


# ── Escalation Detection ────────────────────────────────────────────────


class TestEscalationDetection:
    def test_create_first_mention(self):
        a = _fresh_analytics()
        record_mention("TASK-001", 1, a)
        assert len(a["escalation_history"]["TASK-001"]) == 1

    def test_append_mentions(self):
        a = _fresh_analytics()
        record_mention("TASK-001", 1, a)
        record_mention("TASK-001", 2, a)
        assert len(a["escalation_history"]["TASK-001"]) == 2

    def test_cap_at_five(self):
        a = _fresh_analytics()
        for i in range(7):
            record_mention("TASK-001", i, a)
        assert len(a["escalation_history"]["TASK-001"]) == 5

    def test_bonus_increasing_urgency(self):
        a = _fresh_analytics()
        a["escalation_history"] = {
            "TASK-001": [
                {"urgency": 1, "ts": "2026-01-01T00:00:00"},
                {"urgency": 2, "ts": "2026-01-02T00:00:00"},
                {"urgency": 3, "ts": "2026-01-03T00:00:00"},
            ]
        }
        bonus = get_escalation_bonus("TASK-001", a)
        assert bonus >= 8  # at least 2 increases

    def test_bonus_single_mention(self):
        a = _fresh_analytics()
        a["escalation_history"] = {
            "TASK-001": [{"urgency": 1, "ts": "2026-01-01T00:00:00"}]
        }
        assert get_escalation_bonus("TASK-001", a) == 0


# ── User Pins ────────────────────────────────────────────────────────────


class TestUserPins:
    def test_pin(self):
        a = _fresh_analytics()
        pin_task("TASK-001", a)
        assert "TASK-001" in a["user_pins"]

    def test_unpin(self):
        a = _fresh_analytics()
        pin_task("TASK-001", a)
        unpin_task("TASK-001", a)
        assert "TASK-001" not in a["user_pins"]

    def test_duplicate_pin(self):
        a = _fresh_analytics()
        pin_task("TASK-001", a)
        pin_task("TASK-001", a)
        assert a["user_pins"].count("TASK-001") == 1

    def test_unpin_not_found(self):
        a = _fresh_analytics()
        unpin_task("TASK-999", a)  # should not raise
        assert a["user_pins"] == []

    def test_bonus(self):
        a = _fresh_analytics()
        pin_task("TASK-001", a)
        assert get_pin_bonus("TASK-001", a) == 20
        assert get_pin_bonus("TASK-002", a) == 0


# ── Score Task with Analytics ────────────────────────────────────────────


class TestScoreTaskWithAnalytics:
    def test_backward_compat_no_analytics(self):
        config = _make_config()
        task = _make_task()
        score_task(task, config)  # no analytics param
        bd = task["score_breakdown"]
        assert bd["response_time"] == 0
        assert bd["escalation"] == 0
        assert bd["pin"] == 0

    def test_with_analytics_adds_components(self):
        config = _make_config()
        a = _fresh_analytics()
        a["response_times"]["alex morgan"] = {"avg": 30.0, "count": 5}
        task = _make_task()
        score_task(task, config, a)
        assert task["score_breakdown"]["response_time"] == 10

    def test_pin_bonus_in_score(self):
        config = _make_config()
        a = _fresh_analytics()
        pin_task("TASK-TEST", a)
        task = _make_task()
        score_task(task, config, a)
        assert task["score_breakdown"]["pin"] == 20

    def test_escalation_in_score(self):
        config = _make_config()
        a = _fresh_analytics()
        a["escalation_history"] = {
            "TASK-TEST": [
                {"urgency": 1, "ts": "2026-01-01T00:00:00"},
                {"urgency": 3, "ts": "2026-01-02T00:00:00"},
            ]
        }
        task = _make_task()
        score_task(task, config, a)
        assert task["score_breakdown"]["escalation"] > 0

    def test_cap_at_100(self):
        config = _make_config()
        config["stakeholders"]["alex morgan"]["weight"] = 10
        a = _fresh_analytics()
        a["response_times"]["alex morgan"] = {"avg": 50.0, "count": 10}
        pin_task("TASK-TEST", a)
        a["escalation_history"] = {
            "TASK-TEST": [
                {"urgency": 1, "ts": "t1"}, {"urgency": 2, "ts": "t2"},
                {"urgency": 3, "ts": "t3"}, {"urgency": 4, "ts": "t4"},
            ]
        }
        task = _make_task(
            title="urgent asap",
            created_days_ago=20,
            times_seen=10,
        )
        task["subtask_ids"] = ["T-1", "T-2", "T-3", "T-4"]
        task["source"] = "calendar"
        config["scoring"] = {"calendar_boost": 5}
        task["source_metadata"] = {"alternate_links": [{"source": "email", "link": "x"}]}
        score_task(task, config, a)
        assert task["score"] == 100


# ── Score All Tasks with Analytics ───────────────────────────────────────


class TestScoreAllTasksWithAnalytics:
    def test_passes_analytics_through(self, tmp_path):
        """score_all_tasks loads analytics and passes to score_task."""
        # Set up temp files
        import task_dashboard as td
        old_tasks = td.TASKS_PATH
        old_analytics = td.ANALYTICS_PATH
        td.TASKS_PATH = str(tmp_path / "tasks.json")
        td.ANALYTICS_PATH = str(tmp_path / "analytics.json")

        try:
            store = {"tasks": [_make_task(task_id="TASK-001")]}
            with open(td.TASKS_PATH, "w") as f:
                json.dump(store, f)
            analytics = _fresh_analytics()
            pin_task("TASK-001", analytics)
            with open(td.ANALYTICS_PATH, "w") as f:
                json.dump(analytics, f)

            config = _make_config()
            score_all_tasks(config)

            with open(td.TASKS_PATH) as f:
                result = json.load(f)
            assert result["tasks"][0]["score_breakdown"]["pin"] == 20
        finally:
            td.TASKS_PATH = old_tasks
            td.ANALYTICS_PATH = old_analytics

    def test_backward_compat_without_analytics(self, tmp_path):
        """score_all_tasks works when analytics.json doesn't exist."""
        import task_dashboard as td
        old_tasks = td.TASKS_PATH
        old_analytics = td.ANALYTICS_PATH
        td.TASKS_PATH = str(tmp_path / "tasks.json")
        td.ANALYTICS_PATH = str(tmp_path / "analytics_missing.json")

        try:
            store = {"tasks": [_make_task(task_id="TASK-001")]}
            with open(td.TASKS_PATH, "w") as f:
                json.dump(store, f)

            config = _make_config()
            score_all_tasks(config)

            with open(td.TASKS_PATH) as f:
                result = json.load(f)
            assert result["tasks"][0]["score_breakdown"]["pin"] == 0
            assert result["tasks"][0]["score_breakdown"]["response_time"] == 0
        finally:
            td.TASKS_PATH = old_tasks
            td.ANALYTICS_PATH = old_analytics
