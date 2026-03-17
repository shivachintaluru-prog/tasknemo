"""Query builders — discovery, detail, validation, all WorkIQ queries."""

from datetime import datetime, timedelta

from .dedup import STOP_WORDS  # re-export for backward compat


def calculate_since_date(last_run, overlap_days=2):
    """Return a human-readable date string for 'since' queries."""
    today = datetime.now()
    if last_run is None:
        since = today - timedelta(days=7)
    else:
        last = datetime.fromisoformat(last_run)
        since = last - timedelta(days=overlap_days)
    return since.strftime("%B %d, %Y")


def build_workiq_queries(since_date, config=None):
    """Return the WorkIQ conversation query for task extraction."""
    template = (config or {}).get(
        "conversation_query_template",
        "Show me all my Teams conversations since {since_date}",
    )
    return [template.format(since_date=since_date)]


def build_followup_queries(open_tasks, max_queries=5):
    """Return per-task WorkIQ follow-up queries (DEPRECATED)."""
    queries = []
    for task in open_tasks[:max_queries]:
        sender = task.get("sender", "someone")
        title = task.get("title", "a task")
        queries.append({
            "task_id": task["id"],
            "query": f"Has there been any update about '{title}' with {sender} in Teams recently?",
        })
    return queries


def build_completion_query(since_date, config=None):
    """Return the WorkIQ completion-detection query."""
    template = (config or {}).get(
        "completion_query_template",
        "Which of my Teams conversations since {since_date} have been "
        "resolved or completed, where someone said thanks or confirmed "
        "something was finished?",
    )
    return template.format(since_date=since_date)


def build_email_queries(since_date, config=None):
    """Return WorkIQ email query as a raw data fetch."""
    cfg = config or {}
    template = cfg.get(
        "email_query_template",
        "What emails did I receive since {since_date}? "
        "For each show: sender name, subject, date, and body preview. "
        "Include all emails.",
    )
    return [template.format(since_date=since_date)]


def build_calendar_query(since_date, config=None):
    """Return WorkIQ calendar query as a raw data fetch."""
    template = (config or {}).get(
        "calendar_query_template",
        "Show me ALL my calendar events since {since_date}. Include: "
        "title, date/time, attendees, any meeting notes, and the link.",
    )
    return template.format(since_date=since_date)


def build_transcript_queries(since_date, config=None):
    """Return 2 WorkIQ queries for meeting transcript analysis."""
    cfg = config or {}
    discovery_template = cfg.get(
        "transcript_discovery_query_template",
        "Show me ALL my meetings since {since_date} that have a recording "
        "or transcript available. For each meeting, include the title, date, "
        "attendees, and the recording/transcript link.",
    )
    extraction_template = cfg.get(
        "transcript_extraction_query_template",
        "For each of my meetings since {since_date} that has a transcript, "
        "read the transcript and extract ALL action items and commitments. "
        "For each one include: (1) what the action item is, (2) who committed "
        "to it — me or someone else, (3) any deadline mentioned, (4) the "
        "meeting title and link. Be exhaustive — include every commitment, "
        "even small ones.",
    )
    return [
        discovery_template.format(since_date=since_date),
        extraction_template.format(since_date=since_date),
    ]


def build_sent_items_query(since_date, config=None):
    """Return 1 WorkIQ query to check user's own completed actions."""
    template = (config or {}).get(
        "sent_items_query_template",
        "Check my sent emails and outgoing Teams messages since {since_date}. "
        "What actions have I already completed? Look for emails I sent, "
        "documents I shared, replies I gave, and messages where I delivered "
        "on a commitment. For each, include what I did, who I sent it to, "
        "when, and the link.",
    )
    return template.format(since_date=since_date)


def build_outbound_query(since_date, config=None):
    """Return WorkIQ outbound query as a raw data fetch."""
    template = (config or {}).get(
        "outbound_query_template",
        "Show me ALL my sent messages and emails since {since_date} where "
        "the recipient has NOT replied. Include: recipient, what I said, "
        "when, and the link.",
    )
    return template.format(since_date=since_date)


def build_all_received_query(since_date, config=None):
    """Return 1 WorkIQ query for ALL received messages."""
    template = (config or {}).get(
        "all_received_query_template",
        "Show me ALL messages I received in ALL Teams chats (1:1, group chats, "
        "and channels) since {since_date}. Include: sender name, full message "
        "text, chat/channel name, timestamp, and the Teams link. Do not filter "
        "by reply status. Do not summarize — show actual message content.",
    )
    return template.format(since_date=since_date)


# Keep old name as alias for backwards compatibility in tests
build_inbound_dms_query = build_all_received_query


def build_key_contact_queries(since_date, config=None):
    """Return per-person WorkIQ queries for key contacts."""
    contacts = (config or {}).get("key_contacts", [])
    queries = {}
    for name in contacts:
        queries[name] = (
            f"Show me ALL messages from {name} sent to me since {since_date}. "
            "Show the exact message text, timestamp, and chat name. "
            "Do not summarize."
        )
    return queries


def build_doc_mentions_queries(since_date, config=None):
    """Return 2 WorkIQ queries for document/channel mentions."""
    cfg = config or {}
    email_template = cfg.get(
        "doc_mentions_email_query_template",
        'Show me all emails where the subject contains "mentioned you in". '
        "For each email, show the COMPLETE email body verbatim including the "
        "comment text, document name, who mentioned me, and any @mentions or "
        "task assignments. Do not summarize.",
    )
    direct_template = cfg.get(
        "doc_mentions_direct_query_template",
        "Show me all documents, Word files, PowerPoint files, and Loop pages "
        "where someone has @mentioned me or assigned a task to me since "
        "{since_date}. For each, show who mentioned me, the exact comment text "
        "verbatim, the document name, and the document link.",
    )
    return {
        "email_notifications": email_template,
        "direct_search": direct_template.format(since_date=since_date),
    }


def build_discovery_queries(since_date, config=None):
    """Return Phase 1 (discovery) queries keyed by source."""
    cfg = config or {}
    enabled = cfg.get("sources_enabled", ["teams"])
    result = {}

    chats_template = cfg.get(
        "chats_discovery_query_template",
        "List all Teams chats (1:1, group, channels) where I received or "
        "sent messages since {since_date}. For each, show: chat name, chat "
        "type (1:1/group/channel), the other participants. Do not show "
        "message content.",
    )
    result["chats"] = chats_template.format(since_date=since_date)

    if "email" in enabled:
        email_template = cfg.get(
            "email_discovery_query_template",
            "What emails did I receive since {since_date}? "
            "For each show: sender name, subject, and date received. "
            "Include all emails.",
        )
        result["email"] = email_template.format(since_date=since_date)

    if "calendar" in enabled or "email" in enabled:
        sent_template = cfg.get(
            "sent_items_discovery_query_template",
            "List all emails I sent and Teams messages I posted since "
            "{since_date}. For each: recipient(s), subject or topic, date, "
            "and whether they replied. Do not include body text.",
        )
        result["sent_items"] = sent_template.format(since_date=since_date)

    if "calendar" in enabled:
        cal_template = cfg.get(
            "calendar_discovery_query_template",
            "List all my calendar events since {since_date}. For each: "
            "title, date/time, attendees, and whether a transcript or "
            "recording is available.",
        )
        result["calendar"] = cal_template.format(since_date=since_date)

    return result


def _build_chats_detail_queries(items, since_date, config):
    """Return per-chat detail queries from discovery items."""
    cfg = config or {}
    template = cfg.get(
        "chats_detail_query_template",
        "Show me the recent conversation in my Teams {chat_type} chat "
        "called \"{chat_name}\". I need to see every message since "
        "{since_date} — show who said what with the actual text of each message.",
    )
    queries = []
    for item in items:
        queries.append(template.format(
            chat_type=item.get("chat_type", "1:1"),
            chat_name=item.get("chat_name", "Unknown"),
            since_date=since_date,
        ))
    return queries


def _build_email_detail_queries(items, since_date, config):
    """Return per-email detail queries from discovery items."""
    cfg = config or {}
    template = cfg.get(
        "email_detail_query_template",
        "Show me the full email from {sender} with subject '{subject}'. "
        "Include complete body, all recipients, and Outlook link.",
    )
    queries = []
    for item in items:
        queries.append(template.format(
            sender=item.get("sender", "Unknown"),
            subject=item.get("subject", ""),
            since_date=since_date,
        ))
    return queries


def _build_sent_items_detail_queries(items, since_date, config):
    """Return per-sent-item detail queries from discovery items."""
    cfg = config or {}
    template = cfg.get(
        "sent_items_detail_query_template",
        "Show me what I sent to {recipient} about '{subject}' on {date}, "
        "and show any replies they sent back. Include full text and links.",
    )
    queries = []
    for item in items:
        queries.append(template.format(
            recipient=item.get("recipient", "Unknown"),
            subject=item.get("subject", ""),
            date=item.get("date", ""),
            since_date=since_date,
        ))
    return queries


def build_detail_queries(source, discovery_items, since_date, config=None):
    """Build Phase 2 (detail) queries from Phase 1 discovery results."""
    cfg = config or {}
    max_queries = cfg.get("max_detail_queries_per_source", 25)
    items = discovery_items[:max_queries]

    builders = {
        "chats": _build_chats_detail_queries,
        "email": _build_email_detail_queries,
        "sent_items": _build_sent_items_detail_queries,
    }
    builder = builders.get(source)
    if builder is None:
        return []
    return builder(items, since_date, cfg)


def build_validation_query(since_date, config=None):
    """Return the Phase 3 validation query for cross-checking extracted tasks."""
    template = (config or {}).get(
        "validation_query_template",
        "What are all my pending tasks, action items, and open commitments "
        "since {since_date}? Include anything someone asked me to do, anything "
        "I committed to in a meeting, and any emails or messages that need my "
        "response. For each, show: who asked, what they need, and the source.",
    )
    return template.format(since_date=since_date)


def _build_all_queries_legacy(since_date, config):
    """Legacy single-phase query builder (backward compat)."""
    cfg = config or {}
    enabled = cfg.get("sources_enabled", ["teams"])
    result = {}

    if "teams" in enabled:
        convos = build_workiq_queries(since_date, cfg)
        result["teams"] = {
            "conversations": convos[0] if convos else "",
        }

    if "email" in enabled:
        email_qs = build_email_queries(since_date, cfg)
        result["email"] = {
            "all": email_qs[0],
        }

    if "calendar" in enabled:
        transcript_qs = build_transcript_queries(since_date, cfg)
        result["calendar"] = {
            "all": build_calendar_query(since_date, cfg),
            "transcript_discovery": transcript_qs[0],
            "transcript_extraction": transcript_qs[1],
        }

    if "calendar" in enabled or "email" in enabled:
        result["sent_items"] = build_sent_items_query(since_date, cfg)

    result["outbound"] = build_outbound_query(since_date, cfg)
    result["all_received"] = build_all_received_query(since_date, cfg)
    result["key_contacts"] = build_key_contact_queries(since_date, cfg)
    result["doc_mentions"] = build_doc_mentions_queries(since_date, cfg)

    return result


def build_all_queries(since_date, config=None):
    """Build queries for all enabled sources."""
    cfg = config or {}

    if cfg.get("query_strategy") == "single_phase":
        return _build_all_queries_legacy(since_date, cfg)

    result = {}

    result["phase1"] = build_discovery_queries(since_date, cfg)

    enabled = cfg.get("sources_enabled", ["teams"])
    if "calendar" in enabled:
        transcript_qs = build_transcript_queries(since_date, cfg)
        result["transcript_discovery"] = transcript_qs[0]
        result["transcript_extraction"] = transcript_qs[1]

    result["doc_mentions"] = build_doc_mentions_queries(since_date, cfg)

    # New sources (Step 4)
    if "flagged_email" in enabled:
        result["flagged_emails"] = build_flagged_emails_query(since_date, cfg)
    if "planner" in enabled:
        result["planner"] = build_planner_query(since_date, cfg)

    result["validation"] = build_validation_query(since_date, cfg)

    return result


def build_flagged_emails_query(since_date, config=None):
    """Return WorkIQ query for flagged/starred emails."""
    template = (config or {}).get(
        "flagged_emails_query_template",
        "List all my flagged or starred emails that are not completed. "
        "For each, include: sender, subject, date flagged, body preview, "
        "and the Outlook link.",
    )
    return template.format(since_date=since_date)


def build_planner_query(since_date, config=None):
    """Return WorkIQ query for Planner/To-Do tasks."""
    template = (config or {}).get(
        "planner_query_template",
        "List all my Microsoft Planner tasks and To-Do items that are not "
        "completed. For each, include: task title, who assigned it, due date, "
        "plan/list name, and the link.",
    )
    return template.format(since_date=since_date)
