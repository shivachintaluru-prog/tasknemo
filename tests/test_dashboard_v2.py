"""Unit tests for dashboard v2 rendering — helpers, render functions, and version toggle."""

import sys
import os
import json
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    _compute_idle_days,
    parse_due_hint,
    _is_due_within,
    _compute_confidence,
    classify_task_type,
    TASK_TYPES,
    _generate_next_action,
    _compute_focus_priority,
    _render_task_item_v2,
    render_dashboard_v2,
    render_dashboard,
    render_dashboard_v1,
    _extract_container_key,
)


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture_tasks():
    with open(os.path.join(FIXTURES_DIR, "sample_tasks.json"), "r") as f:
        return json.load(f)["tasks"]


def _make_config(**overrides):
    cfg = {
        "vault_path": tempfile.mkdtemp(),
        "dashboard_filename": "TaskNemo.md",
    }
    cfg.update(overrides)
    return cfg


def _make_task(**overrides):
    """Create a minimal task dict with sensible defaults."""
    now = datetime.now()
    task = {
        "id": "TASK-100",
        "title": "Test task",
        "description": "A test description",
        "sender": "Test User",
        "due_hint": "",
        "teams_link": "",
        "next_step": "",
        "state": "open",
        "score": 50,
        "score_breakdown": {},
        "times_seen": 1,
        "created": now.isoformat(),
        "updated": now.isoformat(),
        "source": "teams",
        "source_link": "",
        "source_metadata": {},
        "direction": "inbound",
        "subtask_ids": [],
        "thread_id": "",
    }
    task.update(overrides)
    return task


# ---------------------------------------------------------------------------
# TestComputeIdleDays
# ---------------------------------------------------------------------------


class TestComputeIdleDays:
    def test_updated_today_returns_zero(self):
        task = _make_task(updated=datetime.now().isoformat())
        assert _compute_idle_days(task) == 0

    def test_updated_three_days_ago(self):
        task = _make_task(updated=(datetime.now() - timedelta(days=3)).isoformat())
        assert _compute_idle_days(task) == 3

    def test_fallback_to_created(self):
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        task = _make_task(created=five_days_ago)
        task.pop("updated", None)
        assert _compute_idle_days(task) == 5


# ---------------------------------------------------------------------------
# TestParseDueHint
# ---------------------------------------------------------------------------


class TestParseDueHint:
    def test_eod_today(self):
        ref = datetime(2026, 3, 6, 10, 0, 0)
        result = parse_due_hint("eod today", ref)
        assert result == datetime(2026, 3, 6, 17, 0, 0)

    def test_eow_returns_friday(self):
        # March 6, 2026 is a Friday
        ref = datetime(2026, 3, 4, 10, 0, 0)  # Wednesday
        result = parse_due_hint("eow", ref)
        assert result.weekday() == 4  # Friday

    def test_tomorrow(self):
        ref = datetime(2026, 3, 6, 10, 0, 0)
        result = parse_due_hint("tomorrow", ref)
        assert result == datetime(2026, 3, 7, 17, 0, 0)

    def test_urgent_means_today(self):
        ref = datetime(2026, 3, 6, 10, 0, 0)
        result = parse_due_hint("urgent", ref)
        assert result == datetime(2026, 3, 6, 17, 0, 0)

    def test_iso_date(self):
        result = parse_due_hint("2026-03-15T09:00:00")
        assert result == datetime(2026, 3, 15, 9, 0, 0)

    def test_empty_returns_none(self):
        assert parse_due_hint("") is None

    def test_garbage_returns_none(self):
        assert parse_due_hint("xyzzy") is None

    def test_eod_friday(self):
        ref = datetime(2026, 3, 3, 10, 0, 0)  # Tuesday
        result = parse_due_hint("eod friday", ref)
        assert result is not None
        assert result.weekday() == 4  # Friday
        assert result.hour == 17


# ---------------------------------------------------------------------------
# TestComputeConfidence
# ---------------------------------------------------------------------------


class TestComputeConfidence:
    def test_full_task_high_confidence(self):
        task = _make_task(
            description="Full desc",
            due_hint="eod",
            teams_link="https://teams.microsoft.com/l/message/123",
            thread_id="19:abc@thread.v2",
            times_seen=2,
            next_step="Do something",
            source="calendar",
            sender="Test User",
        )
        conf = _compute_confidence(task)
        assert conf >= 0.9

    def test_minimal_task_low_confidence(self):
        task = _make_task(
            description="",
            due_hint="",
            teams_link="",
            thread_id="",
            times_seen=1,
            next_step="",
            source="teams",
            sender="",
        )
        conf = _compute_confidence(task)
        assert conf <= 0.2

    def test_calendar_source_boosts(self):
        task_teams = _make_task(source="teams")
        task_cal = _make_task(source="calendar")
        assert _compute_confidence(task_cal) > _compute_confidence(task_teams)


# ---------------------------------------------------------------------------
# TestClassifyTaskType
# ---------------------------------------------------------------------------


class TestClassifyTaskType:
    def test_reply_align(self):
        task = _make_task(title="Reply to Alex with status")
        assert classify_task_type(task) == "reply_align"

    def test_draft_create(self):
        task = _make_task(title="Draft the proposal document")
        assert classify_task_type(task) == "draft_create"

    def test_schedule_book(self):
        task = _make_task(title="Schedule meeting with team")
        assert classify_task_type(task) == "schedule_book"

    def test_review_decide(self):
        task = _make_task(title="Review the budget proposal")
        assert classify_task_type(task) == "review_decide"

    def test_followup_nudge(self):
        task = _make_task(title="Follow up with Jordan on status")
        assert classify_task_type(task) == "followup_nudge"

    def test_default_fallback(self):
        task = _make_task(title="Something vague", description="", next_step="")
        assert classify_task_type(task) == "reply_align"


# ---------------------------------------------------------------------------
# TestGenerateNextAction
# ---------------------------------------------------------------------------


class TestGenerateNextAction:
    def test_shortens_existing_next_step(self):
        long_step = "Send the quarterly report with all the details and make sure to include appendix attachments and summaries for each section item"
        task = _make_task(next_step=long_step)
        result = _generate_next_action(task)
        words = result.split()
        assert len(words) <= 12

    def test_infers_by_type_reply(self):
        task = _make_task(title="Reply to Alex", next_step="")
        result = _generate_next_action(task)
        assert "Reply" in result

    def test_infers_by_type_followup(self):
        task = _make_task(title="Follow up with Jordan", next_step="", sender="Jordan Kim")
        result = _generate_next_action(task)
        assert "Ping" in result or "Jordan" in result

    def test_fills_missing_with_default(self):
        task = _make_task(title="Something vague", next_step="", description="")
        result = _generate_next_action(task)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestComputeFocusPriority
# ---------------------------------------------------------------------------


class TestComputeFocusPriority:
    def test_due_48h_boost(self):
        task_due = _make_task(score=50, due_hint="eod today")
        task_no_due = _make_task(score=50, due_hint="")
        assert _compute_focus_priority(task_due) > _compute_focus_priority(task_no_due)

    def test_idle_boost(self):
        task_stale = _make_task(score=50, updated=(datetime.now() - timedelta(days=4)).isoformat())
        task_fresh = _make_task(score=50, updated=datetime.now().isoformat())
        assert _compute_focus_priority(task_stale) > _compute_focus_priority(task_fresh)

    def test_low_confidence_penalty(self):
        # Minimal task (low confidence) vs rich task (high confidence), same score
        task_minimal = _make_task(
            score=50, description="", due_hint="", teams_link="",
            thread_id="", times_seen=1, next_step="", sender="",
        )
        task_rich = _make_task(
            score=50, description="Has desc", due_hint="eow",
            teams_link="https://teams.microsoft.com/l/message/123",
            thread_id="19:abc", times_seen=2, next_step="Do it",
            sender="Someone", source="calendar",
        )
        assert _compute_focus_priority(task_rich) > _compute_focus_priority(task_minimal)


# ---------------------------------------------------------------------------
# TestRenderTaskItemV2
# ---------------------------------------------------------------------------


class TestRenderTaskItemV2:
    def test_score_age_idle_line(self):
        task = _make_task(score=82)
        result = _render_task_item_v2(task)
        assert "Score: 82" in result
        assert "Age:" in result
        assert "Idle:" in result

    def test_due_age_idle_line(self):
        task = _make_task(due_hint="eod today")
        result = _render_task_item_v2(task)
        assert "Due: eod today" in result
        assert "Age:" in result
        assert "Idle:" in result

    def test_owner_line(self):
        task = _make_task(sender="Alex Morgan")
        result = _render_task_item_v2(task)
        assert "Asked by: Alex Morgan" in result

    def test_next_line(self):
        task = _make_task(next_step="Send summary")
        result = _render_task_item_v2(task)
        assert "Next: Send summary" in result

    def test_link_line_present(self):
        task = _make_task(teams_link="https://teams.microsoft.com/l/message/123")
        result = _render_task_item_v2(task)
        assert "teams.microsoft.com" in result

    def test_closed_format_unchanged(self):
        task = _make_task(state="closed")
        result = _render_task_item_v2(task)
        assert "- [x]" in result
        assert "~~" in result
        assert "closed" in result

    def test_outbound_shows_assigned_to(self):
        task = _make_task(direction="outbound", sender="Casey Ng")
        result = _render_task_item_v2(task)
        assert "Assigned to: Casey Ng" in result


# ---------------------------------------------------------------------------
# TestRenderDashboardV2
# ---------------------------------------------------------------------------


class TestRenderDashboardV2:
    def test_section_order(self):
        tasks = _load_fixture_tasks()
        config = _make_config()
        md = render_dashboard_v2(tasks, config)
        my_tasks_idx = md.index("## My Actions")
        focus_idx = md.index("\U0001f525 Focus Now")
        due_soon_idx = md.index("Due Soon")
        open_idx = md.index("[!todo]")
        followup_idx = md.index("Stale \u2014")
        waiting_others_idx = md.index("## Following Up")
        nudge_idx = md.index("Nudge Needed")
        waiting_idx = md.index("\u23f3 Waiting for Reply")
        closed_idx = md.index("Recently Closed")
        assert my_tasks_idx < focus_idx < due_soon_idx < open_idx < followup_idx
        assert followup_idx < waiting_others_idx < nudge_idx < waiting_idx < closed_idx

    def test_summary_line_format(self):
        tasks = _load_fixture_tasks()
        config = _make_config(last_run="2026-03-06T14:23:00")
        md = render_dashboard_v2(tasks, config)
        assert "Last synced:" in md
        assert "Focus:" in md
        assert "Due soon:" in md
        assert "Nudge:" in md
        assert "Stale (idle" in md

    def test_focus_minimum_3(self):
        """When 1-2 inbound tasks exist, focus should pad to 3 from other states."""
        tasks = [
            _make_task(id="TASK-001", title="Review budget proposal", score=80, state="open"),
            _make_task(id="TASK-002", title="Update API documentation", score=20, state="open"),
            _make_task(id="TASK-003", title="Schedule team standup", score=10, state="waiting"),
        ]
        config = _make_config()
        md = render_dashboard_v2(tasks, config)
        # Focus should contain at least items — check for task IDs in focus section
        focus_section_start = md.index("Focus Now")
        due_section_start = md.index("Due Soon")
        focus_section = md[focus_section_start:due_section_start]
        assert "TASK-001" in focus_section
        assert "TASK-002" in focus_section
        assert "TASK-003" in focus_section

    def test_focus_max_5(self):
        """Focus should never exceed 5 items."""
        tasks = [
            _make_task(id=f"TASK-{i:03d}", title=f"Unique task number {i} for testing", score=90-i, state="open")
            for i in range(8)
        ]
        config = _make_config()
        md = render_dashboard_v2(tasks, config)
        focus_start = md.index("Focus Now")
        due_start = md.index("Due Soon")
        focus_section = md[focus_start:due_start]
        # Count task IDs in focus section
        count = sum(1 for i in range(8) if f"TASK-{i:03d}" in focus_section)
        assert count == 5

    def test_due_soon_section(self):
        tasks = [
            _make_task(id="TASK-DUE", score=30, state="open", due_hint="eod today"),
        ]
        config = _make_config()
        md = render_dashboard_v2(tasks, config)
        assert "Due Soon" in md

    def test_nudge_due_vs_waiting_split(self):
        """Outbound idle >= 3 goes to Nudge Due, fresh outbound goes to Waiting."""
        stale_outbound = _make_task(
            id="TASK-STALE",
            title="Follow up on budget approval",
            direction="outbound",
            state="open",
            updated=(datetime.now() - timedelta(days=5)).isoformat(),
        )
        fresh_outbound = _make_task(
            id="TASK-FRESH",
            title="Check deployment status",
            direction="outbound",
            state="open",
            updated=datetime.now().isoformat(),
        )
        config = _make_config()
        md = render_dashboard_v2([stale_outbound, fresh_outbound], config)
        nudge_idx = md.index("Nudge Needed")
        waiting_idx = md.index("\u23f3 Waiting for Reply")
        nudge_section = md[nudge_idx:waiting_idx]
        waiting_section = md[waiting_idx:]
        assert "TASK-STALE" in nudge_section
        assert "TASK-FRESH" in waiting_section

    def test_container_grouping(self):
        # Need 5+ open tasks so some spill from focus into grouped open
        focus_tasks = [
            _make_task(id=f"TASK-F{i}", title=f"High priority item {i}", state="open", score=90-i)
            for i in range(5)
        ]
        # These 2 tasks share a meeting_title and should be grouped together
        t1 = _make_task(id="TASK-G1", title="Draft sprint retrospective notes", state="open", score=10,
                        source_metadata={"meeting_title": "Sprint Standup"})
        t2 = _make_task(id="TASK-G2", title="Review deployment pipeline changes", state="open", score=10,
                        source_metadata={"meeting_title": "Sprint Standup"})
        config = _make_config()
        md = render_dashboard_v2(focus_tasks + [t1, t2], config)
        assert "Sprint Standup" in md
        assert "2 open" in md

    def test_empty_placeholders(self):
        config = _make_config()
        md = render_dashboard_v2([], config)
        assert "*No high-priority tasks right now.*" in md
        assert "*Nothing due soon.*" in md
        assert "*No nudges needed.*" in md
        assert "*No other open tasks.*" in md
        assert "*Nothing stale" in md

    def test_outbound_routing(self):
        """Outbound tasks should NOT appear in Focus or Open sections."""
        outbound = _make_task(id="TASK-OUT", direction="outbound", state="open", score=95)
        config = _make_config()
        md = render_dashboard_v2([outbound], config)
        focus_start = md.index("Focus Now")
        due_start = md.index("Due Soon")
        focus_section = md[focus_start:due_start]
        assert "TASK-OUT" not in focus_section

    def test_no_duplicate_across_sections(self):
        """An outbound task due<48h should appear in Nudge only, not Due Soon."""
        outbound_due = _make_task(
            id="TASK-OD",
            direction="outbound",
            state="open",
            due_hint="eod today",
        )
        config = _make_config()
        md = render_dashboard_v2([outbound_due], config)
        # Should be in Nudge Due
        nudge_idx = md.index("Nudge Needed")
        assert "TASK-OD" in md[nudge_idx:]
        # Should NOT be in Due Soon (inbound only)
        due_soon_idx = md.index("Due Soon")
        open_idx = md.index("[!todo]")
        due_soon_section = md[due_soon_idx:open_idx]
        assert "TASK-OD" not in due_soon_section

    def test_needs_followup_section(self):
        """Inbound needs_followup task not in focus lands in Needs Follow-up."""
        # Fill focus with 5 higher-priority tasks
        focus_tasks = [
            _make_task(id=f"TASK-F{i}", title=f"High priority item {i} for focus", state="open", score=90-i)
            for i in range(5)
        ]
        followup_task = _make_task(
            id="TASK-NFU",
            title="Check status of deployment review",
            state="needs_followup",
            score=5,
        )
        config = _make_config()
        md = render_dashboard_v2(focus_tasks + [followup_task], config)
        followup_idx = md.index("Stale \u2014")
        waiting_idx = md.index("## Following Up")
        followup_section = md[followup_idx:waiting_idx]
        assert "TASK-NFU" in followup_section


# ---------------------------------------------------------------------------
# TestVersionToggle
# ---------------------------------------------------------------------------


class TestVersionToggle:
    def test_v1_config_produces_v1_output(self):
        config = _make_config(dashboard_version=1)
        md = render_dashboard([], config)
        # v1 uses "Last synced {age}" format without colon
        assert "Last synced" in md
        assert "need attention" in md

    def test_v2_config_produces_v2_output(self):
        config = _make_config(dashboard_version=2)
        md = render_dashboard([], config)
        # v2 uses "Last synced: {timestamp}" format with new metrics
        assert "Last synced:" in md
        assert "Focus:" in md
        assert "Due soon:" in md

    def test_default_is_v2(self):
        config = _make_config()
        md = render_dashboard([], config)
        assert "Last synced:" in md
        assert "Focus:" in md


# ---------------------------------------------------------------------------
# TestExtractContainerKey
# ---------------------------------------------------------------------------


class TestExtractContainerKey:
    def test_meeting_title_takes_priority(self):
        task = _make_task(source_metadata={"meeting_title": "Sprint Standup"}, thread_id="19:abc")
        key, title, src_type, _ = _extract_container_key(task)
        assert "meeting:" in key
        assert title == "Sprint Standup"
        assert src_type == "meeting"

    def test_long_meeting_title_shortened(self):
        task = _make_task(source_metadata={
            "meeting_title": "Voice fundamental metrics and WebRTC readiness criteria sync"
        })
        key, title, src_type, _ = _extract_container_key(task)
        assert "meeting:" in key
        assert len(title.split()) <= 5
        assert "Voice" in title
        assert "fundamental" in title or "metrics" in title

    def test_thread_id_shows_sender_and_title(self):
        task = _make_task(sender="Claire Liu", title="Share voice initiatives documentation",
                          thread_id="19:abc@thread.v2")
        key, title, src_type, _ = _extract_container_key(task)
        assert "thread:" in key
        assert "Claire Liu" in title
        assert "Share voice" in title
        assert src_type == "chat"

    def test_sender_fallback_has_meaningful_context(self):
        task = _make_task(sender="Alex M", title="Update the quarterly report slides",
                          thread_id="", source_metadata={})
        key, title, src_type, _ = _extract_container_key(task)
        assert "sender:" in key
        assert "Alex M" in title
        assert "Update the quarterly report" in title
        assert src_type == "direct"
