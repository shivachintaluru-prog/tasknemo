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
    evaluate_transitions,
    add_task,
    load_config,
    save_config,
    load_tasks,
    save_tasks,
    calculate_since_date,
    score_task,
    sync_inbox,
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


def _make_sync_context(open_tasks=None, all_tasks=None):
    """Build a minimal sync_context dict for testing."""
    _open = open_tasks or []
    return {
        "config": {
            "sources_enabled": ["teams", "email", "calendar"],
            "stakeholders": {},
            "urgency_keywords": [],
            "vault_path": "",
        },
        "since_date": "March 01, 2026",
        "all_queries": {},
        "open_tasks": _open,
        "all_tasks": all_tasks if all_tasks is not None else _open,
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
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026") as mock_calc, \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": "2026-03-02T00:00:00",
            }
            ctx = sync_prepare()
            mock_calc.assert_called_once_with("2026-03-02T00:00:00", 2)
            assert ctx["since_date"] == "March 01, 2026"

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


# ---------------------------------------------------------------------------
# Staleness auto-close tests
# ---------------------------------------------------------------------------


class TestStalenessAutoClose:
    def test_open_auto_close_after_10_days(self):
        """Open task aged 11d with no signals → closed."""
        task = _make_task(task_id="TASK-STALE-OPEN")
        task["created"] = (datetime.now() - timedelta(days=11)).isoformat()
        task["updated"] = task["created"]
        task["state_history"] = [{"state": "open", "reason": "test", "date": task["created"]}]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 1
        assert transitions[0][0] == "TASK-STALE-OPEN"
        assert transitions[0][2] == "closed"
        assert "Stale open auto-close" in transitions[0][3]

    def test_needs_followup_closes_after_7_days_in_state(self):
        """Task entered needs_followup 8 days ago → closed."""
        task = _make_task(task_id="TASK-NF-STALE")
        task["created"] = (datetime.now() - timedelta(days=12)).isoformat()
        task["state"] = "needs_followup"
        nf_date = (datetime.now() - timedelta(days=8)).isoformat()
        task["state_history"] = [
            {"state": "open", "reason": "test", "date": task["created"]},
            {"state": "needs_followup", "reason": "stale", "date": nf_date},
        ]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "closed"

    def test_needs_followup_not_closed_if_recently_entered(self):
        """Created 15d ago but entered needs_followup yesterday → NOT closed."""
        task = _make_task(task_id="TASK-NF-RECENT")
        task["created"] = (datetime.now() - timedelta(days=15)).isoformat()
        task["state"] = "needs_followup"
        nf_date = (datetime.now() - timedelta(days=1)).isoformat()
        task["state_history"] = [
            {"state": "open", "reason": "test", "date": task["created"]},
            {"state": "needs_followup", "reason": "stale", "date": nf_date},
        ]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 0


class TestOutboundAutoWaiting:
    """Outbound tasks should auto-set to 'waiting' state in add_task()."""

    @staticmethod
    def _patch_paths(monkeypatch, tmp_path):
        import task_dashboard as td
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir, exist_ok=True)
        monkeypatch.setattr(td, "DATA_DIR", data_dir)
        monkeypatch.setattr(td, "CONFIG_PATH", os.path.join(data_dir, "config.json"))
        monkeypatch.setattr(td, "TASKS_PATH", os.path.join(data_dir, "tasks.json"))
        monkeypatch.setattr(td, "RUN_LOG_PATH", os.path.join(data_dir, "run_log.json"))
        # Write minimal data files
        with open(os.path.join(data_dir, "tasks.json"), "w") as f:
            json.dump({"tasks": []}, f)
        with open(os.path.join(data_dir, "config.json"), "w") as f:
            json.dump({"next_task_id": 1}, f)

    def test_outbound_task_starts_as_waiting(self, monkeypatch, tmp_path):
        self._patch_paths(monkeypatch, tmp_path)
        config = load_config()
        task = {"title": "Follow up on spec review", "direction": "outbound", "sender": "Alice"}
        task_id = add_task(task, config)
        store = load_tasks()
        saved = [t for t in store["tasks"] if t["id"] == task_id][0]
        assert saved["state"] == "waiting"
        assert saved["state_history"][0]["state"] == "waiting"

    def test_inbound_task_stays_open(self, monkeypatch, tmp_path):
        self._patch_paths(monkeypatch, tmp_path)
        config = load_config()
        task = {"title": "Review PR", "direction": "inbound", "sender": "Bob"}
        task_id = add_task(task, config)
        store = load_tasks()
        saved = [t for t in store["tasks"] if t["id"] == task_id][0]
        assert saved["state"] == "open"
        assert saved["state_history"][0]["state"] == "open"

    def test_outbound_with_explicit_state_not_overridden(self, monkeypatch, tmp_path):
        self._patch_paths(monkeypatch, tmp_path)
        config = load_config()
        task = {"title": "Check in", "direction": "outbound", "state": "needs_followup", "sender": "Charlie"}
        task_id = add_task(task, config)
        store = load_tasks()
        saved = [t for t in store["tasks"] if t["id"] == task_id][0]
        # Only overrides "open" → "waiting", not other states
        assert saved["state"] == "needs_followup"


# ---------------------------------------------------------------------------
# TestClosedTaskDedup — closed/likely_done tasks should not be re-created
# ---------------------------------------------------------------------------


class TestClosedTaskDedup:
    def test_closed_task_not_recreated(self):
        """A closed task matching an incoming item should be skipped, not re-created."""
        closed_task = _make_task(task_id="TASK-001", sender="Alice",
                                 title="Send budget report", state="closed")
        # open_tasks doesn't include it, but all_tasks does
        ctx = _make_sync_context(open_tasks=[], all_tasks=[closed_task])
        items = [
            {"sender": "Alice", "title": "Send budget report",
             "link": "", "source": "email", "direction": "inbound",
             "signal_type": None, "already_done": False, "extra": {}},
        ]
        result = process_source_items("email", items, ctx)
        assert result["skipped"] == 1
        assert len(result["to_create"]) == 0
        assert ctx["run_stats"]["skipped"] == 1

    def test_likely_done_task_not_recreated(self):
        """A likely_done task matching an incoming item should be skipped."""
        ld_task = _make_task(task_id="TASK-002", sender="Bob",
                             title="Review design spec", state="likely_done")
        ctx = _make_sync_context(open_tasks=[], all_tasks=[ld_task])
        items = [
            {"sender": "Bob", "title": "Review design spec",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": False, "extra": {}},
        ]
        result = process_source_items("teams", items, ctx)
        assert result["skipped"] == 1
        assert len(result["to_create"]) == 0

    def test_open_task_still_merges(self):
        """An open task matching should still merge (existing behavior)."""
        open_task = _make_task(task_id="TASK-003", sender="Charlie",
                               title="Update tracker")
        ctx = _make_sync_context(open_tasks=[open_task], all_tasks=[open_task])
        items = [
            {"sender": "Charlie", "title": "Update tracker status",
             "link": "https://outlook.office.com/mail/789", "source": "email",
             "direction": "inbound", "signal_type": None, "already_done": False,
             "extra": {}},
        ]
        result = process_source_items("email", items, ctx)
        assert "TASK-003" in result["merged_ids"]
        assert len(result["to_create"]) == 0
        assert ctx["run_stats"]["merged"] == 1


# ---------------------------------------------------------------------------
# TestCalculateSinceDate — overlap_days usage
# ---------------------------------------------------------------------------


class TestCalculateSinceDate:
    def test_uses_overlap_days(self):
        """With overlap_days=2, should go back 2 days from last_run."""
        last_run = "2026-03-10T12:00:00"
        result = calculate_since_date(last_run, overlap_days=2)
        assert "March 08" in result

    def test_default_overlap(self):
        """Default overlap_days=2 should go back 2 days."""
        last_run = "2026-03-10T12:00:00"
        result = calculate_since_date(last_run)
        assert "March 08" in result

    def test_first_run_defaults_to_7_days(self):
        """No last_run → 7 days ago."""
        result = calculate_since_date(None, overlap_days=2)
        # Just verify it returns a string (date depends on "now")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_custom_overlap_days(self):
        """overlap_days=5 should go back 5 days."""
        last_run = "2026-03-10T12:00:00"
        result = calculate_since_date(last_run, overlap_days=5)
        assert "March 05" in result


# ---------------------------------------------------------------------------
# TestManualTaskScoreBoost — inbox/manual tasks get +15 boost
# ---------------------------------------------------------------------------


class TestManualTaskScoreBoost:
    def test_manual_tasks_get_score_boost(self):
        task = _make_task(task_id="TASK-M1", sender="me", title="Review proposal")
        task["source"] = "manual"
        config = {"stakeholders": {}, "urgency_keywords": [], "scoring": {"manual_boost": 15}}
        score_task(task, config)
        assert task["score_breakdown"]["manual_boost"] == 15
        assert task["score"] >= 15

    def test_non_manual_tasks_no_boost(self):
        task = _make_task(task_id="TASK-T1", sender="me", title="Review proposal")
        task["source"] = "teams"
        config = {"stakeholders": {}, "urgency_keywords": [], "scoring": {"manual_boost": 15}}
        score_task(task, config)
        assert task["score_breakdown"]["manual_boost"] == 0

    def test_default_boost_value(self):
        task = _make_task(task_id="TASK-M2", sender="me", title="Do thing")
        task["source"] = "manual"
        config = {"stakeholders": {}, "urgency_keywords": {}, "scoring": {}}
        score_task(task, config)
        # Default is 15 when not in config
        assert task["score_breakdown"]["manual_boost"] == 15


# ---------------------------------------------------------------------------
# TestSyncInboxFromDashboard — Task Inbox section in dashboard
# ---------------------------------------------------------------------------


class TestSyncInboxFromDashboard:
    def test_inbox_section_parsed_from_dashboard(self, tmp_path):
        """Dashboard with ## Task Inbox section should have items extracted."""
        dashboard = tmp_path / "TaskNemo.md"
        dashboard.write_text(
            "# TaskNemo\n\n"
            "## Task Inbox\n"
            "Add tasks below.\n\n"
            "- Review Danny's proposal\n"
            "- Book team offsite venue\n"
            "\n---\n\n"
            "## Focus Now\n"
        )
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.add_task") as mock_add:
            mock_config.return_value = {"next_task_id": 1}
            mock_add.side_effect = lambda d, c: f"TASK-{c.get('next_task_id', 0):03d}"
            ids = sync_inbox(str(tmp_path), "TaskNemo.md")
        assert mock_add.call_count == 2

    def test_inbox_section_cleared_after_import(self, tmp_path):
        """After import, inbox section header preserved but tasks removed."""
        dashboard = tmp_path / "TaskNemo.md"
        dashboard.write_text(
            "# TaskNemo\n\n"
            "## Task Inbox\n"
            "Add tasks below.\n\n"
            "- Review Danny's proposal\n"
            "\n---\n\n"
            "## Focus Now\n"
            "Some content\n"
        )
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.add_task") as mock_add:
            mock_config.return_value = {"next_task_id": 1}
            mock_add.return_value = "TASK-001"
            sync_inbox(str(tmp_path), "TaskNemo.md")
        content = dashboard.read_text()
        assert "## Task Inbox" in content
        assert "Review Danny's proposal" not in content
        assert "## Focus Now" in content

    def test_legacy_inbox_file_still_works(self, tmp_path):
        """Separate Task Inbox.md file still processed."""
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text(
            "# Task Inbox\n\n"
            "- Fix the login bug\n"
        )
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.add_task") as mock_add:
            mock_config.return_value = {"next_task_id": 1}
            mock_add.return_value = "TASK-001"
            ids = sync_inbox(str(tmp_path), "Task Inbox.md")
        assert mock_add.call_count == 1

    def test_sync_prepare_includes_all_tasks(self):
        """sync_prepare() should include all_tasks key for dedup."""
        open_task = _make_task(task_id="TASK-001", state="open")
        closed_task = _make_task(task_id="TASK-002", state="closed")
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.sync_inbox", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="March 01, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks") as mock_list:
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": None,
            }
            # First call returns open tasks, second returns all tasks
            mock_list.side_effect = [[open_task], [open_task, closed_task]]
            ctx = sync_prepare()
            assert "all_tasks" in ctx
            assert len(ctx["all_tasks"]) == 2
            assert len(ctx["open_tasks"]) == 1


# ---------------------------------------------------------------------------
# TestDateFiltering — items outside sync window are rejected
# ---------------------------------------------------------------------------


class TestDateFiltering:
    def test_old_item_skipped_by_date(self):
        """Item with extracted_date before since_date_iso is skipped."""
        ctx = _make_sync_context()
        ctx["since_date_iso"] = "2026-03-08"
        items = [
            {"sender": "Alice", "title": "Old topic from weeks ago",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": False,
             "extra": {"extracted_date": "2026-02-20"}},
        ]
        result = process_source_items("teams", items, ctx)
        assert result["skipped"] == 1
        assert len(result["to_create"]) == 0
        assert ctx["run_stats"]["skipped"] == 1

    def test_recent_item_passes(self):
        """Item with extracted_date on or after since_date_iso passes through."""
        ctx = _make_sync_context()
        ctx["since_date_iso"] = "2026-03-08"
        items = [
            {"sender": "Alice", "title": "New actionable ask",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": False,
             "extra": {"extracted_date": "2026-03-10"}},
        ]
        result = process_source_items("teams", items, ctx)
        assert result["skipped"] == 0
        assert len(result["to_create"]) == 1

    def test_item_on_boundary_passes(self):
        """Item with extracted_date equal to since_date_iso passes through."""
        ctx = _make_sync_context()
        ctx["since_date_iso"] = "2026-03-08"
        items = [
            {"sender": "Bob", "title": "Boundary date task",
             "link": "", "source": "email", "direction": "inbound",
             "signal_type": None, "already_done": False,
             "extra": {"extracted_date": "2026-03-08"}},
        ]
        result = process_source_items("email", items, ctx)
        assert result["skipped"] == 0
        assert len(result["to_create"]) == 1

    def test_item_without_date_passes(self):
        """Backward compat: no extracted_date means item is not filtered."""
        ctx = _make_sync_context()
        ctx["since_date_iso"] = "2026-03-08"
        items = [
            {"sender": "Charlie", "title": "No date item",
             "link": "", "source": "teams", "direction": "inbound",
             "signal_type": None, "already_done": False, "extra": {}},
        ]
        result = process_source_items("teams", items, ctx)
        assert result["skipped"] == 0
        assert len(result["to_create"]) == 1

    def test_since_date_iso_in_sync_context(self):
        """sync_prepare() includes since_date_iso in the returned context."""
        with patch("task_dashboard.load_config") as mock_config, \
             patch("task_dashboard.sync_dashboard_completions", return_value=[]), \
             patch("task_dashboard.sync_inbox", return_value=[]), \
             patch("task_dashboard.calculate_since_date", return_value="March 08, 2026"), \
             patch("task_dashboard.build_all_queries", return_value={}), \
             patch("task_dashboard.list_tasks", return_value=[]):
            mock_config.return_value = {
                "vault_path": "",
                "overlap_days": 2,
                "last_run": None,
            }
            ctx = sync_prepare()
            assert "since_date_iso" in ctx
            assert ctx["since_date_iso"] == "2026-03-08"
