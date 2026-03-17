"""Unit tests for priority scoring logic."""

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    score_task,
    evaluate_transitions,
    transition_task,
    build_workiq_queries,
    build_completion_query,
    match_conversation_to_tasks,
    build_email_queries,
    build_calendar_query,
    build_all_queries,
)


def _make_config():
    """Return a minimal config for testing."""
    return {
        "stakeholders": {
            "alex morgan": {"name": "Alex Morgan", "weight": 8},
            "pat rivera": {"name": "Pat Rivera", "weight": 9},
            "jamie lee": {"name": "Jamie Lee", "weight": 3},
        },
        "urgency_keywords": [
            "urgent", "asap", "eod", "today", "blocker", "critical", "p0",
        ],
    }


def _make_task(sender="Alex Morgan", title="Reply to status update",
               description="", due_hint="", created_days_ago=0, times_seen=1,
               state="open"):
    """Create a task dict for testing."""
    created = (datetime.now() - timedelta(days=created_days_ago)).isoformat()
    return {
        "id": "TASK-TEST",
        "title": title,
        "description": description,
        "sender": sender,
        "due_hint": due_hint,
        "state": state,
        "times_seen": times_seen,
        "created": created,
        "updated": created,
        "state_history": [
            {"state": "open", "reason": "test", "date": created}
        ],
    }


class TestScoreTask:
    def test_manager_high_stakeholder_score(self):
        config = _make_config()
        task = _make_task(sender="Alex Morgan", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["stakeholder"] == 32  # 8 * 4

    def test_skip_manager_higher_score(self):
        config = _make_config()
        task = _make_task(sender="Pat Rivera", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["stakeholder"] == 36  # 9 * 4

    def test_peer_low_stakeholder_score(self):
        config = _make_config()
        task = _make_task(sender="Jamie Lee", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["stakeholder"] == 12  # 3 * 4

    def test_unknown_sender_default_weight(self):
        config = _make_config()
        task = _make_task(sender="Unknown Person", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["stakeholder"] == 8  # default 2 * 4

    def test_urgency_keyword_in_title(self):
        config = _make_config()
        task = _make_task(title="urgent: Reply to status update", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["urgency"] >= 10

    def test_urgency_keyword_in_due_hint(self):
        config = _make_config()
        task = _make_task(due_hint="asap", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["urgency"] >= 10

    def test_multiple_urgency_keywords(self):
        config = _make_config()
        task = _make_task(title="urgent blocker: critical issue", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["urgency"] == 30  # capped at 30

    def test_no_urgency(self):
        config = _make_config()
        task = _make_task(title="Share document with team", created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["urgency"] == 0

    def test_age_fresh_task(self):
        config = _make_config()
        task = _make_task(created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["age"] == 0

    def test_age_2_days(self):
        config = _make_config()
        task = _make_task(created_days_ago=2)
        score_task(task, config)
        assert task["score_breakdown"]["age"] == 5

    def test_age_5_days(self):
        config = _make_config()
        task = _make_task(created_days_ago=5)
        score_task(task, config)
        assert task["score_breakdown"]["age"] == 10

    def test_age_10_days(self):
        config = _make_config()
        task = _make_task(created_days_ago=10)
        score_task(task, config)
        assert task["score_breakdown"]["age"] == 15

    def test_age_20_days(self):
        config = _make_config()
        task = _make_task(created_days_ago=20)
        score_task(task, config)
        assert task["score_breakdown"]["age"] == 20

    def test_thread_intensity(self):
        config = _make_config()
        task = _make_task(times_seen=5, created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["thread"] == 10  # capped at 10

    def test_thread_single_mention(self):
        config = _make_config()
        task = _make_task(times_seen=1, created_days_ago=0)
        score_task(task, config)
        assert task["score_breakdown"]["thread"] == 2

    def test_total_score_capped_at_100(self):
        config = _make_config()
        # Max everything: skip manager, urgent+blocker+critical, old, many mentions
        task = _make_task(
            sender="Pat Rivera",
            title="urgent blocker critical p0",
            created_days_ago=20,
            times_seen=10,
        )
        score_task(task, config)
        assert task["score"] <= 100

    def test_score_components_sum_correctly(self):
        config = _make_config()
        task = _make_task(sender="Alex Morgan", created_days_ago=5, times_seen=2)
        score_task(task, config)
        bd = task["score_breakdown"]
        expected = (bd["stakeholder"] + bd["urgency"] + bd["age"] + bd["thread"]
                    + bd["subtask_boost"] + bd["calendar_boost"] + bd["multi_source"]
                    + bd["response_time"] + bd["escalation"] + bd["pin"])
        assert task["score"] == min(expected, 100)

    def test_subtask_boost_zero_when_no_children(self):
        config = _make_config()
        task = _make_task()
        task["subtask_ids"] = []
        score_task(task, config)
        assert task["score_breakdown"]["subtask_boost"] == 0

    def test_subtask_boost_one_child(self):
        config = _make_config()
        task = _make_task()
        task["subtask_ids"] = ["TASK-002"]
        score_task(task, config)
        assert task["score_breakdown"]["subtask_boost"] == 5

    def test_subtask_boost_two_children(self):
        config = _make_config()
        task = _make_task()
        task["subtask_ids"] = ["TASK-002", "TASK-003"]
        score_task(task, config)
        assert task["score_breakdown"]["subtask_boost"] == 10

    def test_subtask_boost_capped_at_15(self):
        config = _make_config()
        task = _make_task()
        task["subtask_ids"] = ["T-1", "T-2", "T-3", "T-4", "T-5"]
        score_task(task, config)
        assert task["score_breakdown"]["subtask_boost"] == 15

    def test_calendar_boost_for_calendar_source(self):
        config = _make_config()
        config["scoring"] = {"calendar_boost": 5}
        task = _make_task()
        task["source"] = "calendar"
        score_task(task, config)
        assert task["score_breakdown"]["calendar_boost"] == 5

    def test_calendar_boost_zero_for_teams_source(self):
        config = _make_config()
        config["scoring"] = {"calendar_boost": 5}
        task = _make_task()
        task["source"] = "teams"
        score_task(task, config)
        assert task["score_breakdown"]["calendar_boost"] == 0

    def test_calendar_boost_zero_when_no_source(self):
        config = _make_config()
        task = _make_task()
        # No source field at all
        score_task(task, config)
        assert task["score_breakdown"]["calendar_boost"] == 0

    def test_multi_source_boost_with_alternate_links(self):
        config = _make_config()
        task = _make_task()
        task["source_metadata"] = {
            "alternate_links": [
                {"source": "email", "link": "https://outlook.office.com/mail/123"}
            ]
        }
        score_task(task, config)
        assert task["score_breakdown"]["multi_source"] == 5

    def test_multi_source_zero_without_alternate_links(self):
        config = _make_config()
        task = _make_task()
        task["source_metadata"] = {}
        score_task(task, config)
        assert task["score_breakdown"]["multi_source"] == 0

    def test_updated_sum_with_all_components(self):
        config = _make_config()
        config["scoring"] = {"calendar_boost": 5}
        task = _make_task(sender="Alex Morgan", created_days_ago=5, times_seen=2)
        task["source"] = "calendar"
        task["source_metadata"] = {
            "alternate_links": [
                {"source": "teams", "link": "https://teams.microsoft.com/l/message/123"}
            ]
        }
        score_task(task, config)
        bd = task["score_breakdown"]
        expected = (bd["stakeholder"] + bd["urgency"] + bd["age"] + bd["thread"]
                    + bd["subtask_boost"] + bd["calendar_boost"] + bd["multi_source"]
                    + bd["response_time"] + bd["escalation"] + bd["pin"])
        assert task["score"] == min(expected, 100)
        # calendar_boost=5, multi_source=5 should both be present
        assert bd["calendar_boost"] == 5
        assert bd["multi_source"] == 5


class TestTransitionTask:
    def test_open_to_waiting(self):
        task = _make_task(state="open")
        assert transition_task(task, "waiting", "test") is True
        assert task["state"] == "waiting"

    def test_open_to_closed(self):
        task = _make_task(state="open")
        assert transition_task(task, "closed", "test") is True
        assert task["state"] == "closed"

    def test_closed_can_reopen(self):
        task = _make_task(state="open")
        transition_task(task, "closed", "test")
        assert transition_task(task, "open", "reopen") is True
        assert task["state"] == "open"

    def test_closed_cannot_skip_to_waiting(self):
        task = _make_task(state="open")
        transition_task(task, "closed", "test")
        assert transition_task(task, "waiting", "nope") is False
        assert task["state"] == "closed"

    def test_transition_records_history(self):
        task = _make_task(state="open")
        transition_task(task, "needs_followup", "No update")
        history = task["state_history"]
        assert len(history) == 2
        assert history[-1]["state"] == "needs_followup"
        assert history[-1]["reason"] == "No update"


class TestEvaluateTransitions:
    def test_open_to_needs_followup_when_stale(self):
        task = _make_task(created_days_ago=5, state="open")
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "needs_followup"

    def test_open_stays_open_when_fresh(self):
        task = _make_task(created_days_ago=1, state="open")
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 0

    def test_open_stays_open_when_has_update(self):
        task = _make_task(created_days_ago=5, state="open")
        signals = {task["id"]: {"has_update": True}}
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], signals, today)
        assert len(transitions) == 0

    def test_completion_signal_triggers_likely_done(self):
        task = _make_task(created_days_ago=2, state="open")
        signals = {task["id"]: {"signal_type": "completion", "signal": "thanks"}}
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], signals, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "likely_done"

    def test_waiting_signal_triggers_waiting(self):
        task = _make_task(created_days_ago=2, state="open")
        signals = {task["id"]: {"signal_type": "waiting", "signal": "blocked on"}}
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], signals, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "waiting"

    def test_likely_done_auto_closes(self):
        four_days_ago = (datetime.now() - timedelta(days=4)).isoformat()
        task = _make_task(created_days_ago=6, state="open")
        # Manually set to likely_done 4 days ago
        task["state"] = "likely_done"
        task["state_history"].append({
            "state": "likely_done", "reason": "test", "date": four_days_ago,
        })
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "closed"

    def test_needs_followup_auto_closes_after_7_days(self):
        task = _make_task(created_days_ago=10, state="open")
        task["state"] = "needs_followup"
        nf_date = (datetime.now() - timedelta(days=8)).isoformat()
        task["state_history"].append({"state": "needs_followup", "reason": "stale", "date": nf_date})
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 1
        assert transitions[0][2] == "closed"

    def test_closed_tasks_skipped(self):
        task = _make_task(state="open")
        task["state"] = "closed"
        today = datetime.now().isoformat()
        transitions = evaluate_transitions([task], {}, today)
        assert len(transitions) == 0

    def test_conversation_completion_signal_triggers_likely_done(self):
        task = _make_task(created_days_ago=2, state="open")
        task["thread_id"] = "19:abc@thread.v2"
        conv_signals = [{
            "sender": "Alex Morgan",
            "topic": "status update",
            "thread_id": "19:abc@thread.v2",
            "signal_type": "completion",
            "signal": "Alex said 'thanks, looks good'",
        }]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions(
            [task], {}, today, conversation_signals=conv_signals,
        )
        assert len(transitions) == 1
        assert transitions[0][2] == "likely_done"

    def test_conversation_active_signal_reopens_needs_followup(self):
        task = _make_task(created_days_ago=5, state="open")
        task["state"] = "needs_followup"
        task["thread_id"] = "19:abc@thread.v2"
        task["state_history"].append({
            "state": "needs_followup", "reason": "stale", "date": task["created"],
        })
        conv_signals = [{
            "sender": "Alex Morgan",
            "topic": "status update",
            "thread_id": "19:abc@thread.v2",
            "signal_type": "active",
            "signal": "New messages in thread",
        }]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions(
            [task], {}, today, conversation_signals=conv_signals,
        )
        assert len(transitions) == 1
        assert transitions[0][2] == "open"

    def test_conversation_signal_updates_teams_link(self):
        task = _make_task(created_days_ago=2, state="open")
        task["thread_id"] = "19:abc@thread.v2"
        task["teams_link"] = "https://teams.microsoft.com/l/message/19:abc@thread.v2/123"
        full_url = "https://teams.microsoft.com/l/message/19:abc@thread.v2/456?context=%7B%22chatOrChannel%22%3A%7B%22id%22%3A%2219%3Aabc%40thread.v2%22%7D%7D"
        conv_signals = [{
            "sender": "Alex Morgan",
            "topic": "status update",
            "thread_id": "19:abc@thread.v2",
            "signal_type": "active",
            "signal": "New messages",
            "teams_link": full_url,
        }]
        today = datetime.now().isoformat()
        evaluate_transitions([task], {}, today, conversation_signals=conv_signals)
        assert "context=" in task["teams_link"]

    def test_direct_followup_takes_precedence_over_conversation(self):
        task = _make_task(created_days_ago=2, state="open")
        task["id"] = "TASK-PREC"
        task["thread_id"] = "19:abc@thread.v2"
        # Direct signal says completion
        direct_signals = {"TASK-PREC": {"signal_type": "completion", "signal": "direct: done"}}
        # Conversation signal says active (should be ignored for this task)
        conv_signals = [{
            "sender": "Alex Morgan",
            "topic": "status update",
            "thread_id": "19:abc@thread.v2",
            "signal_type": "active",
            "signal": "conversation activity",
        }]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions(
            [task], direct_signals, today, conversation_signals=conv_signals,
        )
        assert len(transitions) == 1
        assert transitions[0][2] == "likely_done"

    def test_unmatched_conversation_signal_ignored(self):
        task = _make_task(created_days_ago=5, state="open")
        task["thread_id"] = "19:abc@thread.v2"
        conv_signals = [{
            "sender": "Unknown Person",
            "topic": "completely unrelated topic",
            "thread_id": "19:different@thread.v2",
            "signal_type": "completion",
            "signal": "Done",
        }]
        today = datetime.now().isoformat()
        transitions = evaluate_transitions(
            [task], {}, today, conversation_signals=conv_signals,
        )
        # Should still transition to needs_followup (no matching signal)
        assert len(transitions) == 1
        assert transitions[0][2] == "needs_followup"


class TestBuildWorkiqQueries:
    def test_returns_single_conversation_query(self):
        queries = build_workiq_queries("March 01, 2026")
        assert len(queries) == 1
        assert "March 01, 2026" in queries[0]

    def test_uses_config_template(self):
        config = {"conversation_query_template": "Get my chats since {since_date}"}
        queries = build_workiq_queries("March 01, 2026", config)
        assert queries == ["Get my chats since March 01, 2026"]

    def test_default_template_without_config(self):
        queries = build_workiq_queries("March 01, 2026")
        assert "conversations" in queries[0].lower()


class TestBuildCompletionQuery:
    def test_returns_string_with_date(self):
        query = build_completion_query("March 01, 2026")
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"completion_query_template": "What's done since {since_date}?"}
        query = build_completion_query("March 01, 2026", config)
        assert query == "What's done since March 01, 2026?"

    def test_default_mentions_resolved(self):
        query = build_completion_query("March 01, 2026")
        assert "resolved" in query.lower() or "completed" in query.lower()


class TestMatchConversationToTasks:
    def test_match_by_thread_id(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "title": "Task A",
             "thread_id": "19:abc@thread.v2"},
            {"id": "T-002", "sender": "Bob", "title": "Task B",
             "thread_id": "19:def@thread.v2"},
        ]
        conv = {"sender": "Charlie", "topic": "Something else",
                "thread_id": "19:abc@thread.v2"}
        match = match_conversation_to_tasks(conv, tasks)
        assert match is not None
        assert match["id"] == "T-001"

    def test_match_by_sender_and_topic(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "title": "Review status update",
             "thread_id": ""},
            {"id": "T-002", "sender": "Bob", "title": "Share tracker",
             "thread_id": ""},
        ]
        conv = {"sender": "Alice", "topic": "Review the status update",
                "thread_id": ""}
        match = match_conversation_to_tasks(conv, tasks)
        assert match is not None
        assert match["id"] == "T-001"

    def test_no_match_different_sender_and_thread(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "title": "Task A",
             "thread_id": "19:abc@thread.v2"},
        ]
        conv = {"sender": "Bob", "topic": "Completely different",
                "thread_id": "19:xyz@thread.v2"}
        match = match_conversation_to_tasks(conv, tasks)
        assert match is None

    def test_thread_id_match_takes_priority_over_sender(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "title": "Task A",
             "thread_id": "19:abc@thread.v2"},
            {"id": "T-002", "sender": "Bob", "title": "Task A similar",
             "thread_id": "19:def@thread.v2"},
        ]
        # Sender is Bob but thread_id matches Alice's task
        conv = {"sender": "Bob", "topic": "Task A",
                "thread_id": "19:abc@thread.v2"}
        match = match_conversation_to_tasks(conv, tasks)
        assert match["id"] == "T-001"

    def test_empty_tasks_returns_none(self):
        conv = {"sender": "Alice", "topic": "Something",
                "thread_id": "19:abc@thread.v2"}
        assert match_conversation_to_tasks(conv, []) is None

    def test_sender_match_without_topic_returns_none(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "title": "Task A",
             "thread_id": ""},
        ]
        conv = {"sender": "Alice", "topic": "", "thread_id": ""}
        match = match_conversation_to_tasks(conv, tasks)
        assert match is None
