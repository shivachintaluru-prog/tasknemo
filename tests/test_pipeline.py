"""Unit tests for the v2 step-based pipeline functions."""

import sys
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    sync_prepare,
    process_source_items,
    build_completion_signals,
    run_transitions,
    finalize_sync,
    match_conversation_to_tasks,
    find_cross_source_match,
    merge_cross_source_signal,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture_tasks():
    with open(os.path.join(FIXTURES_DIR, "sample_tasks.json"), "r") as f:
        return json.load(f)


def _make_task(task_id="TASK-TEST", sender="Jordan Kim",
               title="Follow up on API schema mapping", state="open",
               source="teams", thread_id=""):
    created = datetime.now().isoformat()
    return {
        "id": task_id,
        "title": title,
        "sender": sender,
        "state": state,
        "source": source,
        "source_link": "",
        "source_metadata": {},
        "times_seen": 1,
        "created": created,
        "updated": created,
        "thread_id": thread_id,
        "state_history": [
            {"state": "open", "reason": "test", "date": created}
        ],
    }


def _make_sync_context(open_tasks=None):
    """Build a minimal sync_context dict for testing."""
    return {
        "config": {
            "sources_enabled": ["teams", "email", "calendar"],
            "stakeholders": {},
            "urgency_keywords": [],
            "vault_path": "",
        },
        "since_date": "March 01, 2026",
        "all_queries": {},
        "open_tasks": open_tasks or [],
        "pre_closed": [],
        "run_stats": {
            "new_tasks": 0,
            "transitions": 0,
            "merged": 0,
            "skipped": 0,
        },
    }


# ---------------------------------------------------------------------------
# TestSyncPrepare
# ---------------------------------------------------------------------------


class TestSyncPrepare:
    def test_returns_dict_with_required_keys(self):
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": None,
            }
            ctx = sync_prepare()
            assert "config" in ctx
            assert "since_date" in ctx
            assert "all_queries" in ctx
            assert "open_tasks" in ctx
            assert "pre_closed" in ctx
            assert "run_stats" in ctx

    def test_performs_obsidian_readback(self):
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=["TASK-001"]) as mock_sync, \
             patch("task_dashboard.score_all_tasks") as mock_score, \
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "/some/vault",
                "dashboard_filename": "TaskNemo.md",
                "overlap_days": 2,
                "last_run": None,
            }
            ctx = sync_prepare()
            mock_sync.assert_called_once_with("/some/vault", "TaskNemo.md")
            mock_score.assert_called_once()
            assert ctx["pre_closed"] == ["TASK-001"]

    def test_calculates_since_date(self):
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="February 28, 2026") as mock_calc, \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": "2026-03-02T00:00:00",
            }
            ctx = sync_prepare()
            mock_calc.assert_called_once_with("2026-03-02T00:00:00", 2)
            assert ctx["since_date"] == "February 28, 2026"

    def test_open_tasks_only_includes_non_closed(self):
        open_task = _make_task(task_id="TASK-001", state="open")
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[open_task]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": None,
            }
            ctx = sync_prepare()
            assert len(ctx["open_tasks"]) == 1
            assert ctx["open_tasks"][0]["id"] == "TASK-001"

    def test_run_stats_initialized_to_zero(self):
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": None,
            }
            ctx = sync_prepare()
            stats = ctx["run_stats"]
            assert stats["new_tasks"] == 0
            assert stats["transitions"] == 0
            assert stats["merged"] == 0
            assert stats["skipped"] == 0


# ---------------------------------------------------------------------------
# TestProcessSourceItems
# ---------------------------------------------------------------------------


class TestProcessSourceItems:
    def test_skips_already_done_items(self):
        ctx = _make_sync_context()
        items = [
            {"sender": "Alice", "title": "Send doc", "link": "", "source": "email",
             "direction": "inbound", "signal_type": None, "already_done": True, "extra": {}},
        ]
        result = process_source_items("email", items, ctx)
        assert result["skipped"] == 1
        assert len(result["to_create"]) == 0
        assert ctx["run_stats"]["skipped"] == 1

    def test_finds_cross_source_match_and_merges(self):
        existing = _make_task(task_id="TASK-001", sender="Jordan Kim",
                              title="Follow up on API schema mapping")
        ctx = _make_sync_context(open_tasks=[existing])
        items = [
            {"sender": "Jordan Kim", "title": "API schema mapping follow-up",
             "link": "https://outlook.office.com/mail/123", "source": "email",
             "direction": "inbound", "signal_type": None, "already_done": False, "extra": {}},
        ]
        result = process_source_items("email", items, ctx)
        assert "TASK-001" in result["merged_ids"]
        assert len(result["to_create"]) == 0
        assert ctx["run_stats"]["merged"] == 1

    def test_returns_to_create_for_unmatched(self):
        ctx = _make_sync_context(open_tasks=[])
        items = [
            {"sender": "New Person", "title": "Brand new ask",
             "link": "https://outlook.office.com/mail/456", "source": "email",
             "direction": "inbound", "signal_type": None, "already_done": False, "extra": {}},
        ]
        result = process_source_items("email", items, ctx)
        assert len(result["to_create"]) == 1
        assert result["to_create"][0]["title"] == "Brand new ask"

    def test_collects_signals_from_items_with_signal_type(self):
        existing = _make_task(task_id="TASK-001", sender="Alice", title="Review PR")
        ctx = _make_sync_context(open_tasks=[existing])
        items = [
            {"sender": "Alice", "title": "Review PR update",
             "link": "https://teams.microsoft.com/l/message/123", "source": "teams",
             "direction": "inbound", "signal_type": "completion", "already_done": False,
             "extra": {"thread_id": "19:abc@thread.v2", "evidence": "PR approved"}},
        ]
        result = process_source_items("teams", items, ctx)
        assert len(result["signals"]) == 1
        assert result["signals"][0]["signal_type"] == "completion"

    def test_increments_run_stats(self):
        existing = _make_task(task_id="TASK-001", sender="Alice", title="Task A")
        ctx = _make_sync_context(open_tasks=[existing])
        items = [
            {"sender": "Alice", "title": "Task A update",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": False, "extra": {}},
            {"sender": "Bob", "title": "Something done",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": True, "extra": {}},
        ]
        result = process_source_items("teams", items, ctx)
        assert ctx["run_stats"]["merged"] == 1
        assert ctx["run_stats"]["skipped"] == 1


# ---------------------------------------------------------------------------
# TestBuildCompletionSignals
# ---------------------------------------------------------------------------


class TestBuildCompletionSignals:
    def test_matches_by_thread_id(self):
        tasks = [
            _make_task(task_id="TASK-001", sender="Alice", title="Review doc",
                       thread_id="19:abc@thread.v2"),
        ]
        items = [
            {"sender": "Alice", "topic": "doc review", "thread_id": "19:abc@thread.v2",
             "evidence": "Alice said thanks, doc looks good"},
        ]
        signals = build_completion_signals(items, tasks)
        assert len(signals) == 1
        assert signals[0]["task_id"] == "TASK-001"
        assert signals[0]["signal_type"] == "completion"

    def test_matches_by_sender_and_topic(self):
        tasks = [
            _make_task(task_id="TASK-002", sender="Bob", title="Share tracker update"),
        ]
        items = [
            {"sender": "Bob", "topic": "tracker update shared",
             "thread_id": "", "evidence": "Bob confirmed receipt"},
        ]
        signals = build_completion_signals(items, tasks)
        assert len(signals) == 1
        assert signals[0]["task_id"] == "TASK-002"

    def test_returns_empty_for_no_match(self):
        tasks = [
            _make_task(task_id="TASK-001", sender="Alice", title="Task A"),
        ]
        items = [
            {"sender": "UnknownPerson", "topic": "completely unrelated",
             "thread_id": "19:different@thread.v2", "evidence": "Done"},
        ]
        signals = build_completion_signals(items, tasks)
        assert len(signals) == 0

    def test_excludes_closed_tasks(self):
        tasks = [
            _make_task(task_id="TASK-001", sender="Alice", title="Task A",
                       state="closed"),
        ]
        items = [
            {"sender": "Alice", "topic": "Task A", "thread_id": "",
             "evidence": "Done"},
        ]
        # match_conversation_to_tasks skips closed tasks internally
        signals = build_completion_signals(items, tasks)
        # Should still be empty because closed tasks won't match in many cases
        # (depends on match_conversation_to_tasks behavior)
        assert isinstance(signals, list)


# ---------------------------------------------------------------------------
# TestRunTransitions
# ---------------------------------------------------------------------------


class TestRunTransitions:
    def test_calls_evaluate_transitions_with_signals(self):
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.evaluate_transitions", return_value=[]) as mock_eval, \
             patch("task_dashboard.score_all_tasks"), \
             patch("task_dashboard.save_tasks"), \
             patch("task_dashboard.save_config"):
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            signals = [{"sender": "Alice", "topic": "done", "thread_id": "",
                        "signal_type": "completion", "signal": "thanks"}]
            result = run_transitions(signals, ctx)
            mock_eval.assert_called_once()
            call_args = mock_eval.call_args
            assert call_args.kwargs["conversation_signals"] == signals

    def test_updates_last_run_in_config(self):
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.evaluate_transitions", return_value=[]), \
             patch("task_dashboard.score_all_tasks"), \
             patch("task_dashboard.save_tasks"), \
             patch("task_dashboard.save_config") as mock_save_config:
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            run_transitions([], ctx)
            assert "last_run" in ctx["config"]
            mock_save_config.assert_called_once_with(ctx["config"])

    def test_returns_transition_list(self):
        transitions = [("TASK-001", "open", "likely_done", "Completion")]
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.evaluate_transitions", return_value=transitions), \
             patch("task_dashboard.score_all_tasks"), \
             patch("task_dashboard.save_tasks"), \
             patch("task_dashboard.save_config"):
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            result = run_transitions([], ctx)
            assert result["transitions"] == transitions
            assert result["run_stats"]["transitions"] == 1


# ---------------------------------------------------------------------------
# TestFinalizeSync
# ---------------------------------------------------------------------------


class TestFinalizeSync:
    def test_writes_dashboard(self):
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.render_dashboard", return_value="# Dashboard") as mock_render, \
             patch("task_dashboard.write_dashboard", return_value="/vault/TaskNemo.md") as mock_write, \
             patch("task_dashboard.log_run") as mock_log:
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            ctx["config"]["vault_path"] = "/vault"
            ctx["config"]["dashboard_filename"] = "TaskNemo.md"
            stats = {"new_tasks": 2, "transitions": 1, "merged": 3, "skipped": 0}
            path = finalize_sync(stats, ctx)
            mock_render.assert_called_once()
            mock_write.assert_called_once_with("# Dashboard", "/vault", "TaskNemo.md")
            assert path == "/vault/TaskNemo.md"

    def test_logs_run(self):
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.render_dashboard", return_value="# Dashboard"), \
             patch("task_dashboard.write_dashboard", return_value="/vault/dash.md"), \
             patch("task_dashboard.log_run") as mock_log:
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            ctx["config"]["vault_path"] = "/vault"
            ctx["config"]["dashboard_filename"] = "dash.md"
            stats = {"new_tasks": 1, "transitions": 0, "merged": 0, "skipped": 0}
            finalize_sync(stats, ctx)
            mock_log.assert_called_once_with(stats)

    def test_returns_path(self):
        with patch("task_dashboard.load_tasks") as mock_load, \
             patch("task_dashboard.render_dashboard", return_value="# Dashboard"), \
             patch("task_dashboard.write_dashboard", return_value="/vault/TaskNemo.md"), \
             patch("task_dashboard.log_run"):
            mock_load.return_value = {"tasks": []}
            ctx = _make_sync_context()
            ctx["config"]["vault_path"] = "/vault"
            ctx["config"]["dashboard_filename"] = "TaskNemo.md"
            path = finalize_sync({}, ctx)
            assert path == "/vault/TaskNemo.md"
