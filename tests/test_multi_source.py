"""Unit tests for multi-source (email + calendar) query building and cross-source matching."""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    build_email_queries,
    build_calendar_query,
    build_all_queries,
    build_sent_items_query,
    build_outbound_query,
    build_all_received_query,
    build_inbound_dms_query,
    build_key_contact_queries,
    merge_duplicates,
    build_doc_mentions_queries,
    build_transcript_queries,
    build_discovery_queries,
    build_detail_queries,
    build_validation_query,
    find_cross_source_match,
    merge_cross_source_signal,
)


def _make_task(task_id="TASK-TEST", sender="Jordan Kim",
               title="Follow up on API schema mapping", state="open",
               source="teams", source_link="", source_metadata=None):
    created = datetime.now().isoformat()
    return {
        "id": task_id,
        "title": title,
        "sender": sender,
        "state": state,
        "source": source,
        "source_link": source_link,
        "source_metadata": source_metadata or {},
        "times_seen": 1,
        "created": created,
        "updated": created,
    }


class TestBuildEmailQueries:
    def test_returns_one_query(self):
        queries = build_email_queries("March 01, 2026")
        assert len(queries) == 1

    def test_uses_config_template(self):
        config = {
            "email_query_template": "Emails since {since_date}",
        }
        queries = build_email_queries("March 01, 2026", config)
        assert queries[0] == "Emails since March 01, 2026"

    def test_date_interpolation(self):
        queries = build_email_queries("February 28, 2026")
        assert "February 28, 2026" in queries[0]

    def test_default_template_fetches_all_emails(self):
        queries = build_email_queries("March 01, 2026")
        assert "email" in queries[0].lower()


class TestBuildCalendarQuery:
    def test_returns_string_with_date(self):
        query = build_calendar_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"calendar_query_template": "Meeting action items since {since_date}"}
        query = build_calendar_query("March 01, 2026", config)
        assert query == "Meeting action items since March 01, 2026"

    def test_default_mentions_calendar_events(self):
        query = build_calendar_query("March 01, 2026")
        assert "calendar" in query.lower() or "event" in query.lower()


class TestBuildAllQueries:
    """Tests for build_all_queries in legacy single_phase mode."""

    def test_all_sources_enabled(self):
        config = {"sources_enabled": ["teams", "email", "calendar"],
                  "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" in result
        assert "email" in result
        assert "calendar" in result
        assert "conversations" in result["teams"]
        assert isinstance(result["teams"]["conversations"], str)
        assert "all" in result["email"]
        assert "all" in result["calendar"]
        assert "transcript_discovery" in result["calendar"]
        assert "transcript_extraction" in result["calendar"]

    def test_teams_only(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" in result
        assert "email" not in result
        assert "calendar" not in result

    def test_empty_sources_still_has_outbound_and_all_received(self):
        config = {"sources_enabled": [], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" not in result
        assert "email" not in result
        assert "calendar" not in result
        assert "outbound" in result
        assert "all_received" in result
        assert "key_contacts" in result

    def test_default_config_teams_only(self):
        config = {"query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" in result
        assert "email" not in result


class TestFindCrossSourceMatch:
    def test_email_matches_teams_task(self):
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="Follow up on API schema mapping", source="teams"),
        ]
        new_task = {"sender": "Jordan Kim", "title": "API schema mapping follow-up"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is not None
        assert match["id"] == "T-001"

    def test_calendar_matches_teams_task(self):
        existing = [
            _make_task(task_id="T-001", sender="Pat Rivera",
                       title="Send demo readiness update", source="teams"),
        ]
        new_task = {"sender": "Pat Rivera", "title": "Demo readiness update"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is not None
        assert match["id"] == "T-001"

    def test_no_match_different_sender(self):
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="API schema mapping"),
        ]
        new_task = {"sender": "Pat Rivera", "title": "API schema mapping"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is None

    def test_no_match_different_title(self):
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="API schema mapping"),
        ]
        new_task = {"sender": "Jordan Kim", "title": "Quarterly budget review"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is None

    def test_matches_closed_task(self):
        """Closed tasks ARE found now (for dedup to prevent re-creation)."""
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="API schema mapping", state="closed"),
        ]
        new_task = {"sender": "Jordan Kim", "title": "API schema mapping follow-up"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is not None
        assert match["id"] == "T-001"
        assert match["state"] == "closed"

    def test_matches_likely_done_task(self):
        """likely_done tasks ARE found now (for dedup to prevent re-creation)."""
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="API schema mapping", state="likely_done"),
        ]
        new_task = {"sender": "Jordan Kim", "title": "API schema mapping follow-up"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is not None
        assert match["state"] == "likely_done"

    def test_empty_sender_returns_none(self):
        existing = [_make_task()]
        new_task = {"sender": "", "title": "Something"}
        assert find_cross_source_match(new_task, existing) is None

    def test_empty_title_returns_none(self):
        existing = [_make_task()]
        new_task = {"sender": "Jordan Kim", "title": ""}
        assert find_cross_source_match(new_task, existing) is None


class TestMergeCrossSourceSignal:
    def test_bumps_times_seen(self):
        task = _make_task()
        assert task["times_seen"] == 1
        merge_cross_source_signal(task, "email", "https://outlook.office.com/mail/123")
        assert task["times_seen"] == 2

    def test_stores_alternate_link(self):
        task = _make_task()
        merge_cross_source_signal(task, "email", "https://outlook.office.com/mail/123")
        alt_links = task["source_metadata"]["alternate_links"]
        assert len(alt_links) == 1
        assert alt_links[0]["source"] == "email"
        assert alt_links[0]["link"] == "https://outlook.office.com/mail/123"

    def test_no_duplicate_links(self):
        task = _make_task()
        url = "https://outlook.office.com/mail/123"
        merge_cross_source_signal(task, "email", url)
        merge_cross_source_signal(task, "email", url)
        alt_links = task["source_metadata"]["alternate_links"]
        assert len(alt_links) == 1

    def test_multiple_sources(self):
        task = _make_task()
        merge_cross_source_signal(task, "email", "https://outlook.office.com/mail/123")
        merge_cross_source_signal(task, "calendar", "https://teams.microsoft.com/meeting/456")
        alt_links = task["source_metadata"]["alternate_links"]
        assert len(alt_links) == 2
        assert task["times_seen"] == 3

    def test_updates_timestamp(self):
        task = _make_task()
        old_updated = task["updated"]
        merge_cross_source_signal(task, "email", "https://outlook.office.com/mail/123")
        assert task["updated"] >= old_updated


class TestBuildSentItemsQuery:
    def test_returns_string_with_date(self):
        query = build_sent_items_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"sent_items_query_template": "What did I send since {since_date}?"}
        query = build_sent_items_query("March 01, 2026", config)
        assert query == "What did I send since March 01, 2026?"

    def test_default_mentions_sent(self):
        query = build_sent_items_query("March 01, 2026")
        assert "sent" in query.lower()


class TestBuildOutboundQuery:
    def test_returns_string_with_date(self):
        query = build_outbound_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"outbound_query_template": "Pending asks since {since_date}?"}
        query = build_outbound_query("March 01, 2026", config)
        assert query == "Pending asks since March 01, 2026?"

    def test_default_mentions_not_replied(self):
        query = build_outbound_query("March 01, 2026")
        assert "not replied" in query.lower() or "not" in query.lower()


class TestBuildAllReceivedQuery:
    def test_returns_string_with_date(self):
        query = build_all_received_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"all_received_query_template": "All received since {since_date}?"}
        query = build_all_received_query("March 01, 2026", config)
        assert query == "All received since March 01, 2026?"

    def test_no_reply_filter_in_default(self):
        """The all_received query should NOT filter by reply status."""
        query = build_all_received_query("March 01, 2026")
        assert "not replied" not in query.lower()
        assert "not reply" not in query.lower()
        assert "haven't replied" not in query.lower()

    def test_backward_compat_alias(self):
        """build_inbound_dms_query still works as alias."""
        q1 = build_all_received_query("March 01, 2026")
        q2 = build_inbound_dms_query("March 01, 2026")
        assert q1 == q2


class TestBuildKeyContactQueries:
    def test_generates_per_person_queries(self):
        config = {"key_contacts": ["Alice", "Bob", "Charlie"]}
        queries = build_key_contact_queries("March 01, 2026", config)
        assert len(queries) == 3
        assert "Alice" in queries
        assert "Alice" in queries["Alice"]
        assert "March 01, 2026" in queries["Alice"]

    def test_empty_config_returns_empty(self):
        queries = build_key_contact_queries("March 01, 2026", {})
        assert queries == {}

    def test_none_config_returns_empty(self):
        queries = build_key_contact_queries("March 01, 2026", None)
        assert queries == {}

    def test_no_key_contacts_key_returns_empty(self):
        config = {"sources_enabled": ["teams"]}
        queries = build_key_contact_queries("March 01, 2026", config)
        assert queries == {}


class TestBuildAllQueriesWithSentAndOutbound:
    """Tests for legacy single_phase query structure."""

    def test_sent_items_included_when_calendar_enabled(self):
        config = {"sources_enabled": ["teams", "calendar"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" in result
        assert isinstance(result["sent_items"], str)

    def test_sent_items_included_when_email_enabled(self):
        config = {"sources_enabled": ["teams", "email"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" in result

    def test_sent_items_excluded_when_no_calendar_or_email(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" not in result

    def test_outbound_always_included(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "outbound" in result

    def test_outbound_included_with_empty_sources(self):
        config = {"sources_enabled": [], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "outbound" in result

    def test_all_received_always_included(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "all_received" in result

    def test_all_received_included_with_empty_sources(self):
        config = {"sources_enabled": [], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "all_received" in result

    def test_key_contacts_always_included(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "key_contacts" in result

    def test_key_contacts_populated_from_config(self):
        config = {"sources_enabled": ["teams"], "key_contacts": ["Alice", "Bob"],
                  "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert len(result["key_contacts"]) == 2
        assert "Alice" in result["key_contacts"]

    def test_doc_mentions_always_included(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "doc_mentions" in result
        assert "email_notifications" in result["doc_mentions"]
        assert "direct_search" in result["doc_mentions"]

    def test_doc_mentions_included_with_empty_sources(self):
        config = {"sources_enabled": [], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "doc_mentions" in result

    def test_transcript_queries_included_when_calendar_enabled(self):
        config = {"sources_enabled": ["calendar"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "transcript_discovery" in result["calendar"]
        assert "transcript_extraction" in result["calendar"]

    def test_transcript_queries_excluded_when_calendar_not_enabled(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "calendar" not in result


class TestBuildTranscriptQueries:
    def test_returns_two_queries(self):
        queries = build_transcript_queries("March 01, 2026")
        assert len(queries) == 2

    def test_date_interpolation(self):
        queries = build_transcript_queries("March 01, 2026")
        assert "March 01, 2026" in queries[0]
        assert "March 01, 2026" in queries[1]

    def test_uses_config_templates(self):
        config = {
            "transcript_discovery_query_template": "Find transcripts since {since_date}",
            "transcript_extraction_query_template": "Extract items since {since_date}",
        }
        queries = build_transcript_queries("March 01, 2026", config)
        assert queries[0] == "Find transcripts since March 01, 2026"
        assert queries[1] == "Extract items since March 01, 2026"

    def test_discovery_mentions_recording_or_transcript(self):
        queries = build_transcript_queries("March 01, 2026")
        q = queries[0].lower()
        assert "recording" in q or "transcript" in q

    def test_extraction_mentions_action_items(self):
        queries = build_transcript_queries("March 01, 2026")
        q = queries[1].lower()
        assert "action item" in q or "commitment" in q


class TestBuildDocMentionsQueries:
    def test_returns_dict_with_two_keys(self):
        result = build_doc_mentions_queries("March 01, 2026")
        assert isinstance(result, dict)
        assert "email_notifications" in result
        assert "direct_search" in result

    def test_uses_config_email_template(self):
        config = {"doc_mentions_email_query_template": "Custom email query"}
        result = build_doc_mentions_queries("March 01, 2026", config)
        assert result["email_notifications"] == "Custom email query"

    def test_uses_config_direct_template(self):
        config = {"doc_mentions_direct_query_template": "Docs since {since_date}"}
        result = build_doc_mentions_queries("March 01, 2026", config)
        assert result["direct_search"] == "Docs since March 01, 2026"

    def test_default_email_mentions_mentioned_you(self):
        result = build_doc_mentions_queries("March 01, 2026")
        assert "mentioned you in" in result["email_notifications"]

    def test_date_interpolation_in_direct(self):
        result = build_doc_mentions_queries("February 28, 2026")
        assert "February 28, 2026" in result["direct_search"]


# ---------------------------------------------------------------------------
# New 2-Phase Query Tests
# ---------------------------------------------------------------------------


class TestBuildDiscoveryQueries:
    def test_returns_all_enabled_sources(self):
        config = {"sources_enabled": ["teams", "email", "calendar"]}
        result = build_discovery_queries("March 01, 2026", config)
        assert "chats" in result
        assert "email" in result
        assert "sent_items" in result
        assert "calendar" in result

    def test_chats_discovery_no_message_content(self):
        config = {"sources_enabled": ["teams"]}
        result = build_discovery_queries("March 01, 2026", config)
        q = result["chats"].lower()
        assert "do not show message content" in q

    def test_email_discovery_includes_all(self):
        config = {"sources_enabled": ["email"]}
        result = build_discovery_queries("March 01, 2026", config)
        q = result["email"].lower()
        assert "include all emails" in q

    def test_sent_items_included_when_email_or_calendar(self):
        for source in ["email", "calendar"]:
            config = {"sources_enabled": [source]}
            result = build_discovery_queries("March 01, 2026", config)
            assert "sent_items" in result

    def test_uses_config_templates(self):
        config = {
            "sources_enabled": ["teams"],
            "chats_discovery_query_template": "Custom chats since {since_date}",
        }
        result = build_discovery_queries("March 01, 2026", config)
        assert result["chats"] == "Custom chats since March 01, 2026"

    def test_empty_sources_still_has_chats(self):
        config = {"sources_enabled": []}
        result = build_discovery_queries("March 01, 2026", config)
        assert "chats" in result
        assert "email" not in result


class TestBuildDetailQueries:
    def test_chats_one_query_per_item(self):
        items = [
            {"chat_type": "1:1", "chat_name": "Jordan Kim"},
            {"chat_type": "group", "chat_name": "API Review"},
            {"chat_type": "channel", "chat_name": "General"},
        ]
        queries = build_detail_queries("chats", items, "March 01, 2026")
        assert len(queries) == 3

    def test_email_one_query_per_item(self):
        items = [
            {"sender": "Alice", "subject": "Budget proposal"},
            {"sender": "Bob", "subject": "Design review"},
        ]
        queries = build_detail_queries("email", items, "March 01, 2026")
        assert len(queries) == 2

    def test_sent_items_includes_reply_check(self):
        items = [
            {"recipient": "Alice", "subject": "Question", "date": "March 05"},
        ]
        queries = build_detail_queries("sent_items", items, "March 01, 2026")
        assert len(queries) == 1
        assert "replies" in queries[0].lower() or "reply" in queries[0].lower()

    def test_unknown_source_returns_empty(self):
        queries = build_detail_queries("foo", [{"a": 1}], "March 01, 2026")
        assert queries == []

    def test_empty_items_returns_empty(self):
        queries = build_detail_queries("chats", [], "March 01, 2026")
        assert queries == []

    def test_max_limit_applied(self):
        items = [{"chat_type": "1:1", "chat_name": f"Person {i}"} for i in range(10)]
        config = {"max_detail_queries_per_source": 3}
        queries = build_detail_queries("chats", items, "March 01, 2026", config)
        assert len(queries) == 3


class TestBuildAllQueriesV3:
    """Tests for 2-phase (default) query structure."""

    def test_has_phase1_key(self):
        config = {"sources_enabled": ["teams", "email", "calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "phase1" in result

    def test_phase1_has_all_sources(self):
        config = {"sources_enabled": ["teams", "email", "calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "chats" in result["phase1"]
        assert "email" in result["phase1"]
        assert "sent_items" in result["phase1"]
        assert "calendar" in result["phase1"]

    def test_has_validation_key(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "validation" in result

    def test_legacy_mode(self):
        config = {"sources_enabled": ["teams"], "query_strategy": "single_phase"}
        result = build_all_queries("March 01, 2026", config)
        assert "phase1" not in result
        assert "teams" in result

    def test_transcript_queries_present(self):
        config = {"sources_enabled": ["calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "transcript_discovery" in result
        assert "transcript_extraction" in result

    def test_doc_mentions_present(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "doc_mentions" in result

    def test_no_key_contacts_at_top_level(self):
        """key_contacts removed in 2-phase — replaced by Phase 1 chat discovery."""
        config = {"sources_enabled": ["teams"], "key_contacts": ["Alice"]}
        result = build_all_queries("March 01, 2026", config)
        assert "key_contacts" not in result


class TestBuildValidationQuery:
    def test_returns_string_with_date(self):
        query = build_validation_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"validation_query_template": "My tasks since {since_date}"}
        query = build_validation_query("March 01, 2026", config)
        assert query == "My tasks since March 01, 2026"

    def test_default_mentions_commitments(self):
        query = build_validation_query("March 01, 2026")
        assert "commitment" in query.lower()


class TestMergeDuplicates:
    def _make_dup_task(self, task_id, title, thread_id="", meeting_title="",
                       state="open", created=None):
        now = datetime.now()
        created = created or now.isoformat()
        return {
            "id": task_id,
            "title": title,
            "sender": "Test User",
            "state": state,
            "source": "teams",
            "source_link": "",
            "source_metadata": {"meeting_title": meeting_title} if meeting_title else {},
            "times_seen": 1,
            "created": created,
            "updated": created,
            "thread_id": thread_id,
            "description": "",
            "state_history": [],
        }

    def test_same_thread_similar_title_merged(self):
        t1 = self._make_dup_task("TASK-001", "Follow up on API schema mapping",
                                 thread_id="19:abc",
                                 created="2026-03-01T10:00:00")
        t2 = self._make_dup_task("TASK-002", "Follow up API schema mapping status",
                                 thread_id="19:abc",
                                 created="2026-03-02T10:00:00")
        tasks = [t1, t2]
        result = merge_duplicates(tasks)
        assert len(result) == 1
        kept_id, merged_ids = result[0]
        assert kept_id == "TASK-002"  # newest
        assert "TASK-001" in merged_ids

    def test_different_thread_different_sender_not_merged(self):
        t1 = self._make_dup_task("TASK-001", "Follow up on API schema mapping",
                                 thread_id="19:abc")
        t1["sender"] = "Alice"
        t2 = self._make_dup_task("TASK-002", "Follow up on API schema mapping",
                                 thread_id="19:def")
        t2["sender"] = "Bob"
        tasks = [t1, t2]
        result = merge_duplicates(tasks)
        assert len(result) == 0

    def test_newest_id_kept(self):
        t1 = self._make_dup_task("TASK-001", "Review budget proposal",
                                 thread_id="19:abc",
                                 created="2026-03-01T10:00:00")
        t2 = self._make_dup_task("TASK-002", "Review budget proposal",
                                 thread_id="19:abc",
                                 created="2026-03-03T10:00:00")
        tasks = [t1, t2]
        merge_duplicates(tasks)
        assert t2["state"] == "open"  # kept
        assert t1["state"] == "closed"  # merged away

    def test_merge_note_appended(self):
        t1 = self._make_dup_task("TASK-001", "Review budget proposal",
                                 thread_id="19:abc",
                                 created="2026-03-01T10:00:00")
        t2 = self._make_dup_task("TASK-002", "Review budget proposal",
                                 thread_id="19:abc",
                                 created="2026-03-03T10:00:00")
        tasks = [t1, t2]
        merge_duplicates(tasks)
        assert "Merged: TASK-001" in t2.get("description", "")

    def test_dissimilar_titles_not_merged(self):
        t1 = self._make_dup_task("TASK-001", "Review budget proposal",
                                 thread_id="19:abc")
        t2 = self._make_dup_task("TASK-002", "Schedule meeting with Casey",
                                 thread_id="19:abc")
        tasks = [t1, t2]
        result = merge_duplicates(tasks)
        assert len(result) == 0
        assert t1["state"] == "open"
        assert t2["state"] == "open"

    def test_merge_duplicates_sender_grouping(self):
        """Two tasks from the same sender with near-identical titles but different thread_ids should merge."""
        t1 = _make_task(task_id="TASK-S1", sender="Jordan Kim",
                        title="Follow up on API schema mapping",
                        source="teams")
        t1["thread_id"] = "19:thread-aaa"
        t1["created"] = "2026-03-08T10:00:00"
        t1["updated"] = "2026-03-08T10:00:00"
        t2 = _make_task(task_id="TASK-S2", sender="Jordan Kim",
                        title="Follow up on API schema mapping review",
                        source="email")
        t2["thread_id"] = "19:thread-bbb"
        t2["created"] = "2026-03-09T10:00:00"
        t2["updated"] = "2026-03-09T10:00:00"
        tasks = [t1, t2]
        result = merge_duplicates(tasks)
        assert len(result) == 1
        kept_id, merged_ids = result[0]
        assert kept_id == "TASK-S2"  # newer task kept
        assert "TASK-S1" in merged_ids
        assert t1["state"] == "closed"
