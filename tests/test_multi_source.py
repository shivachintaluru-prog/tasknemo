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
    build_inbound_dms_query,
    merge_duplicates,
    build_doc_mentions_queries,
    build_transcript_queries,
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
    def test_all_sources_enabled(self):
        config = {"sources_enabled": ["teams", "email", "calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" in result
        assert "email" in result
        assert "calendar" in result
        # v2 structure: no separate completion keys
        assert "conversations" in result["teams"]
        assert isinstance(result["teams"]["conversations"], str)
        assert "all" in result["email"]
        assert "all" in result["calendar"]
        assert "transcript_discovery" in result["calendar"]
        assert "transcript_extraction" in result["calendar"]

    def test_teams_only(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "teams" in result
        assert "email" not in result
        assert "calendar" not in result

    def test_empty_sources_still_has_outbound_and_inbound_dms(self):
        config = {"sources_enabled": []}
        result = build_all_queries("March 01, 2026", config)
        # No teams/email/calendar, but outbound + inbound_dms are always present
        assert "teams" not in result
        assert "email" not in result
        assert "calendar" not in result
        assert "outbound" in result
        assert "inbound_dms" in result

    def test_default_config_teams_only(self):
        # No sources_enabled key defaults to teams only
        result = build_all_queries("March 01, 2026", {})
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

    def test_closed_tasks_excluded(self):
        existing = [
            _make_task(task_id="T-001", sender="Jordan Kim",
                       title="API schema mapping", state="closed"),
        ]
        new_task = {"sender": "Jordan Kim", "title": "API schema mapping follow-up"}
        match = find_cross_source_match(new_task, existing, threshold=0.5)
        assert match is None

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


class TestBuildInboundDmsQuery:
    def test_returns_string_with_date(self):
        query = build_inbound_dms_query("March 01, 2026")
        assert isinstance(query, str)
        assert "March 01, 2026" in query

    def test_uses_config_template(self):
        config = {"inbound_dms_query_template": "Unreplied DMs since {since_date}?"}
        query = build_inbound_dms_query("March 01, 2026", config)
        assert query == "Unreplied DMs since March 01, 2026?"

    def test_default_mentions_replied(self):
        query = build_inbound_dms_query("March 01, 2026")
        assert "replied" in query.lower() or "reply" in query.lower()


class TestBuildAllQueriesWithSentAndOutbound:
    def test_sent_items_included_when_calendar_enabled(self):
        config = {"sources_enabled": ["teams", "calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" in result
        assert isinstance(result["sent_items"], str)

    def test_sent_items_included_when_email_enabled(self):
        config = {"sources_enabled": ["teams", "email"]}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" in result

    def test_sent_items_excluded_when_no_calendar_or_email(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "sent_items" not in result

    def test_outbound_always_included(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "outbound" in result

    def test_outbound_included_with_empty_sources(self):
        config = {"sources_enabled": []}
        result = build_all_queries("March 01, 2026", config)
        assert "outbound" in result

    def test_inbound_dms_always_included(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "inbound_dms" in result

    def test_inbound_dms_included_with_empty_sources(self):
        config = {"sources_enabled": []}
        result = build_all_queries("March 01, 2026", config)
        assert "inbound_dms" in result

    def test_doc_mentions_always_included(self):
        config = {"sources_enabled": ["teams"]}
        result = build_all_queries("March 01, 2026", config)
        assert "doc_mentions" in result
        assert "email_notifications" in result["doc_mentions"]
        assert "direct_search" in result["doc_mentions"]

    def test_doc_mentions_included_with_empty_sources(self):
        config = {"sources_enabled": []}
        result = build_all_queries("March 01, 2026", config)
        assert "doc_mentions" in result

    def test_transcript_queries_included_when_calendar_enabled(self):
        config = {"sources_enabled": ["calendar"]}
        result = build_all_queries("March 01, 2026", config)
        assert "transcript_discovery" in result["calendar"]
        assert "transcript_extraction" in result["calendar"]

    def test_transcript_queries_excluded_when_calendar_not_enabled(self):
        config = {"sources_enabled": ["teams"]}
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

    def test_different_thread_not_merged(self):
        t1 = self._make_dup_task("TASK-001", "Follow up on API schema mapping",
                                 thread_id="19:abc")
        t2 = self._make_dup_task("TASK-002", "Follow up on API schema mapping",
                                 thread_id="19:def")
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
