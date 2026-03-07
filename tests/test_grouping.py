"""Unit tests for Teams link helpers and subtask grouping."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import extract_thread_id, build_search_fallback, suggest_groups


class TestExtractThreadId:
    def test_standard_message_link(self):
        url = "https://teams.microsoft.com/l/message/19:abc123@thread.v2/1772125351677"
        assert extract_thread_id(url) == "19:abc123@thread.v2"

    def test_meeting_thread_link(self):
        url = "https://teams.microsoft.com/l/message/19:meeting_NTczYzE4OWYt@thread.v2/1772185827336"
        assert extract_thread_id(url) == "19:meeting_NTczYzE4OWYt@thread.v2"

    def test_unq_gbl_spaces_link(self):
        url = "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_c8a77f12-5ed3-45dc-8bdb-6bc6f80a56f9@unq.gbl.spaces/1772444152457"
        assert extract_thread_id(url) == "19:27e21d95-d37b-4024-a823-b2d9c44db61a_c8a77f12-5ed3-45dc-8bdb-6bc6f80a56f9@unq.gbl.spaces"

    def test_empty_string(self):
        assert extract_thread_id("") == ""

    def test_none(self):
        assert extract_thread_id(None) == ""

    def test_malformed_url(self):
        assert extract_thread_id("not-a-url") == ""

    def test_teams_url_without_message_path(self):
        url = "https://teams.microsoft.com/l/channel/19:abc@thread.v2"
        # No /message/ segment → falls through to path parsing which won't match
        assert extract_thread_id(url) == ""

    def test_context_param_with_chat_id(self):
        import json
        ctx = json.dumps({"chatOrChannel": {"id": "19:ctx_thread@thread.v2"}})
        url = f"https://teams.microsoft.com/l/message/19:abc@thread.v2/123?context={ctx}"
        assert extract_thread_id(url) == "19:ctx_thread@thread.v2"


class TestBuildSearchFallback:
    def test_basic_fallback(self):
        task = {"title": "Share resources and videos for app extensibility", "sender": "Tirtha Tushar Panda"}
        result = build_search_fallback(task)
        assert "Tirtha Tushar Panda" in result
        assert 'Search "' in result

    def test_fallback_without_sender(self):
        task = {"title": "Some task title", "sender": ""}
        result = build_search_fallback(task)
        assert "in Teams" in result
        assert "Search" in result

    def test_fallback_strips_stop_words(self):
        task = {"title": "Reply to the status update for Rahul", "sender": "Rahul Bhuptani"}
        result = build_search_fallback(task)
        # "to", "the", "for" are stop words and should be excluded
        assert "Reply" in result or "status" in result or "update" in result

    def test_fallback_with_short_title(self):
        task = {"title": "Fix bug", "sender": "Alice"}
        result = build_search_fallback(task)
        assert 'Search "' in result
        assert "Alice" in result


class TestSuggestGroups:
    def test_groups_same_sender_same_thread(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Short task"},
            {"id": "T-002", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "A much longer description that indicates broader scope of work"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 1
        # Longer description → parent
        assert groups[0]["parent_id"] == "T-002"
        assert groups[0]["child_ids"] == ["T-001"]

    def test_no_group_for_different_threads(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Task A"},
            {"id": "T-002", "sender": "Alice", "thread_id": "19:def@thread.v2",
             "description": "Task B"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 0

    def test_no_group_for_different_senders(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Task A"},
            {"id": "T-002", "sender": "Bob", "thread_id": "19:abc@thread.v2",
             "description": "Task B"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 0

    def test_no_group_for_empty_thread_id(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "",
             "description": "Task A"},
            {"id": "T-002", "sender": "Alice", "thread_id": "",
             "description": "Task B"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 0

    def test_multiple_groups(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Alice task 1 with longer description"},
            {"id": "T-002", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Alice task 2"},
            {"id": "T-003", "sender": "Bob", "thread_id": "19:xyz@thread.v2",
             "description": "Bob task 1 with a much longer description for grouping"},
            {"id": "T-004", "sender": "Bob", "thread_id": "19:xyz@thread.v2",
             "description": "Bob task 2"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 2
        parent_ids = {g["parent_id"] for g in groups}
        assert "T-001" in parent_ids
        assert "T-003" in parent_ids

    def test_single_task_not_grouped(self):
        tasks = [
            {"id": "T-001", "sender": "Alice", "thread_id": "19:abc@thread.v2",
             "description": "Only one task"},
        ]
        groups = suggest_groups(tasks)
        assert len(groups) == 0
