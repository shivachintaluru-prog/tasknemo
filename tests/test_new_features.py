"""Tests for new features: agent framework, QA agent, new sources, dashboard improvements, priority."""

import sys
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    # New queries
    build_flagged_emails_query, build_planner_query, build_all_queries,
    # Scoring with mention boost
    score_task,
    # cmd_find
    cmd_find,
    # cmd_add with priority
    cmd_add,
    # Rendering
    render_dashboard_v2, _render_task_item_v2,
    _format_age,
    # State machine
    transition_task,
    # Store
    load_tasks, save_tasks, load_config, save_config,
)

from tasknemo.rendering import _compute_sync_health


def _make_task(**overrides):
    defaults = {
        "id": "TASK-100",
        "title": "Test task",
        "sender": "Test User",
        "state": "open",
        "score": 50,
        "score_breakdown": {},
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "source": "teams",
        "source_link": "",
        "source_metadata": {},
        "direction": "inbound",
        "parent_id": None,
        "subtask_ids": [],
        "thread_id": "",
        "times_seen": 1,
        "description": "",
        "due_hint": "",
    }
    defaults.update(overrides)
    return defaults


def _make_config(**overrides):
    defaults = {
        "stakeholders": {},
        "urgency_keywords": ["urgent", "asap"],
        "scoring": {"calendar_boost": 5, "manual_boost": 15},
        "user_name": "",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Step 2: Agent framework
# ---------------------------------------------------------------------------


class TestAgentFramework:
    def test_agent_registry_lists_agents(self):
        from tasknemo.agent.registry import get_registry
        registry = get_registry()
        agents = registry.list_agents()
        agent_ids = [a.agent_id for a in agents]
        assert "task_sync" in agent_ids
        assert "quality_eval" in agent_ids

    def test_agent_registry_get_agent(self):
        from tasknemo.agent.registry import get_registry
        registry = get_registry()
        agent = registry.get_agent("quality_eval")
        assert agent is not None
        assert agent.display_name == "Quality Evaluation"

    def test_agent_registry_get_nonexistent(self):
        from tasknemo.agent.registry import get_registry
        registry = get_registry()
        assert registry.get_agent("nonexistent") is None

    def test_agent_result_dataclass(self):
        from tasknemo.agent.base import AgentResult
        result = AgentResult(
            agent_id="test",
            started=datetime.now(),
            finished=datetime.now(),
            success=True,
            stats={"count": 5},
        )
        assert result.success
        assert result.stats["count"] == 5
        assert result.errors == []

    def test_agent_schedule(self):
        from tasknemo.agent.registry import get_registry
        registry = get_registry()
        qa = registry.get_agent("quality_eval")
        assert qa.get_schedule() == "daily 7:00"
        sync = registry.get_agent("task_sync")
        assert sync.get_schedule() == "every 30m"


# ---------------------------------------------------------------------------
# Step 3: Quality Evaluation Agent
# ---------------------------------------------------------------------------


class TestQualityEvalAgent:
    def test_run_returns_result(self):
        from tasknemo.agents.quality_eval.agent import QualityEvalAgent
        agent = QualityEvalAgent()
        result = agent.run({})
        assert result.agent_id == "quality_eval"
        assert result.success
        assert "total_tasks" in result.stats
        assert "total_issues" in result.stats

    def test_detects_duplicates(self):
        from tasknemo.agents.quality_eval.agent import QualityEvalAgent
        agent = QualityEvalAgent()

        with patch("tasknemo.agents.quality_eval.agent.QualityEvalAgent._render_report", return_value=""):
            with patch("tasknemo.store.load_tasks") as mock_load:
                with patch("tasknemo.store.load_run_log", return_value={"runs": []}):
                    with patch("tasknemo.store.load_config", return_value={"vault_path": ""}):
                        mock_load.return_value = {"tasks": [
                            _make_task(id="TASK-001", title="Review proposal from Alice",
                                       sender="Alice", state="open"),
                            _make_task(id="TASK-002", title="Review proposal from Alice please",
                                       sender="Alice", state="open"),
                        ]}
                        result = agent.run({})
                        assert result.stats.get("duplicates_found", 0) > 0

    def test_detects_score_anomalies(self):
        from tasknemo.agents.quality_eval.agent import QualityEvalAgent
        agent = QualityEvalAgent()

        with patch("tasknemo.agents.quality_eval.agent.QualityEvalAgent._render_report", return_value=""):
            with patch("tasknemo.store.load_tasks") as mock_load:
                with patch("tasknemo.store.load_run_log", return_value={"runs": []}):
                    with patch("tasknemo.store.load_config", return_value={"vault_path": ""}):
                        mock_load.return_value = {"tasks": [
                            _make_task(id="TASK-001", score=0, state="open"),
                            _make_task(id="TASK-002", score=100, state="open"),
                            _make_task(id="TASK-003", score=50, state="open"),
                        ]}
                        result = agent.run({})
                        assert result.stats.get("score_anomalies", 0) == 2

    def test_report_rendering(self):
        from tasknemo.agents.quality_eval.agent import QualityEvalAgent
        agent = QualityEvalAgent()
        stats = {"total_tasks": 10, "active_tasks": 5, "total_issues": 2}
        issues = [
            {"category": "duplicate", "severity": "medium",
             "description": "TASK-001 and TASK-002", "task_ids": ["TASK-001", "TASK-002"]},
            {"category": "stale", "severity": "low",
             "description": "TASK-003 is old", "task_ids": ["TASK-003"]},
        ]
        report = agent._render_report(stats, issues, {})
        assert "Quality Report" in report
        assert "Potential Duplicates" in report
        assert "Stale Open Items" in report
        assert "Recommendations" in report


# ---------------------------------------------------------------------------
# Step 4: New sources
# ---------------------------------------------------------------------------


class TestNewSources:
    def test_flagged_emails_query(self):
        q = build_flagged_emails_query("March 10, 2026")
        assert "flagged" in q.lower() or "starred" in q.lower()

    def test_planner_query(self):
        q = build_planner_query("March 10, 2026")
        assert "planner" in q.lower() or "to-do" in q.lower()

    def test_build_all_queries_includes_flagged_when_enabled(self):
        config = {"sources_enabled": ["teams", "email", "flagged_email"],
                  "query_strategy": "two_phase"}
        result = build_all_queries("March 10, 2026", config)
        assert "flagged_emails" in result

    def test_build_all_queries_includes_planner_when_enabled(self):
        config = {"sources_enabled": ["teams", "planner"],
                  "query_strategy": "two_phase"}
        result = build_all_queries("March 10, 2026", config)
        assert "planner" in result

    def test_build_all_queries_excludes_flagged_when_disabled(self):
        config = {"sources_enabled": ["teams", "email"],
                  "query_strategy": "two_phase"}
        result = build_all_queries("March 10, 2026", config)
        assert "flagged_emails" not in result


# ---------------------------------------------------------------------------
# Step 4c: Mention boost in scoring
# ---------------------------------------------------------------------------


class TestMentionBoost:
    def test_mention_boost_detected(self):
        task = _make_task(title="@mention me in the doc", description="tagged you in review")
        config = _make_config()
        score_task(task, config)
        assert task["score_breakdown"]["mention_boost"] == 15

    def test_no_mention_boost_without_pattern(self):
        task = _make_task(title="Review the proposal")
        config = _make_config()
        score_task(task, config)
        assert task["score_breakdown"]["mention_boost"] == 0


# ---------------------------------------------------------------------------
# Step 5a: Closed by Me
# ---------------------------------------------------------------------------


class TestClosedByMe:
    def test_cmd_close_sets_closed_by_user(self, monkeypatch):
        task = _make_task(id="TASK-001", state="open")
        store = {"tasks": [task]}
        saved = []
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: saved.append(s))

        from task_dashboard import cmd_close
        cmd_close("TASK-001")
        assert task.get("closed_by") == "user"

    def test_render_v2_shows_closed_by_me_section(self):
        now = datetime.now()
        tasks = [
            _make_task(id="TASK-001", state="closed", closed_by="user",
                       updated=now.isoformat()),
            _make_task(id="TASK-002", state="closed",
                       updated=now.isoformat()),
        ]
        config = _make_config(last_run=now.isoformat(), vault_path="")
        with patch("tasknemo.rendering.load_analytics", return_value={}):
            with patch("tasknemo.rendering.load_run_log", return_value={"runs": []}):
                md = render_dashboard_v2(tasks, config)
        assert "Closed by Me" in md


# ---------------------------------------------------------------------------
# Step 5b: Sync health
# ---------------------------------------------------------------------------


class TestSyncHealth:
    def test_sync_health_recent_run(self):
        now = datetime.now()
        with patch("tasknemo.rendering.load_run_log") as mock:
            mock.return_value = {"runs": [
                {"timestamp": now.isoformat()},
            ]}
            result = _compute_sync_health({})
        assert "Sync:" in result
        assert "1 runs today" in result

    def test_sync_health_no_runs(self):
        with patch("tasknemo.rendering.load_run_log") as mock:
            mock.return_value = {"runs": []}
            result = _compute_sync_health({})
        assert result == ""


# ---------------------------------------------------------------------------
# Step 5c: cmd_find
# ---------------------------------------------------------------------------


class TestCmdFind:
    def test_find_by_keyword(self, monkeypatch, capsys):
        tasks = [
            _make_task(id="TASK-001", title="Review proposal"),
            _make_task(id="TASK-002", title="Send report"),
        ]
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: {"tasks": tasks})
        cmd_find(query="proposal")
        output = capsys.readouterr().out
        assert "TASK-001" in output
        assert "TASK-002" not in output

    def test_find_by_sender(self, monkeypatch, capsys):
        tasks = [
            _make_task(id="TASK-001", sender="Alice"),
            _make_task(id="TASK-002", sender="Bob"),
        ]
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: {"tasks": tasks})
        cmd_find(sender="Alice")
        output = capsys.readouterr().out
        assert "TASK-001" in output
        assert "TASK-002" not in output

    def test_find_no_results(self, monkeypatch, capsys):
        tasks = [_make_task(id="TASK-001", title="Something")]
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: {"tasks": tasks})
        cmd_find(query="nonexistent")
        output = capsys.readouterr().out
        assert "No matching tasks found" in output


# ---------------------------------------------------------------------------
# Step 5d: Dashboard UX polish
# ---------------------------------------------------------------------------


class TestDashboardPolish:
    def test_v2_no_confidence_in_render(self):
        task = _make_task(score=50)
        result = _render_task_item_v2(task)
        assert "Conf:" not in result
        assert "Priority:" not in result

    def test_v2_task_count_in_sections(self):
        tasks = [
            _make_task(id="TASK-001", state="open", score=80),
            _make_task(id="TASK-002", state="open", score=70),
        ]
        config = _make_config(last_run=datetime.now().isoformat(), vault_path="")
        with patch("tasknemo.rendering.load_analytics", return_value={}):
            with patch("tasknemo.rendering.load_run_log", return_value={"runs": []}):
                md = render_dashboard_v2(tasks, config)
        assert "tasks)" in md

    def test_v2_no_per_container_cap(self):
        """All tasks in a container should render (no 10-task cap)."""
        tasks = [_make_task(
            id=f"TASK-{i:03d}", state="open", score=20,
            thread_id="thread123", sender="Alice",
            title=f"Task number {i}"
        ) for i in range(15)]
        config = _make_config(last_run=datetime.now().isoformat(), vault_path="")
        with patch("tasknemo.rendering.load_analytics", return_value={}):
            with patch("tasknemo.rendering.load_run_log", return_value={"runs": []}):
                md = render_dashboard_v2(tasks, config)
        # All 15 tasks should appear (since we removed the cap)
        for i in range(15):
            assert f"TASK-{i:03d}" in md


# ---------------------------------------------------------------------------
# Step 6: Manual priority on add
# ---------------------------------------------------------------------------


class TestManualPriority:
    def test_cmd_add_with_priority(self, monkeypatch):
        store = {"tasks": []}
        config = {"next_task_id": 1, "scoring": {"manual_boost": 15}, "stakeholders": {}, "urgency_keywords": []}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)
        monkeypatch.setattr("task_dashboard.load_config", lambda: config)
        monkeypatch.setattr("task_dashboard.save_config", lambda c: None)

        task_id = cmd_add("High priority task", priority="high")
        assert task_id == "TASK-001"
        # Check the task was created with user_priority
        created = store["tasks"][0]
        assert created.get("user_priority") == 20

    def test_score_includes_user_priority(self):
        task = _make_task(user_priority=20, source="manual")
        config = _make_config()
        score_task(task, config)
        assert task["score_breakdown"]["user_priority_boost"] == 20

    def test_priority_medium(self, monkeypatch):
        store = {"tasks": []}
        config = {"next_task_id": 1, "scoring": {"manual_boost": 15}, "stakeholders": {}, "urgency_keywords": []}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)
        monkeypatch.setattr("task_dashboard.load_config", lambda: config)
        monkeypatch.setattr("task_dashboard.save_config", lambda c: None)

        cmd_add("Medium task", priority="medium")
        assert store["tasks"][0].get("user_priority") == 10

    def test_priority_low(self, monkeypatch):
        store = {"tasks": []}
        config = {"next_task_id": 1, "scoring": {"manual_boost": 15}, "stakeholders": {}, "urgency_keywords": []}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)
        monkeypatch.setattr("task_dashboard.load_config", lambda: config)
        monkeypatch.setattr("task_dashboard.save_config", lambda c: None)

        cmd_add("Low task", priority="low")
        assert store["tasks"][0].get("user_priority") == 0
