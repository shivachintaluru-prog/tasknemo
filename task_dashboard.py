"""
TaskNemo — Task Extraction and Priority Dashboard

Extracts tasks from Teams (via WorkIQ MCP), manages their lifecycle,
scores priorities, and renders a markdown dashboard for Obsidian.

Architecture: Claude Code is the orchestrator. It calls WorkIQ MCP for
natural-language queries, uses its reasoning to interpret responses, and
invokes the deterministic functions in this script for dedup, scoring,
state transitions, and rendering.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
TASKS_PATH = os.path.join(DATA_DIR, "tasks.json")
RUN_LOG_PATH = os.path.join(DATA_DIR, "run_log.json")

# ---------------------------------------------------------------------------
# Config & Store I/O
# ---------------------------------------------------------------------------


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_config():
    return load_json(CONFIG_PATH)


def save_config(config):
    save_json(CONFIG_PATH, config)


def load_tasks():
    return load_json(TASKS_PATH)


def save_tasks(store):
    save_json(TASKS_PATH, store)


def load_run_log():
    return load_json(RUN_LOG_PATH)


def save_run_log(log):
    save_json(RUN_LOG_PATH, log)


# ---------------------------------------------------------------------------
# Analytics I/O & Learning
# ---------------------------------------------------------------------------

ANALYTICS_PATH = os.path.join(DATA_DIR, "analytics.json")

_ANALYTICS_DEFAULT = {"response_times": {}, "escalation_history": {}, "user_pins": []}


def load_analytics():
    """Load analytics.json, returning defaults if missing or corrupt."""
    try:
        return load_json(ANALYTICS_PATH)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_ANALYTICS_DEFAULT)


def save_analytics(data):
    """Persist analytics data."""
    save_json(ANALYTICS_PATH, data)


def record_response_time(sender, hours, analytics=None):
    """Track running average response time for a sender.

    Updates analytics in-place and saves.
    """
    if analytics is None:
        analytics = load_analytics()
    key = sender.lower().strip()
    rt = analytics.setdefault("response_times", {})
    if key in rt:
        prev = rt[key]
        prev["count"] += 1
        prev["avg"] = prev["avg"] + (hours - prev["avg"]) / prev["count"]
    else:
        rt[key] = {"avg": hours, "count": 1}
    save_analytics(analytics)
    return analytics


def get_response_time_factor(sender, analytics=None):
    """Return 0-10 score factor based on avg response time.

    Slow responders (avg > 24h) get the max bump. Returns 0 if insufficient data.
    """
    if analytics is None:
        return 0
    key = sender.lower().strip()
    entry = analytics.get("response_times", {}).get(key)
    if not entry or entry["count"] < 2:
        return 0
    avg = entry["avg"]
    if avg <= 4:
        return 0
    if avg <= 12:
        return 3
    if avg <= 24:
        return 6
    return 10


def record_mention(task_id, urgency_hits, analytics=None):
    """Log a mention with its urgency level for escalation tracking."""
    if analytics is None:
        analytics = load_analytics()
    history = analytics.setdefault("escalation_history", {})
    entries = history.setdefault(task_id, [])
    if len(entries) < 5:
        entries.append({"urgency": urgency_hits, "ts": datetime.now().isoformat()})
    save_analytics(analytics)
    return analytics


def get_escalation_bonus(task_id, analytics=None):
    """Return 0-15 based on increasing urgency pattern across mentions.

    A single mention returns 0. Increasing urgency across 2+ mentions
    scores higher (up to 15).
    """
    if analytics is None:
        return 0
    entries = analytics.get("escalation_history", {}).get(task_id, [])
    if len(entries) < 2:
        return 0
    urgencies = [e["urgency"] for e in entries]
    # Count how many times urgency increased vs decreased
    increases = sum(1 for i in range(1, len(urgencies)) if urgencies[i] > urgencies[i - 1])
    if increases == 0:
        return 3  # repeated mentions without escalation still gets a small bump
    return min(increases * 5 + 3, 15)


def pin_task(task_id, analytics=None):
    """Add task to user_pins list. No-op if already pinned."""
    if analytics is None:
        analytics = load_analytics()
    pins = analytics.setdefault("user_pins", [])
    if task_id not in pins:
        pins.append(task_id)
    save_analytics(analytics)
    return analytics


def unpin_task(task_id, analytics=None):
    """Remove task from user_pins list. No-op if not pinned."""
    if analytics is None:
        analytics = load_analytics()
    pins = analytics.setdefault("user_pins", [])
    if task_id in pins:
        pins.remove(task_id)
    save_analytics(analytics)
    return analytics


def get_pin_bonus(task_id, analytics=None):
    """Return 20 if task is pinned, else 0."""
    if analytics is None:
        return 0
    return 20 if task_id in analytics.get("user_pins", []) else 0


# ---------------------------------------------------------------------------
# Phase 1: Query Pipeline
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "to", "for", "of", "in", "on", "at", "is", "it",
    "and", "or", "but", "with", "by", "from", "up", "about", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "out", "off", "over", "under", "again", "further", "then", "once",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "this", "that", "these",
    "those", "am", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "shall", "should",
    "may", "might", "must", "can", "could", "not", "no", "nor", "so",
    "too", "very", "just", "also",
}


def calculate_since_date(last_run, overlap_days=2):
    """Return a human-readable date string for 'since' queries.

    If last_run is None (first run), defaults to 7 days ago.
    Otherwise, goes back to last_run minus overlap_days for safe coverage.
    """
    today = datetime.now()
    if last_run is None:
        since = today - timedelta(days=7)
    else:
        last = datetime.fromisoformat(last_run)
        since = last - timedelta(days=overlap_days)
    return since.strftime("%B %d, %Y")


def build_workiq_queries(since_date, config=None):
    """Return the WorkIQ conversation query for task extraction.

    Returns a single broad query that asks for ALL recent conversations,
    replacing the previous 3 narrow queries. Claude Code then reasons over
    the full conversation dump to extract tasks, detect completions, etc.
    """
    template = (config or {}).get(
        "conversation_query_template",
        "Show me all my Teams conversations since {since_date}",
    )
    return [template.format(since_date=since_date)]


def build_followup_queries(open_tasks, max_queries=5):
    """Return per-task WorkIQ follow-up queries for existing open tasks.

    DEPRECATED: Kept for backward compatibility. New sync flow uses
    build_completion_query() instead of per-task followups.
    """
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
    """Return the WorkIQ completion-detection query.

    Asks WorkIQ which conversations have been resolved/completed,
    replacing the per-task followup queries with a single broad query.
    """
    template = (config or {}).get(
        "completion_query_template",
        "Which of my Teams conversations since {since_date} have been "
        "resolved or completed, where someone said thanks or confirmed "
        "something was finished?",
    )
    return template.format(since_date=since_date)


def build_email_queries(since_date, config=None):
    """Return WorkIQ email query as a raw data fetch.

    Returns a single broad query that fetches ALL emails (not just
    action-required). Claude reasons locally over the raw email list +
    sent items to determine what needs action vs. what's resolved.

    For backward compat, still returns a list — but with 1 element.
    """
    cfg = config or {}
    template = cfg.get(
        "email_query_template",
        "Show me ALL my emails since {since_date}. For each, include: "
        "sender, subject, body preview, date, whether I replied, and "
        "the Outlook link.",
    )
    return [template.format(since_date=since_date)]


def build_calendar_query(since_date, config=None):
    """Return WorkIQ calendar query as a raw data fetch.

    Fetches ALL calendar events — Claude reasons locally to identify
    action items rather than asking WorkIQ to filter.
    """
    template = (config or {}).get(
        "calendar_query_template",
        "Show me ALL my calendar events since {since_date}. Include: "
        "title, date/time, attendees, any meeting notes, and the link.",
    )
    return template.format(since_date=since_date)


def build_transcript_queries(since_date, config=None):
    """Return 2 WorkIQ queries for meeting transcript analysis.

    Query 1: Find all meetings with transcripts/recordings available.
    Query 2: For each transcribed meeting, extract ALL commitments —
    both inbound (user committed) and outbound (others committed to user).
    """
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
    """Return 1 WorkIQ query to check user's own completed actions.

    Used to detect self-completion: the user committed to do something
    (e.g., in a meeting) and already did it (sent the email, shared the doc).
    """
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
    """Return WorkIQ outbound query as a raw data fetch.

    Fetches ALL sent messages where the recipient has NOT replied.
    Claude reasons locally to determine which are trackable requests.
    """
    template = (config or {}).get(
        "outbound_query_template",
        "Show me ALL my sent messages and emails since {since_date} where "
        "the recipient has NOT replied. Include: recipient, what I said, "
        "when, and the link.",
    )
    return template.format(since_date=since_date)


def build_all_received_query(since_date, config=None):
    """Return 1 WorkIQ query for ALL received messages (not just unreplied).

    Replaces the old unreplied-only DM query to avoid missing tasks in
    conversations where the user already replied to earlier messages.
    """
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
    """Return per-person WorkIQ queries for key contacts.

    Fills WorkIQ's recall gaps — broad queries miss conversations,
    but targeted per-person queries reliably return results.
    """
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
    """Return 2 WorkIQ queries for document/channel mentions.

    Query 1 (email pattern): Find notification emails where someone mentioned
    the user in a document. Subjects like "X mentioned you in Y" contain the
    actual comment text in the body.

    Query 2 (direct search): Ask WorkIQ for documents where someone recently
    @mentioned or assigned a task to the user.
    """
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
    """Return Phase 1 (discovery) queries keyed by source.

    These are lightweight enumeration queries — list names/subjects only,
    no message body text. WorkIQ handles simple listing reliably.
    """
    cfg = config or {}
    enabled = cfg.get("sources_enabled", ["teams"])
    result = {}

    # Chats discovery — replaces both teams + all_received
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
            "List all emails I received since {since_date} from real people "
            "(exclude automated notifications, newsletters, bot messages). "
            "For each: sender name, subject, date, and whether I replied. "
            "Do not include body text.",
        )
        result["email"] = email_template.format(since_date=since_date)

    # Sent items discovery — replaces both sent_items + outbound
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
        "Show me all messages in my {chat_type} chat '{chat_name}' since "
        "{since_date}. Include sender, full message text, timestamp, Teams "
        "link. Do not summarize.",
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
    """Build Phase 2 (detail) queries from Phase 1 discovery results.

    Takes structured discovery items and returns per-item detail query strings.
    Respects max_detail_queries_per_source config limit.
    """
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
    """Return the Phase 3 validation query for cross-checking extracted tasks.

    Run AFTER all Phase 1+2 extraction. Compare WorkIQ's interpretive task
    list against already-extracted tasks to identify potential gaps.
    Do NOT blindly create tasks from this — verify against raw data first.
    """
    template = (config or {}).get(
        "validation_query_template",
        "What are all my pending tasks, action items, and open commitments "
        "since {since_date}? Include anything someone asked me to do, anything "
        "I committed to in a meeting, and any emails or messages that need my "
        "response. For each, show: who asked, what they need, and the source.",
    )
    return template.format(since_date=since_date)


def _build_all_queries_legacy(since_date, config):
    """Legacy single-phase query builder (backward compat).

    Returns the old flat dict structure keyed by source.
    """
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
    """Build queries for all enabled sources.

    Two modes controlled by config["query_strategy"]:
    - "single_phase" → legacy flat dict (backward compat)
    - "two_phase" (default) → Phase 1 discovery + targeted queries + validation
    """
    cfg = config or {}

    if cfg.get("query_strategy") == "single_phase":
        return _build_all_queries_legacy(since_date, cfg)

    result = {}

    # Phase 1: Discovery queries
    result["phase1"] = build_discovery_queries(since_date, cfg)

    # Already-targeted queries (no phase split needed)
    enabled = cfg.get("sources_enabled", ["teams"])
    if "calendar" in enabled:
        transcript_qs = build_transcript_queries(since_date, cfg)
        result["transcript_discovery"] = transcript_qs[0]
        result["transcript_extraction"] = transcript_qs[1]

    result["doc_mentions"] = build_doc_mentions_queries(since_date, cfg)

    # Phase 3: Validation query
    result["validation"] = build_validation_query(since_date, cfg)

    return result


# ---------------------------------------------------------------------------
# Phase 2: Dedup
# ---------------------------------------------------------------------------


def normalize_text(text):
    """Lowercase and strip whitespace."""
    return text.strip().lower()


def normalize_title_words(title):
    """Lowercase, remove stop words, sort remaining words."""
    words = normalize_text(title).split()
    filtered = sorted(w for w in words if w not in STOP_WORDS)
    return " ".join(filtered)


def compute_dedup_hash(sender, title, extracted_date):
    """SHA-256 hash of sender|normalized_title|date, truncated to 16 chars."""
    norm_sender = normalize_text(sender)
    norm_title = normalize_title_words(title)
    norm_date = normalize_text(extracted_date)
    payload = f"{norm_sender}|{norm_title}|{norm_date}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def jaccard_similarity(set_a, set_b):
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def fuzzy_match(new_title, existing_tasks, threshold=0.7):
    """Check if new_title fuzzy-matches any existing task title.

    Returns the matched task dict or None.
    """
    new_words = set(normalize_title_words(new_title).split())
    for task in existing_tasks:
        existing_words = set(normalize_title_words(task["title"]).split())
        if jaccard_similarity(new_words, existing_words) >= threshold:
            return task
    return None


def is_duplicate(new_hash, existing_tasks):
    """Check if a hash already exists in the task store."""
    return any(t.get("dedup_hash") == new_hash for t in existing_tasks)


# ---------------------------------------------------------------------------
# Cross-Source Matching
# ---------------------------------------------------------------------------


def find_cross_source_match(new_task_dict, existing_tasks, threshold=0.5):
    """Find a matching task across sources using sender + fuzzy title.

    Matches an incoming task dict (must have "sender" and "title") against
    ALL existing tasks from any source, including closed and likely_done.
    This prevents re-creating tasks that were already closed.

    Returns the matched task dict or None.
    """
    new_sender = normalize_text(new_task_dict.get("sender", ""))
    new_title = new_task_dict.get("title", "")
    if not new_sender or not new_title:
        return None

    candidates = [
        t for t in existing_tasks
        if normalize_text(t.get("sender", "")) == new_sender
    ]
    if not candidates:
        return None

    return fuzzy_match(new_title, candidates, threshold=threshold)


def merge_cross_source_signal(existing_task, new_source, new_link):
    """Merge a cross-source signal into an existing task.

    Bumps times_seen and stores the alternate link in source_metadata.
    Does not add duplicate links.
    """
    existing_task["times_seen"] = existing_task.get("times_seen", 1) + 1
    existing_task["updated"] = datetime.now().isoformat()

    meta = existing_task.setdefault("source_metadata", {})
    alt_links = meta.setdefault("alternate_links", [])

    link_entry = {"source": new_source, "link": new_link}
    # Avoid duplicates
    if not any(a.get("link") == new_link for a in alt_links):
        alt_links.append(link_entry)


def merge_duplicates(tasks):
    """Merge duplicate non-closed tasks sharing thread_id or meeting_title.

    Within each group, pairwise Jaccard similarity on title words is checked.
    If >= 0.7: keep newest-created task, close older ones with merge reason.

    Returns list of (kept_id, [merged_ids]).
    """
    from collections import defaultdict

    non_closed = [t for t in tasks if t.get("state") != "closed"]
    id_map = {t["id"]: t for t in tasks}

    # Build groups
    groups = defaultdict(list)
    for t in non_closed:
        thread = t.get("thread_id", "")
        meeting = t.get("source_metadata", {}).get("meeting_title", "")
        sender = normalize_text(t.get("sender", ""))
        if thread:
            groups[f"thread:{thread}"].append(t)
        if meeting:
            groups[f"meeting:{meeting}"].append(t)
        if sender:
            groups[f"sender:{sender}"].append(t)

    merged_results = []
    already_merged = set()

    for _key, group in groups.items():
        if len(group) < 2:
            continue

        # Sort by created desc — newest first
        group.sort(key=lambda x: x.get("created", ""), reverse=True)

        for i in range(len(group)):
            if group[i]["id"] in already_merged:
                continue
            merged_ids = []
            words_i = set(normalize_title_words(group[i].get("title", "")).split())
            for j in range(i + 1, len(group)):
                if group[j]["id"] in already_merged:
                    continue
                words_j = set(normalize_title_words(group[j].get("title", "")).split())
                if jaccard_similarity(words_i, words_j) >= 0.7:
                    # Close the older task
                    older = group[j]
                    older["state"] = "closed"
                    older["state_history"] = older.get("state_history", [])
                    older["state_history"].append({
                        "state": "closed",
                        "reason": f"Merged into {group[i]['id']}",
                        "date": datetime.now().isoformat(),
                    })
                    older["updated"] = datetime.now().isoformat()
                    merged_ids.append(older["id"])
                    already_merged.add(older["id"])

            if merged_ids:
                keeper = group[i]
                desc = keeper.get("description", "") or ""
                merge_note = "Merged: " + ", ".join(merged_ids)
                if desc:
                    keeper["description"] = desc + " | " + merge_note
                else:
                    keeper["description"] = merge_note
                merged_results.append((keeper["id"], merged_ids))
                already_merged.add(keeper["id"])  # prevent re-processing

    return merged_results


# ---------------------------------------------------------------------------
# Teams Link Helpers
# ---------------------------------------------------------------------------


def extract_thread_id(teams_link):
    """Extract the thread/conversation ID from a Teams deep link.

    Handles both /l/message/ and ?context= URL patterns.
    Returns the thread ID string, or "" if unparseable.
    """
    if not teams_link:
        return ""
    try:
        parsed = urlparse(teams_link)
        # Try ?context= parameter first (contains chatOrChannel.id)
        qs = parse_qs(parsed.query)
        ctx = qs.get("context", [""])[0]
        if ctx:
            import json as _json
            ctx_obj = _json.loads(ctx)
            cid = ctx_obj.get("chatOrChannel", {}).get("id", "")
            if cid:
                return cid
        # Fallback: extract from the path segments
        # Typical pattern: /l/message/<thread_id>/<message_ts>
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "l" and parts[1] == "message":
            return parts[2]
    except Exception:
        pass
    return ""


def build_search_fallback(task):
    """Return a plain-text search hint for manually finding the thread.

    Example: Search "Compass Connect" in chat with Sri Varsha Nadella
    """
    sender = task.get("sender", "")
    title = task.get("title", "")
    # Pick a short keyword phrase from the title (first 3-4 meaningful words)
    words = [w for w in title.split() if w.lower() not in STOP_WORDS]
    keyword = " ".join(words[:3]) if words else title[:30]
    if sender:
        return f'Search "{keyword}" in chat with {sender}'
    return f'Search "{keyword}" in Teams'


# ---------------------------------------------------------------------------
# Subtask Grouping
# ---------------------------------------------------------------------------


def suggest_groups(tasks):
    """Group tasks by same sender + same thread_id.

    Returns a list of dicts: [{"parent_id": ..., "child_ids": [...]}, ...]
    Picks the broadest-scope task (longest description) as parent.
    Only groups when there are 2+ tasks sharing sender+thread.
    """
    from collections import defaultdict
    buckets = defaultdict(list)
    for t in tasks:
        thread = t.get("thread_id", "")
        if not thread:
            continue
        sender = normalize_text(t.get("sender", ""))
        if not sender:
            continue
        key = f"{sender}|{thread}"
        buckets[key].append(t)

    groups = []
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        # Pick parent: longest description
        group_sorted = sorted(group, key=lambda t: len(t.get("description", "")), reverse=True)
        parent = group_sorted[0]
        children = [t for t in group_sorted[1:] if t["id"] != parent["id"]]
        groups.append({
            "parent_id": parent["id"],
            "child_ids": [c["id"] for c in children],
        })
    return groups


def group_tasks(parent_id, child_ids, store=None):
    """Set parent/child relationships in the store. Saves to disk."""
    if store is None:
        store = load_tasks()
    task_map = {t["id"]: t for t in store["tasks"]}
    parent = task_map.get(parent_id)
    if not parent:
        return False
    existing = set(parent.get("subtask_ids", []))
    for cid in child_ids:
        child = task_map.get(cid)
        if child and cid != parent_id:
            child["parent_id"] = parent_id
            existing.add(cid)
    parent["subtask_ids"] = sorted(existing)
    save_tasks(store)
    return True


def ungroup_task(task_id, store=None):
    """Remove a task from its parent. Saves to disk."""
    if store is None:
        store = load_tasks()
    task_map = {t["id"]: t for t in store["tasks"]}
    task = task_map.get(task_id)
    if not task:
        return False
    parent_id = task.get("parent_id")
    if not parent_id:
        return False
    task["parent_id"] = None
    parent = task_map.get(parent_id)
    if parent:
        subs = parent.get("subtask_ids", [])
        parent["subtask_ids"] = [s for s in subs if s != task_id]
    save_tasks(store)
    return True


# ---------------------------------------------------------------------------
# Phase 2: Task Store CRUD
# ---------------------------------------------------------------------------


def next_task_id(config):
    """Generate next TASK-NNN id and increment counter."""
    num = config.get("next_task_id", 1)
    task_id = f"TASK-{num:03d}"
    config["next_task_id"] = num + 1
    return task_id


def add_task(task_dict, config):
    """Add a new task to the store. Returns the assigned task ID."""
    store = load_tasks()
    task_id = next_task_id(config)
    task_dict["id"] = task_id
    task_dict.setdefault("state", "open")
    # Outbound tasks start in "waiting" — user is waiting on someone else
    if task_dict.get("direction") == "outbound" and task_dict.get("state") == "open":
        task_dict["state"] = "waiting"
    task_dict.setdefault("score", 0)
    task_dict.setdefault("score_breakdown", {})
    source = task_dict.get("source", "teams")
    source_labels = {"teams": "Teams", "email": "email", "calendar": "calendar", "doc_mentions": "Document Mention", "all_received": "Teams message", "key_contacts": "key contact message"}
    initial_state = task_dict.get("state", "open")
    reason = f"Extracted from {source_labels.get(source, source)}"
    task_dict.setdefault("state_history", [
        {"state": initial_state, "reason": reason, "date": datetime.now().isoformat()}
    ])
    task_dict.setdefault("times_seen", 1)
    task_dict.setdefault("created", datetime.now().isoformat())
    task_dict.setdefault("updated", datetime.now().isoformat())
    # Source fields
    task_dict.setdefault("source", "teams")
    task_dict.setdefault("source_link", "")
    task_dict.setdefault("source_metadata", {})
    # Direction: "inbound" = someone asked me, "outbound" = I asked someone
    task_dict.setdefault("direction", "inbound")
    # Grouping fields
    task_dict.setdefault("parent_id", None)
    task_dict.setdefault("subtask_ids", [])
    task_dict.setdefault("thread_id", extract_thread_id(task_dict.get("teams_link", "")))
    store["tasks"].append(task_dict)
    save_tasks(store)
    save_config(config)
    return task_id


def get_task(task_id):
    """Return a single task by ID, or None."""
    store = load_tasks()
    for t in store["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def list_tasks(states=None):
    """Return tasks, optionally filtered by state(s)."""
    store = load_tasks()
    tasks = store["tasks"]
    if states:
        tasks = [t for t in tasks if t.get("state") in states]
    return tasks


def update_task(task_id, updates):
    """Partial update of a task. Returns updated task or None."""
    store = load_tasks()
    for t in store["tasks"]:
        if t["id"] == task_id:
            t.update(updates)
            t["updated"] = datetime.now().isoformat()
            save_tasks(store)
            return t
    return None


# ---------------------------------------------------------------------------
# Phase 3: State Machine
# ---------------------------------------------------------------------------

VALID_STATES = {"open", "waiting", "needs_followup", "likely_done", "closed"}

VALID_TRANSITIONS = {
    "open": {"waiting", "needs_followup", "likely_done", "closed"},
    "waiting": {"open", "needs_followup", "likely_done", "closed"},
    "needs_followup": {"open", "waiting", "likely_done", "closed"},
    "likely_done": {"open", "closed"},
    "closed": set(),  # terminal
}


def transition_task(task, new_state, reason, today=None):
    """Move task to new_state if valid. Mutates task in-place. Returns bool."""
    current = task.get("state", "open")
    if new_state not in VALID_TRANSITIONS.get(current, set()):
        return False
    today = today or datetime.now().isoformat()
    task["state"] = new_state
    task.setdefault("state_history", []).append({
        "state": new_state,
        "reason": reason,
        "date": today,
    })
    task["updated"] = today
    return True


def match_conversation_to_tasks(conversation, tasks, threshold=0.5):
    """Match a conversation theme to existing tasks.

    A conversation dict should have:
      - sender: str (who the conversation is with)
      - topic: str (conversation topic/summary)
      - thread_id: str (optional, Teams thread ID)

    Matching priority:
      1. Exact thread_id match (if both have one)
      2. Same sender + topic similarity (fuzzy title match)

    Returns the matched task or None.
    """
    conv_thread = conversation.get("thread_id", "")
    conv_sender = normalize_text(conversation.get("sender", ""))
    conv_topic = conversation.get("topic", "")

    # Pass 1: thread_id match (strongest signal)
    if conv_thread:
        for task in tasks:
            if task.get("thread_id") == conv_thread:
                return task

    # Pass 2: sender + topic similarity
    sender_matches = [
        t for t in tasks
        if normalize_text(t.get("sender", "")) == conv_sender
    ] if conv_sender else []

    if sender_matches and conv_topic:
        match = fuzzy_match(conv_topic, sender_matches, threshold=threshold)
        if match:
            return match

    return None


def evaluate_transitions(tasks, followup_signals=None, today=None,
                         conversation_signals=None, config=None):
    """Evaluate state transitions for a list of tasks.

    Supports two signal formats:

    1. followup_signals (legacy): dict mapping task_id ->
       {"has_update": bool, "signal": str, "signal_type": str}

    2. conversation_signals (new, conversation-first): list of dicts, each:
       {"sender": str, "topic": str, "thread_id": str,
        "signal_type": "completion"|"waiting"|"active",
        "signal": str, "teams_link": str}

    When conversation_signals is provided, each signal is matched to tasks
    by sender + thread_id + topic similarity, then merged into the
    per-task signal dict. Direct followup_signals take precedence.

    Returns list of (task_id, old_state, new_state, reason) transitions made.
    """
    today_dt = datetime.fromisoformat(today) if today else datetime.now()
    today_str = today or today_dt.isoformat()
    followup_signals = followup_signals or {}
    config = config or {}
    transitions = []
    task_map = {t["id"]: t for t in tasks}

    # Merge conversation_signals into per-task signals
    if conversation_signals:
        open_tasks = [t for t in tasks if t.get("state") != "closed"]
        for conv in conversation_signals:
            matched_task = match_conversation_to_tasks(conv, open_tasks)
            if matched_task:
                task_id = matched_task["id"]
                # Don't overwrite explicit followup_signals
                if task_id not in followup_signals:
                    followup_signals[task_id] = {
                        "has_update": True,
                        "signal_type": conv.get("signal_type", "active"),
                        "signal": conv.get("signal", "Conversation activity detected"),
                    }
                # Update teams_link if conversation provides a better one
                conv_link = conv.get("teams_link", "")
                if conv_link and "context=" in conv_link:
                    matched_task["teams_link"] = conv_link
                    matched_task["thread_id"] = extract_thread_id(conv_link)

    for task in tasks:
        if task["state"] == "closed":
            continue

        task_id = task["id"]
        old_state = task["state"]
        created = datetime.fromisoformat(task.get("created", today_str))
        age_days = (today_dt - created).days
        signal = followup_signals.get(task_id, {})

        # Likely Done → Closed: 3+ days with no contradicting signal
        if task["state"] == "likely_done":
            last_transition = task.get("state_history", [])[-1] if task.get("state_history") else None
            if last_transition:
                ld_date = datetime.fromisoformat(last_transition["date"])
                if (today_dt - ld_date).days >= 3 and not signal.get("has_update"):
                    transition_task(task, "closed", "Auto-closed: no contradicting signal after likely_done", today_str)
                    transitions.append((task_id, old_state, "closed", "Auto-closed after likely_done timeout"))
            continue

        # Check for completion signals in followup
        if signal.get("signal_type") == "completion":
            transition_task(task, "likely_done", f"Completion signal: {signal.get('signal', '')}", today_str)
            transitions.append((task_id, old_state, "likely_done", f"Completion signal detected"))
            continue

        # Check for waiting signals
        if signal.get("signal_type") == "waiting":
            if task["state"] != "waiting":
                transition_task(task, "waiting", f"Waiting signal: {signal.get('signal', '')}", today_str)
                transitions.append((task_id, old_state, "waiting", "Waiting signal detected"))
            continue

        # "active" signal from conversation means the thread is alive — reset to open
        if signal.get("signal_type") == "active" and task["state"] in ("needs_followup",):
            transition_task(task, "open", f"Activity detected: {signal.get('signal', '')}", today_str)
            transitions.append((task_id, old_state, "open", "Activity detected in conversation"))
            continue

        # Needs Follow-up → Closed: 7+ days in needs_followup with no re-mention
        if task["state"] == "needs_followup" and not signal.get("has_update"):
            nf_entry = None
            for sh in reversed(task.get("state_history", [])):
                if sh.get("state") == "needs_followup":
                    nf_entry = sh
                    break
            days_in_nf = (today_dt - datetime.fromisoformat(nf_entry["date"])).days if nf_entry else age_days
            auto_close_stale = config.get("auto_close_stale_days", 7)
            if days_in_nf >= auto_close_stale:
                transition_task(task, "closed", f"Auto-closed: in needs_followup for {days_in_nf}d", today_str)
                transitions.append((task_id, old_state, "closed", "Stale auto-close"))
                continue

        # Open → Closed: 10+ days with zero signals
        auto_close_open = config.get("auto_close_open_days", 10)
        if task["state"] == "open" and age_days >= auto_close_open and not signal.get("has_update"):
            transition_task(task, "closed", f"Auto-closed: open {age_days}d with no signals", today_str)
            transitions.append((task_id, old_state, "closed", f"Stale open auto-close after {age_days}d"))
            continue

        # Open → Needs Follow-up: age > 3 days, no recent mention
        if task["state"] == "open" and age_days > 3 and not signal.get("has_update"):
            transition_task(task, "needs_followup", f"No update after {age_days} days", today_str)
            transitions.append((task_id, old_state, "needs_followup", f"No update after {age_days}d"))
            continue

    # Auto-close open subtasks when their parent closes
    newly_closed = {tid for (tid, _, ns, _) in transitions if ns == "closed"}
    for parent_id in newly_closed:
        parent = task_map.get(parent_id)
        if not parent:
            continue
        for child_id in parent.get("subtask_ids", []):
            child = task_map.get(child_id)
            if child and child["state"] != "closed":
                child_old = child["state"]
                transition_task(child, "closed", "Parent task closed.", today_str)
                transitions.append((child_id, child_old, "closed", "Parent task closed."))

    return transitions


# ---------------------------------------------------------------------------
# Phase 3: Priority Scoring
# ---------------------------------------------------------------------------


def score_task(task, config, analytics=None):
    """Score a task 0–100 with breakdown. Mutates task in-place.

    When analytics is provided, three additional components are added:
    response_time (0-10), escalation (0-15), and pin (0-20).
    All return 0 when analytics is None for backward compatibility.
    """
    breakdown = {}

    # Stakeholder weight (0–40)
    sender_key = normalize_text(task.get("sender", ""))
    stakeholder = config.get("stakeholders", {}).get(sender_key, {})
    weight = stakeholder.get("weight", 2)  # default unknown = 2
    stakeholder_score = min(weight * 4, 40)
    breakdown["stakeholder"] = stakeholder_score

    # Urgency signal (0–30)
    urgency_keywords = config.get("urgency_keywords", [])
    text_to_scan = f"{task.get('title', '')} {task.get('description', '')} {task.get('due_hint', '')}".lower()
    urgency_hits = sum(1 for kw in urgency_keywords if kw.lower() in text_to_scan)
    urgency_score = min(urgency_hits * 10, 30)
    breakdown["urgency"] = urgency_score

    # Age penalty (0–20)
    created = datetime.fromisoformat(task.get("created", datetime.now().isoformat()))
    age_days = (datetime.now() - created).days
    if age_days <= 1:
        age_score = 0
    elif age_days <= 3:
        age_score = 5
    elif age_days <= 7:
        age_score = 10
    elif age_days <= 14:
        age_score = 15
    else:
        age_score = 20
    breakdown["age"] = age_score

    # Thread intensity (0–10)
    times_seen = task.get("times_seen", 1)
    thread_score = min(times_seen * 2, 10)
    breakdown["thread"] = thread_score

    # Subtask boost (0–15): parents with children score higher
    subtask_count = len(task.get("subtask_ids", []))
    subtask_boost = min(subtask_count * 5, 15)
    breakdown["subtask_boost"] = subtask_boost

    # Calendar boost (0–5): formal meeting action items get a bump
    cal_boost_val = config.get("scoring", {}).get("calendar_boost", 5)
    calendar_boost = cal_boost_val if task.get("source") == "calendar" else 0
    breakdown["calendar_boost"] = calendar_boost

    # Multi-source corroboration (0–5): task seen across multiple sources
    alt_links = task.get("source_metadata", {}).get("alternate_links", [])
    multi_source = 5 if alt_links else 0
    breakdown["multi_source"] = multi_source

    # Analytics-based components (all return 0 when analytics is None)
    response_time = get_response_time_factor(task.get("sender", ""), analytics)
    breakdown["response_time"] = response_time

    escalation = get_escalation_bonus(task.get("id", ""), analytics)
    breakdown["escalation"] = escalation

    pin = get_pin_bonus(task.get("id", ""), analytics)
    breakdown["pin"] = pin

    # Manual/inbox task boost — ensures manually added tasks surface in Focus Now
    if task.get("source") == "manual":
        manual_boost = config.get("scoring", {}).get("manual_boost", 15)
    else:
        manual_boost = 0
    breakdown["manual_boost"] = manual_boost

    total = (stakeholder_score + urgency_score + age_score + thread_score
             + subtask_boost + calendar_boost + multi_source
             + response_time + escalation + pin + manual_boost)
    task["score"] = min(total, 100)
    task["score_breakdown"] = breakdown
    return task["score"]


def score_all_tasks(config, analytics=None):
    """Rescore all active (non-closed) tasks. Saves store.

    Loads analytics once if not provided.
    """
    if analytics is None:
        analytics = load_analytics()
    store = load_tasks()
    for task in store["tasks"]:
        if task.get("state") != "closed":
            score_task(task, config, analytics)
    save_tasks(store)


# ---------------------------------------------------------------------------
# Phase 4: Dashboard Rendering
# ---------------------------------------------------------------------------


def _format_age(created_str):
    """Return a human-readable age string like '2d ago' or '3h ago'."""
    created = datetime.fromisoformat(created_str)
    delta = datetime.now() - created
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours}h ago"
    if days == 1:
        return "1d ago"
    return f"{days}d ago"


# ---------------------------------------------------------------------------
# V2 Helpers — leaf functions for dashboard v2 rendering
# ---------------------------------------------------------------------------

TASK_TYPES = {
    "followup_nudge": {
        "emoji": "\U0001f514",
        "label": "Follow-up / Nudge",
        "keywords": ["follow up", "followup", "nudge", "ping", "remind", "check in", "chase"],
    },
    "schedule_book": {
        "emoji": "\U0001f4c5",
        "label": "Schedule / Book",
        "keywords": ["schedule", "book", "invite", "meeting", "calendar", "set up", "arrange"],
    },
    "draft_create": {
        "emoji": "\u270f\ufe0f",
        "label": "Draft / Create",
        "keywords": ["draft", "create", "write", "prepare", "document", "build", "design"],
    },
    "review_decide": {
        "emoji": "\U0001f50d",
        "label": "Review / Decide",
        "keywords": ["review", "decide", "approve", "evaluate", "assess", "feedback", "sign off"],
    },
    "reply_align": {
        "emoji": "\u2709\ufe0f",
        "label": "Reply / Align",
        "keywords": ["reply", "respond", "align", "update", "status", "confirm", "acknowledge"],
    },
}


def _compute_idle_days(task):
    """Days since last update (falls back to created)."""
    ts = task.get("updated") or task.get("created")
    if not ts:
        return 0
    dt = datetime.fromisoformat(ts)
    return (datetime.now() - dt).days


def parse_due_hint(due_hint, reference_date=None):
    """Parse a due_hint keyword into a datetime. Returns None for unrecognised values.

    Supported:
        eod / eod today / today / urgent / asap  -> today 17:00
        tomorrow                                  -> tomorrow 17:00
        eow / end of week                         -> Friday 17:00
        eod {weekday}                             -> next occurrence of that weekday 17:00
        next week                                 -> next Monday 09:00
        ISO date string                           -> datetime.fromisoformat()
    """
    if not due_hint:
        return None
    ref = reference_date or datetime.now()
    hint = due_hint.strip().lower()

    # Today variants
    if hint in ("eod", "eod today", "today", "urgent", "asap"):
        return ref.replace(hour=17, minute=0, second=0, microsecond=0)

    if hint == "tomorrow":
        return (ref + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)

    if hint in ("eow", "end of week"):
        # Friday = 4
        days_ahead = (4 - ref.weekday()) % 7
        if days_ahead == 0 and ref.hour >= 17:
            days_ahead = 7
        return (ref + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)

    if hint == "next week":
        # Next Monday
        days_ahead = (7 - ref.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (ref + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)

    # eod {weekday}
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    m = re.match(r"^eod\s+(\w+)$", hint)
    if m:
        day_name = m.group(1)
        target = weekdays.get(day_name)
        if target is not None:
            days_ahead = (target - ref.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (ref + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)

    # ISO date
    try:
        return datetime.fromisoformat(due_hint.strip())
    except (ValueError, TypeError):
        pass

    return None


def _is_due_within(task, hours=48):
    """True if the task's due_hint resolves to within `hours` from now."""
    dt = parse_due_hint(task.get("due_hint", ""))
    if dt is None:
        return False
    return dt <= datetime.now() + timedelta(hours=hours)


def _compute_confidence(task):
    """Heuristic confidence score 0.0–1.0, computed at render time."""
    conf = 0.0
    if task.get("description"):
        conf += 0.2
    if task.get("due_hint"):
        conf += 0.1
    if task.get("teams_link") or task.get("source_link"):
        conf += 0.2
    if task.get("thread_id"):
        conf += 0.1
    if task.get("times_seen", 1) > 1:
        conf += 0.1
    if task.get("next_step"):
        conf += 0.1
    if task.get("source") in ("calendar", "transcript"):
        conf += 0.1
    if task.get("sender"):
        conf += 0.1
    return min(conf, 1.0)


def classify_task_type(task):
    """Classify a task into one of TASK_TYPES based on keyword scan."""
    text = " ".join([
        task.get("title", ""),
        task.get("description", ""),
        task.get("next_step", ""),
    ]).lower()
    for type_key, info in TASK_TYPES.items():
        for kw in info["keywords"]:
            if kw in text:
                return type_key
    return "reply_align"


def _generate_next_action(task):
    """Return a short next-action string for a task.

    If next_step exists, truncate to first 12 words (verb-first).
    Otherwise, infer from task type.
    """
    ns = task.get("next_step", "").strip()
    if ns:
        words = ns.split()
        return " ".join(words[:12])

    tt = classify_task_type(task)
    sender = task.get("sender", "them")
    defaults = {
        "reply_align": "Reply with status and ETA",
        "draft_create": "Draft document and share link",
        "schedule_book": "Send meeting invite",
        "review_decide": "Review and provide decision",
        "followup_nudge": f"Ping {sender} with reminder",
    }
    return defaults.get(tt, "Reply with status and ETA")


def _shorten_meeting_title(title, max_words=5):
    """Shorten a meeting title to its most meaningful words."""
    filler = {"and", "the", "for", "with", "sync", "meeting", "discussion",
              "review", "weekly", "daily", "bi-weekly", "recurring", "session",
              "call", "touchpoint", "catchup", "catch-up", "check-in"}
    words = title.split()
    # If already short, keep as-is
    if len(words) <= max_words:
        return title
    meaningful = [w for w in words if w.lower().strip("()-,") not in filler]
    if not meaningful:
        meaningful = words
    return " ".join(meaningful[:max_words])


def _extract_container_key(task):
    """Return (key, title, source_type, source_link) for grouping.

    Priority: source_metadata.meeting_title > thread_id > sender + title words.
    """
    meta = task.get("source_metadata", {})
    meeting = meta.get("meeting_title", "")
    if meeting:
        short = _shorten_meeting_title(meeting)
        return (f"meeting:{meeting}", short, "meeting", task.get("source_link", ""))

    thread = task.get("thread_id", "")
    if thread:
        # Use sender + short title summary instead of opaque thread ID
        sender = task.get("sender", "Unknown")
        title_words = task.get("title", "").split()
        # Take up to 4 meaningful content words from the title
        summary = " ".join(title_words[:4]) if title_words else "thread"
        display = f"{sender} \u2014 {summary}"
        return (f"thread:{thread}", display, "chat", task.get("teams_link", ""))

    sender = task.get("sender", "Unknown")
    title_words = task.get("title", "").split()[:5]
    fallback_title = f"{sender} \u2014 {' '.join(title_words)}" if title_words else sender
    return (f"sender:{sender}:{' '.join(title_words)}", fallback_title, "direct", "")


def _compute_focus_priority(task):
    """Priority score for Focus sorting. Not persisted."""
    score = task.get("score", 0)
    due_48h = 25 if _is_due_within(task, 48) else 0
    due_7d = 15 if _is_due_within(task, 168) else 0
    idle = min(5 * _compute_idle_days(task), 20)
    conf_penalty = -10 if _compute_confidence(task) < 0.6 else 0
    return score + due_48h + due_7d + idle + conf_penalty


def _build_links_line(task, prefix):
    """Build a single links line combining all available links."""
    parts = []
    source = task.get("source", "")
    source_link = task.get("source_link", "")
    teams_link = task.get("teams_link", "")

    link_labels = {
        "email": "Open in Outlook",
        "calendar": "Open Meeting",
    }

    if source in link_labels and source_link:
        parts.append(f"[{link_labels[source]}]({source_link})")

    if teams_link:
        parts.append(f"[Open in Teams]({teams_link})")

    alt_links = task.get("source_metadata", {}).get("alternate_links", [])
    for alt in alt_links:
        alt_label = link_labels.get(alt.get("source", ""), "Open Link")
        alt_url = alt.get("link", "")
        if alt_url:
            parts.append(f"[{alt_label}]({alt_url})")

    fallback = build_search_fallback(task)
    if fallback:
        parts.append(fallback)

    if parts:
        return f"{prefix}  \U0001f517 {' \u00b7 '.join(parts)}"
    return ""


def _render_task_item_v1(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Render a single task as a markdown item with emoji metadata (v1 layout).

    Args:
        task: The task dict.
        indent: Number of indent levels (0 = top-level, 1 = subtask).
        all_tasks: Dict of id->task for resolving subtasks.
        section: Section context ('focus', 'open', etc.) for conditional rendering.
        analytics: Analytics dict for pin detection.
    """
    prefix = "  " * indent
    title = task.get("title", "Untitled")
    score = task.get("score", 0)
    description = task.get("description", "")
    next_step = task.get("next_step", "")
    sender = task.get("sender", "Unknown")
    created = task.get("created", datetime.now().isoformat())
    state = task.get("state", "open")
    task_id = task.get("id", "")
    direction = task.get("direction", "inbound")
    due_hint = task.get("due_hint", "")

    # Closed tasks: compact single line with strikethrough
    if state == "closed":
        age = _format_age(task.get("updated", created))
        return f"{prefix}- [x] ~~{task_id} | {title}~~ \u00b7 closed {age}"

    # Outbound tasks: checkbox so users can close from Obsidian
    if direction == "outbound":
        lines = [f"{prefix}- [ ] **{task_id} | {title}** `Score: {score}`"]
        if due_hint:
            lines.append(f"{prefix}  \U0001f4c5 Due: {due_hint} \u00b7 \u23f1 {_format_age(created)}")
        else:
            lines.append(f"{prefix}  \u23f1 {_format_age(created)}")
        lines.append(f"{prefix}  \u2192 **{sender}** owes this")
        links_line = _build_links_line(task, prefix)
        if links_line:
            lines.append(links_line)
        return "\n".join(lines)

    # Inbound active tasks: checkbox + full detail
    lines = [f"{prefix}- [ ] **{task_id} | {title}** `Score: {score}`"]

    if due_hint:
        lines.append(f"{prefix}  \U0001f4c5 Due: {due_hint} \u00b7 \u23f1 Created: {_format_age(created)}")
    elif section == "focus":
        lines.append(f"{prefix}  \U0001f4c5 Due: \u2014 \u00b7 \u23f1 Created: {_format_age(created)}")
    else:
        lines.append(f"{prefix}  \u23f1 Created: {_format_age(created)}")

    pin_indicator = ""
    if analytics and task_id in analytics.get("user_pins", []):
        pin_indicator = " \u00b7 \U0001f4cc Pinned"
    lines.append(f"{prefix}  \U0001f464 {sender}{pin_indicator}")

    if description and next_step:
        lines.append(f"{prefix}  \U0001f4ac {description} \u00b7 Next: {next_step}")
    elif description:
        lines.append(f"{prefix}  \U0001f4ac {description}")
    elif next_step:
        lines.append(f"{prefix}  \U0001f4ac Next: {next_step}")

    links_line = _build_links_line(task, prefix)
    if links_line:
        lines.append(links_line)

    # Render subtasks nested under parent
    subtask_ids = task.get("subtask_ids", [])
    if subtask_ids and all_tasks:
        lines.append(f"{prefix}  - Subtasks:")
        for sid in subtask_ids:
            child = all_tasks.get(sid)
            if child:
                lines.append(_render_task_item_v1(child, indent=indent + 2, all_tasks=all_tasks,
                                                  section=section, analytics=analytics))

    return "\n".join(lines)


def _render_task_item_v2(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Render a single task as a multi-line block with score, priority, confidence (v2 layout)."""
    prefix = "  " * indent
    title = task.get("title", "Untitled")
    score = task.get("score", 0)
    sender = task.get("sender", "Unknown")
    created = task.get("created", datetime.now().isoformat())
    state = task.get("state", "open")
    task_id = task.get("id", "")
    direction = task.get("direction", "inbound")
    due_hint = task.get("due_hint", "")

    # Closed tasks: unchanged compact format
    if state == "closed":
        age = _format_age(task.get("updated", created))
        return f"{prefix}- [x] ~~{task_id} | {title}~~ \u00b7 closed {age}"

    # Compute v2 metrics
    priority = _compute_focus_priority(task)
    confidence = _compute_confidence(task)
    idle_days = _compute_idle_days(task)
    next_action = task.get("_next_action") or _generate_next_action(task)
    age = _format_age(created)

    lines = [f"{prefix}- [ ] {task_id} | {title}"]
    lines.append(f"{prefix}  Score: {score} \u00b7 Priority: {priority} \u00b7 Conf: {confidence:.1f}")
    lines.append(f"{prefix}  Due: {due_hint or '\u2014'} \u00b7 Age: {age} \u00b7 Idle: {idle_days}d")

    if direction == "outbound":
        lines.append(f"{prefix}  Assigned to: {sender}")
    else:
        lines.append(f"{prefix}  Asked by: {sender}")

    lines.append(f"{prefix}  Next: {next_action}")

    # Link line
    links_line = _build_links_line(task, prefix)
    if links_line:
        lines.append(links_line)

    # Render subtasks nested under parent
    subtask_ids = task.get("subtask_ids", [])
    if subtask_ids and all_tasks:
        lines.append(f"{prefix}  - Subtasks:")
        for sid in subtask_ids:
            child = all_tasks.get(sid)
            if child:
                lines.append(_render_task_item_v2(child, indent=indent + 2, all_tasks=all_tasks,
                                                  section=section, analytics=analytics))

    return "\n".join(lines)


def _render_task_item(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Dispatcher \u2014 calls v1 or v2 based on task's _dashboard_version flag."""
    version = task.get("_dashboard_version", 2)
    if version == 1:
        return _render_task_item_v1(task, indent, all_tasks, section, analytics)
    return _render_task_item_v2(task, indent, all_tasks, section, analytics)


_CHECKED_TASK_RE = re.compile(r"- \[x\] (?:\*\*|~~)?(TASK-\d+)")


def sync_dashboard_completions(vault_path, filename="TaskNemo.md"):
    """Read the Obsidian dashboard and close tasks the user checked off.

    Looks for lines matching '- [x] **TASK-NNN | ...**' where the task
    is NOT already closed in the store. Returns list of closed task IDs.
    """
    path = os.path.join(vault_path, filename)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    checked_ids = _CHECKED_TASK_RE.findall(content)
    if not checked_ids:
        return []

    store = load_tasks()
    closed_ids = []
    for task in store["tasks"]:
        if task["id"] in checked_ids and task.get("state") != "closed":
            transition_task(task, "closed", "Marked complete in Obsidian dashboard")
            closed_ids.append(task["id"])

    if closed_ids:
        save_tasks(store)

    return closed_ids


def render_dashboard_v1(tasks, config, run_stats=None, analytics=None):
    """Render the full dashboard as a markdown string."""
    now = datetime.now()
    run_stats = run_stats or {}
    if analytics is None:
        analytics = load_analytics()
    all_tasks = {t["id"]: t for t in tasks}

    # IDs that are subtasks — exclude from top-level sections
    subtask_ids = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids.add(sid)

    def is_root(t):
        return t["id"] not in subtask_ids

    # Categorize tasks (root only); separate inbound from outbound
    active = [t for t in tasks if t.get("state") != "closed" and is_root(t)]
    inbound_active = [t for t in active if t.get("direction", "inbound") == "inbound"]
    outbound_active = [t for t in active if t.get("direction") == "outbound"]
    active_sorted = sorted(inbound_active, key=lambda t: t.get("score", 0), reverse=True)
    outbound_sorted = sorted(outbound_active, key=lambda t: t.get("score", 0), reverse=True)

    focus = [t for t in active_sorted if t.get("score", 0) >= 70 and t.get("state") in ("open", "needs_followup")][:5]
    focus_ids = {t["id"] for t in focus}

    open_tasks = [t for t in active_sorted if t.get("state") == "open" and t["id"] not in focus_ids]
    waiting = [t for t in active_sorted if t.get("state") == "waiting"]
    needs_followup = [t for t in active_sorted if t.get("state") == "needs_followup" and t["id"] not in focus_ids]

    seven_days_ago = (now - timedelta(days=7)).isoformat()
    recently_closed = [
        t for t in tasks
        if t.get("state") == "closed" and t.get("updated", "") >= seven_days_ago and is_root(t)
    ]

    # Summary counts
    total_open = len(active)
    total_closed = len([t for t in tasks if t.get("state") == "closed" and is_root(t)])
    focus_count = len(focus)
    last_run = config.get("last_run")
    sync_age = _format_age(last_run) if last_run else "just now"

    # Build markdown
    lines = [
        "# TaskNemo",
        "",
        f"> Last synced {sync_age} | **{total_open}** open \u00b7 **{total_closed}** closed \u00b7 **{focus_count}** need attention",
        "",
    ]

    # Run stats
    if run_stats:
        new_count = run_stats.get("new_tasks", 0)
        transitions_count = run_stats.get("transitions", 0)
        lines.append(f"> Run: +{new_count} new, {transitions_count} transitions")
        lines.append("")

    def _render_section(callout_type, title, items, empty_msg, section_key=None):
        lines.append("---")
        lines.append("")
        lines.append(f"> [!{callout_type}] {title} ({len(items)})")
        lines.append(">")
        if items:
            for i, t in enumerate(items):
                rendered = _render_task_item_v1(
                    t, all_tasks=all_tasks, section=section_key, analytics=analytics
                )
                for line in rendered.split("\n"):
                    lines.append(f"> {line}")
                if i < len(items) - 1:
                    lines.append(">")
        else:
            lines.append(f"> *{empty_msg}*")
        lines.append("")

    _render_section("warning", "Focus Now", focus,
                    "No high-priority tasks right now.", "focus")
    _render_section("todo", "Open", open_tasks,
                    "No other open tasks.", "open")
    _render_section("example", "Waiting", waiting,
                    "Nothing waiting on others.", "waiting")
    _render_section("question", "Stale \u2014 Close or Chase", needs_followup,
                    "Nothing stale \u2014 you're on top of it.", "needs_followup")
    _render_section("info", "Following Up", outbound_sorted,
                    "No pending requests to others.", "outbound")
    _render_section("success", "Recently Closed", recently_closed,
                    "No recently closed tasks.", "closed")

    return "\n".join(lines)


def render_dashboard_v2(tasks, config, run_stats=None, analytics=None):
    """Render the full dashboard as markdown (v2 layout with grouped sections)."""
    from collections import OrderedDict

    now = datetime.now()
    run_stats = run_stats or {}
    if analytics is None:
        analytics = load_analytics()
    all_tasks_map = {t["id"]: t for t in tasks}

    # IDs that are subtasks
    subtask_ids_set = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids_set.add(sid)

    def is_root(t):
        return t["id"] not in subtask_ids_set

    # Pre-render: merge duplicates on non-closed tasks
    merge_duplicates(tasks)

    # Pre-render: generate next actions
    for t in tasks:
        if t.get("state") != "closed":
            t["_next_action"] = _generate_next_action(t)

    # Categorize
    active = [t for t in tasks if t.get("state") != "closed" and is_root(t)]
    inbound_active = [t for t in active if t.get("direction", "inbound") == "inbound"]
    outbound_active = [t for t in active if t.get("direction") == "outbound"]

    # Section 1: Focus Now — top 5 inbound by focus priority, min 3 if any exist
    focus_sorted = sorted(inbound_active, key=lambda t: _compute_focus_priority(t), reverse=True)
    focus_candidates = [t for t in focus_sorted if t.get("state") in ("open", "needs_followup")]
    if len(focus_candidates) >= 5:
        focus = focus_candidates[:5]
    elif len(focus_candidates) >= 3:
        focus = focus_candidates[:5]
    elif focus_candidates:
        # Force minimum 3 — pad from remaining inbound if needed
        focus = focus_candidates[:]
        remaining = [t for t in focus_sorted if t not in focus and t.get("state") in ("open", "needs_followup", "waiting")]
        for t in remaining:
            if len(focus) >= 3:
                break
            focus.append(t)
    else:
        focus = []
    focus_ids = {t["id"] for t in focus}

    # Section 2: Due Soon — inbound due<48h, excluding focus
    due_soon = [
        t for t in inbound_active
        if _is_due_within(t, 48) and t["id"] not in focus_ids
    ]
    due_soon.sort(key=lambda t: parse_due_hint(t.get("due_hint", "")) or datetime.max)
    due_soon_ids = {t["id"] for t in due_soon}

    # Section 3: Open (Grouped) — inbound, open, not in focus or due_soon
    open_grouped = [
        t for t in inbound_active
        if t.get("state") == "open" and t["id"] not in focus_ids and t["id"] not in due_soon_ids
    ]

    # Section 4: Needs Follow-up — inbound waiting/needs_followup, not placed above
    placed_inbound = focus_ids | due_soon_ids | {t["id"] for t in open_grouped}
    needs_followup = [
        t for t in inbound_active
        if t.get("state") in ("waiting", "needs_followup") and t["id"] not in placed_inbound
    ]

    # Section 5: Nudge Due — outbound idle>=3 or due<48h
    nudge_due = [t for t in outbound_active if _compute_idle_days(t) >= 3 or _is_due_within(t, 48)]
    nudge_due_ids = {t["id"] for t in nudge_due}

    # Section 6: Waiting — outbound not in nudge
    waiting_outbound = [t for t in outbound_active if t["id"] not in nudge_due_ids]

    # Section 7: Recently Closed
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    recently_closed = [
        t for t in tasks
        if t.get("state") == "closed" and t.get("updated", "") >= seven_days_ago and is_root(t)
    ]

    # Summary counts
    focus_count = len(focus)
    stale_count = len([t for t in active if _compute_idle_days(t) >= 3])
    last_run = config.get("last_run")
    if last_run:
        try:
            ts_dt = datetime.fromisoformat(last_run)
            timestamp = ts_dt.strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            timestamp = "unknown"
    else:
        timestamp = "just now"

    # Build markdown
    lines = [
        "# TaskNemo",
        "",
        f"> Last synced: {timestamp} | Focus: {focus_count} \u00b7 Due soon: {len(due_soon)} \u00b7 Nudge: {len(nudge_due)} \u00b7 Stale (idle \u22653d): {stale_count}",
        "",
    ]

    # Run stats
    if run_stats:
        new_count = run_stats.get("new_tasks", 0)
        transitions_count = run_stats.get("transitions", 0)
        lines.append(f"> Run: +{new_count} new, {transitions_count} transitions")
        lines.append("")

    # Task Inbox section — embedded at top of dashboard
    lines.append("## Task Inbox")
    lines.append("Add tasks below \u2014 they'll be imported on next sync or refresh.")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("---")
    lines.append("")

    def _render_section_v2(callout_type, title, items, empty_msg, section_key=None):
        lines.append("---")
        lines.append("")
        lines.append(f"> [!{callout_type}] {title} ({len(items)})")
        lines.append(">")
        if items:
            for i, t in enumerate(items):
                rendered = _render_task_item_v2(
                    t, all_tasks=all_tasks_map, section=section_key, analytics=analytics
                )
                for line in rendered.split("\n"):
                    lines.append(f"> {line}")
                if i < len(items) - 1:
                    lines.append(">")
        else:
            lines.append(f"> *{empty_msg}*")
        lines.append("")

    def _render_grouped_open_section():
        lines.append("---")
        lines.append("")
        lines.append(f"> [!todo] \U0001f4cb Open ({len(open_grouped)})")
        lines.append(">")
        if not open_grouped:
            lines.append("> *No other open tasks.*")
            lines.append("")
            return

        # Group tasks by container
        containers = OrderedDict()
        for t in open_grouped:
            key, c_title, src_type, src_link = _extract_container_key(t)
            if key not in containers:
                containers[key] = {"title": c_title, "source_type": src_type, "source_link": src_link, "tasks": []}
            containers[key]["tasks"].append(t)

        # Separate real groups (2+) from solo tasks
        grouped = [(k, c) for k, c in containers.items() if len(c["tasks"]) >= 2]
        solo_tasks = [t for _k, c in containers.items() if len(c["tasks"]) == 1 for t in c["tasks"]]

        # Render real groups with container headers
        for _ckey, cdata in grouped:
            c_title = cdata["title"]
            c_tasks = cdata["tasks"]
            c_type = cdata["source_type"]
            c_link = cdata["source_link"]
            lines.append(f"> ### {c_title} \u00b7 {len(c_tasks)} open  ({c_type})")
            if c_link:
                lines.append(f"> \U0001f517 {c_link}")

            # Sub-group by task type
            by_type = OrderedDict()
            for t in c_tasks:
                tt = classify_task_type(t)
                by_type.setdefault(tt, []).append(t)

            shown = 0
            for _tt, tt_tasks in by_type.items():
                for t in tt_tasks:
                    if shown >= 10:
                        break
                    rendered = _render_task_item_v2(
                        t, all_tasks=all_tasks_map, section="open", analytics=analytics
                    )
                    for line in rendered.split("\n"):
                        lines.append(f"> {line}")
                    lines.append(">")
                    shown += 1
                if shown >= 10:
                    break

            overflow = len(c_tasks) - min(shown, len(c_tasks))
            if overflow > 0:
                lines.append(f"> *+ {overflow} more*")
            lines.append(">")

        # Render solo tasks flat (no container header)
        for t in solo_tasks:
            rendered = _render_task_item_v2(
                t, all_tasks=all_tasks_map, section="open", analytics=analytics
            )
            for line in rendered.split("\n"):
                lines.append(f"> {line}")
            lines.append(">")

        lines.append("")

    # My Actions
    lines.append("## My Actions")
    lines.append("")
    _render_section_v2("warning", "\U0001f525 Focus Now", focus,
                       "No high-priority tasks right now.", "focus")
    _render_section_v2("danger", "\u23f0 Due Soon", due_soon,
                       "Nothing due soon.", "due_soon")
    _render_grouped_open_section()
    _render_section_v2("example", "\U0001f50d Stale \u2014 Close or Chase", needs_followup,
                       "Nothing stale \u2014 you're on top of it.", "needs_followup")

    # Following Up
    lines.append("## Following Up")
    lines.append("")
    _render_section_v2("question", "\U0001f4e3 Nudge Needed", nudge_due,
                       "No nudges needed.", "nudge_due")
    _render_section_v2("example", "\u23f3 Waiting for Reply", waiting_outbound,
                       "Nothing waiting.", "waiting")
    _render_section_v2("success", "\u2705 Recently Closed", recently_closed,
                       "No recently closed tasks.", "closed")

    return "\n".join(lines)


def render_dashboard(tasks, config, run_stats=None, analytics=None):
    """Dispatcher \u2014 calls v1 or v2 based on config dashboard_version."""
    version = config.get("dashboard_version", 2)
    if version == 1:
        return render_dashboard_v1(tasks, config, run_stats, analytics)
    return render_dashboard_v2(tasks, config, run_stats, analytics)


def write_dashboard(markdown, vault_path, filename="TaskNemo.md"):
    """Write the dashboard markdown to the Obsidian vault."""
    os.makedirs(vault_path, exist_ok=True)
    path = os.path.join(vault_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return path


# ---------------------------------------------------------------------------
# Alerts / Notifications
# ---------------------------------------------------------------------------


def _notify(title, message):
    """Show a desktop toast notification. Silently no-ops on failure."""
    try:
        from win11toast import notify
        notify(title, message)
    except Exception:
        pass


def _build_change_summary(new_count=0, closed_count=0, transition_count=0):
    """Return a human-readable change summary string, or None if nothing changed."""
    if new_count == 0 and closed_count == 0 and transition_count == 0:
        return None
    parts = []
    if new_count:
        parts.append(f"+{new_count} new {'task' if new_count == 1 else 'tasks'}")
    if closed_count:
        parts.append(f"{closed_count} closed")
    if transition_count:
        s = "" if transition_count == 1 else "s"
        parts.append(f"{transition_count} transition{s}")
    return ", ".join(parts)


def render_alerts(transitions, new_tasks, run_stats, analytics=None):
    """Render Task Alerts markdown with callout-based sections.

    Sections: new tasks, state changes, escalations, stale items.
    Returns a markdown string.
    """
    lines = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# Task Alerts \u2014 {now_str}")
    lines.append("")

    # New tasks
    lines.append("> [!abstract] New Tasks")
    lines.append(">")
    if new_tasks:
        for t in new_tasks:
            direction = t.get("direction", "inbound")
            arrow = "<-" if direction == "inbound" else "->"
            sender = t.get("sender", "Unknown")
            lines.append(f"> - {arrow} **{t.get('title', 'Untitled')}** ({sender})")
    else:
        lines.append("> *No new tasks this sync.*")
    lines.append("")

    # State changes
    lines.append("> [!info] State Changes")
    lines.append(">")
    if transitions:
        for task_id, old_state, new_state, reason in transitions:
            lines.append(f"> - {task_id}: {old_state} -> {new_state} \u2014 {reason}")
    else:
        lines.append("> *No state changes.*")
    lines.append("")

    # Escalations (tasks with escalation bonus > 0)
    lines.append("> [!warning] Escalations")
    lines.append(">")
    escalation_items = []
    if analytics:
        for task_id, entries in analytics.get("escalation_history", {}).items():
            if len(entries) >= 2:
                urgencies = [e["urgency"] for e in entries]
                if any(urgencies[i] > urgencies[i - 1] for i in range(1, len(urgencies))):
                    escalation_items.append(
                        f"> - {task_id}: {len(entries)} mentions, urgency pattern {urgencies}"
                    )
    if escalation_items:
        lines.extend(escalation_items)
    else:
        lines.append("> *No escalation patterns detected.*")
    lines.append("")

    # Stale items (open or needs_followup for > 7 days)
    lines.append("> [!danger] Stale Items")
    lines.append(">")
    stale_items = []
    store = None
    try:
        store = load_tasks()
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if store:
        for t in store["tasks"]:
            if t.get("state") in ("open", "needs_followup"):
                created = datetime.fromisoformat(t.get("created", datetime.now().isoformat()))
                age_days = (datetime.now() - created).days
                if age_days > 7:
                    stale_items.append(
                        f"> - {t['id']}: **{t.get('title', '')}** ({age_days}d old, {t['state']})"
                    )
    if stale_items:
        lines.extend(stale_items[:10])  # cap at 10
        if len(stale_items) > 10:
            lines.append(f"> - ...and {len(stale_items) - 10} more")
    else:
        lines.append("> *No stale items.*")
    lines.append("")

    return "\n".join(lines)


def write_alerts(markdown, vault_path, filename="Task Alerts.md"):
    """Write alerts markdown to the Obsidian vault."""
    os.makedirs(vault_path, exist_ok=True)
    path = os.path.join(vault_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return path


# ---------------------------------------------------------------------------
# Sync Log
# ---------------------------------------------------------------------------


def render_sync_log(run_log_entries, max_entries=20):
    """Render a Sync Log markdown page from run_log entries (newest first)."""
    lines = ["# Sync Log", ""]
    if not run_log_entries:
        lines.append("*No syncs recorded yet.*")
        return "\n".join(lines)

    recent = list(reversed(run_log_entries))[:max_entries]
    for entry in recent:
        ts_raw = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            ts = ts_raw

        is_full = "sources_queried" in entry
        if is_full:
            callout = "[!tip] Full Sync"
        else:
            callout = "[!note] Refresh"

        new = entry.get("new_tasks", 0)
        trans = entry.get("transitions", 0)
        merged = entry.get("merged", 0)
        skipped = entry.get("skipped", 0)

        lines.append(f"> {callout} \u2014 {ts}")
        lines.append(">")
        lines.append(f"> +{new} new \u00b7 {trans} transitions \u00b7 {merged} merged \u00b7 {skipped} skipped")

        obs_closed = entry.get("obsidian_closed", [])
        if obs_closed:
            lines.append(f"> Closed from Obsidian: {', '.join(obs_closed)}")

        sources = entry.get("sources_queried", [])
        if sources:
            lines.append(f"> Sources: {', '.join(sources)}")

        lines.append("")

    return "\n".join(lines)


def write_sync_log(markdown, vault_path, filename="Sync Log.md"):
    """Write sync log markdown to the Obsidian vault."""
    os.makedirs(vault_path, exist_ok=True)
    path = os.path.join(vault_path, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return path


# ---------------------------------------------------------------------------
# Phase 5: Run Log
# ---------------------------------------------------------------------------


def log_run(stats):
    """Append a run entry to the run log."""
    log = load_run_log()
    entry = {
        "timestamp": datetime.now().isoformat(),
        **stats,
    }
    log["runs"].append(entry)
    save_run_log(log)
    return entry


# ---------------------------------------------------------------------------
# Phase 5b: Step-Based Pipeline
# ---------------------------------------------------------------------------


def sync_prepare():
    """Prepare sync context — the first step of the pipeline.

    Reads back Obsidian completions, calculates the since-date, builds
    all queries, and loads open tasks. Returns a sync_context dict that
    the rest of the pipeline consumes.

    Returns:
        dict with keys: config, since_date, all_queries, open_tasks,
        pre_closed (task IDs closed from Obsidian), run_stats.
    """
    config = load_config()

    # Read back completions from Obsidian
    vault_path = config.get("vault_path", "")
    dash_file = config.get("dashboard_filename", "TaskNemo.md")
    pre_closed = []
    if vault_path:
        pre_closed = sync_dashboard_completions(vault_path, dash_file)
        if pre_closed:
            score_all_tasks(config)

    # Import inbox tasks (from dashboard section + legacy file)
    inbox_ids = []
    if vault_path:
        inbox_ids += sync_inbox(vault_path, dash_file)
        inbox_ids += sync_inbox(vault_path, "Task Inbox.md")

    since_date = calculate_since_date(
        config.get("last_run"), config.get("overlap_days", 2)
    )
    since_dt = datetime.strptime(since_date, "%B %d, %Y")
    since_date_iso = since_dt.strftime("%Y-%m-%d")
    all_queries = build_all_queries(since_date, config)
    open_tasks = list_tasks(states={"open", "needs_followup", "waiting"})
    all_tasks = list_tasks()  # All states including closed/likely_done for dedup

    return {
        "config": config,
        "since_date": since_date,
        "since_date_iso": since_date_iso,
        "all_queries": all_queries,
        "open_tasks": open_tasks,
        "all_tasks": all_tasks,
        "pre_closed": pre_closed,
        "inbox_ids": inbox_ids,
        "run_stats": {
            "new_tasks": 0,
            "transitions": 0,
            "merged": 0,
            "skipped": 0,
            "source_counts": {},
        },
    }


def process_source_items(source, items, sync_context):
    """Process extracted items from a single WorkIQ source response.

    Claude extracts structured items from each WorkIQ response, then calls
    this function. For each item:
      1. If already_done → skip, increment skipped count.
      2. Try find_cross_source_match() against open tasks.
      3. If match → merge_cross_source_signal(), add to merged_ids.
      4. If no match → add to to_create list (Claude calls add_task() for each).

    Args:
        source: str — the source name (e.g., "teams", "email", "calendar").
        items: list of dicts with keys:
            sender, title, link, source, direction, signal_type,
            already_done, extra (dict with description, due_hint, etc.)
        sync_context: dict from sync_prepare().

    Returns:
        dict with keys: source, to_create, merged_ids, signals, skipped.

    Note: This function does NOT call add_task() — it returns to_create
    so Claude can do a final sanity check before persisting.
    """
    all_tasks = sync_context.get("all_tasks", sync_context["open_tasks"])
    run_stats = sync_context["run_stats"]
    to_create = []
    merged_ids = []
    signals = []
    skipped = 0

    for item in items:
        # Skip items the user already completed
        if item.get("already_done"):
            skipped += 1
            run_stats["skipped"] += 1
            continue

        # Skip items with extracted_date before the sync window
        item_date = item.get("extra", {}).get("extracted_date", "")
        since_iso = sync_context.get("since_date_iso", "")
        if item_date and since_iso and item_date < since_iso:
            skipped += 1
            run_stats["skipped"] += 1
            continue

        # Try cross-source match against ALL tasks (including closed)
        match = find_cross_source_match(
            {"sender": item.get("sender", ""), "title": item.get("title", "")},
            all_tasks,
        )

        if match:
            if match.get("state") in ("closed", "likely_done"):
                # Don't recreate closed/likely_done tasks
                skipped += 1
                run_stats["skipped"] += 1
                continue
            merge_cross_source_signal(
                match, source, item.get("link", "")
            )
            merged_ids.append(match["id"])
            run_stats["merged"] += 1
        else:
            to_create.append(item)

        # Collect signals for transition evaluation
        if item.get("signal_type"):
            signals.append({
                "sender": item.get("sender", ""),
                "topic": item.get("title", ""),
                "thread_id": item.get("extra", {}).get("thread_id", ""),
                "signal_type": item["signal_type"],
                "signal": item.get("extra", {}).get("evidence", ""),
                "teams_link": item.get("link", ""),
            })

    return {
        "source": source,
        "to_create": to_create,
        "merged_ids": merged_ids,
        "signals": signals,
        "skipped": skipped,
    }


def build_completion_signals(items, open_tasks):
    """Build completion signals by matching completion evidence to open tasks.

    Takes Claude's extracted completion items (from analyzing conversations,
    emails, etc.) and matches them to open tasks via
    match_conversation_to_tasks(). Returns only signals with a plausible
    match, preventing accidental signals for non-existent tasks.

    Args:
        items: list of dicts with keys:
            sender (str), topic (str), thread_id (str), evidence (str).
        open_tasks: list of task dicts to match against.

    Returns:
        list of dicts: [{"task_id": str, "signal_type": "completion",
                         "signal": str}]
    """
    signals = []
    for item in items:
        conversation = {
            "sender": item.get("sender", ""),
            "topic": item.get("topic", ""),
            "thread_id": item.get("thread_id", ""),
        }
        matched = match_conversation_to_tasks(conversation, open_tasks)
        if matched:
            signals.append({
                "task_id": matched["id"],
                "signal_type": "completion",
                "signal": item.get("evidence", "Completion detected"),
            })
    return signals


def run_transitions(conversation_signals, sync_context):
    """Run the mechanical transition sequence.

    Wraps: evaluate_transitions() → score_all_tasks() → save_tasks()
    → update config["last_run"] → save_config().

    Args:
        conversation_signals: list of signal dicts for evaluate_transitions().
        sync_context: dict from sync_prepare().

    Returns:
        dict with keys: transitions (list of tuples), run_stats (updated).
    """
    config = sync_context["config"]
    run_stats = sync_context["run_stats"]

    all_tasks = load_tasks()["tasks"]
    today = datetime.now().isoformat()

    transitions = evaluate_transitions(
        all_tasks, followup_signals={}, today=today,
        conversation_signals=conversation_signals, config=config,
    )
    run_stats["transitions"] = len(transitions)

    # Record response times for tasks transitioning to likely_done or closed
    analytics = load_analytics()
    task_map = {t["id"]: t for t in all_tasks}
    for task_id, _old_state, new_state, _reason in transitions:
        if new_state in ("likely_done", "closed"):
            t = task_map.get(task_id)
            if t:
                created = datetime.fromisoformat(t.get("created", today))
                hours = (datetime.fromisoformat(today) - created).total_seconds() / 3600
                record_response_time(t.get("sender", ""), hours, analytics)

    score_all_tasks(config, analytics)
    save_tasks(load_tasks())

    config["last_run"] = today
    save_config(config)

    return {
        "transitions": transitions,
        "run_stats": run_stats,
    }


def finalize_sync(run_stats, sync_context, transitions=None, new_tasks=None):
    """Render dashboard, write it, optionally write alerts, and log the run.

    Args:
        run_stats: dict with new_tasks, transitions, merged, skipped counts.
        sync_context: dict from sync_prepare().
        transitions: optional list of (task_id, old, new, reason) tuples.
        new_tasks: optional list of new task dicts.

    Returns:
        str — path where the dashboard was written.
    """
    config = sync_context["config"]
    vault_path = config.get("vault_path", "")
    dash_file = config.get("dashboard_filename", "TaskNemo.md")

    # Second readback: catch any checkboxes the user ticked during the sync.
    # Without this, the re-render overwrites user-checked [x] marks.
    if vault_path:
        late_closed = sync_dashboard_completions(vault_path, dash_file)
        if late_closed:
            score_all_tasks(config)

    store = load_tasks()
    md = render_dashboard(store["tasks"], config, run_stats=run_stats)
    path = write_dashboard(md, vault_path, dash_file)

    # Write alerts if transition data is available
    if transitions is not None:
        analytics = load_analytics()
        alerts_md = render_alerts(
            transitions, new_tasks or [], run_stats, analytics,
        )
        alerts_file = config.get("alerts_filename", "Task Alerts.md")
        write_alerts(alerts_md, vault_path, alerts_file)

    log_run(run_stats)

    # Write sync log
    if vault_path:
        run_log = load_run_log()
        sync_md = render_sync_log(run_log["runs"])
        write_sync_log(sync_md, vault_path)

    # Desktop notification
    summary = _build_change_summary(
        run_stats.get("new_tasks", 0),
        len(sync_context.get("pre_closed", [])),
        run_stats.get("transitions", 0),
    )
    if summary:
        _notify("TaskNemo", summary)

    return path


# ---------------------------------------------------------------------------
# Phase 5: CLI
# ---------------------------------------------------------------------------


def cmd_status():
    """Print task counts by state."""
    tasks = list_tasks()
    counts = {}
    for t in tasks:
        state = t.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    total = len(tasks)
    print(f"TaskNemo Status ({total} total)")
    print("-" * 35)
    for state in ["open", "waiting", "needs_followup", "likely_done", "closed"]:
        print(f"  {state:20s} {counts.get(state, 0)}")


def cmd_list():
    """Print all active tasks, with subtasks nested under parents."""
    tasks = list_tasks()
    subtask_ids = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids.add(sid)

    active = [t for t in tasks if t.get("state") != "closed" and t["id"] not in subtask_ids]
    active_sorted = sorted(active, key=lambda t: t.get("score", 0), reverse=True)
    task_map = {t["id"]: t for t in tasks}

    if not active_sorted:
        print("No active tasks.")
        return
    print(f"{'ID':10s} {'Score':6s} {'State':16s} {'Sender':20s} Title")
    print("-" * 80)
    for t in active_sorted:
        print(f"{t['id']:10s} {t.get('score', 0):<6d} {t.get('state', ''):16s} {t.get('sender', ''):20s} {t.get('title', '')}")
        for sid in t.get("subtask_ids", []):
            child = task_map.get(sid)
            if child and child.get("state") != "closed":
                print(f"  {'+-' + child['id']:10s} {child.get('score', 0):<6d} {child.get('state', ''):16s} {child.get('sender', ''):20s} {child.get('title', '')}")


def cmd_close(task_id):
    """Manually close a task."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    if task["state"] == "closed":
        print(f"Task {task_id} is already closed.")
        return
    transition_task(task, "closed", "Manually closed by user")
    update_task(task_id, task)
    print(f"Closed {task_id}: {task.get('title', '')}")


def cmd_check():
    """Lightweight status check — reads local data only, no WorkIQ queries.

    Prints: time since last sync, task counts by state, top 3 focus items
    (score >= 70), stale item count, and a recommendation if a full sync
    is needed.
    """
    config = load_config()
    tasks = list_tasks()

    # Time since last sync
    last_run = config.get("last_run")
    if last_run:
        delta = datetime.now() - datetime.fromisoformat(last_run)
        hours_since = delta.total_seconds() / 3600
        print(f"Last sync: {last_run} ({_format_age(last_run)})")
    else:
        hours_since = float("inf")
        print("Last sync: never")

    # Task counts by state
    counts = {}
    for t in tasks:
        state = t.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    total = len(tasks)
    print(f"\nTasks: {total} total")
    for state in ["open", "waiting", "needs_followup", "likely_done", "closed"]:
        c = counts.get(state, 0)
        if c:
            print(f"  {state:20s} {c}")

    # Top 3 focus items (score >= 70)
    active = [t for t in tasks if t.get("state") not in ("closed", "likely_done")]
    focus = sorted(active, key=lambda t: t.get("score", 0), reverse=True)
    focus = [t for t in focus if t.get("score", 0) >= 70][:3]
    if focus:
        print("\nFocus now:")
        for t in focus:
            print(f"  [{t.get('score', 0)}] {t['id']}: {t.get('title', '')}")

    # Stale items
    stale = [t for t in active if t.get("state") in ("open", "needs_followup")
             and (datetime.now() - datetime.fromisoformat(
                 t.get("created", datetime.now().isoformat()))).days > 7]
    if stale:
        print(f"\nStale items: {len(stale)}")

    # Recommendation
    threshold = config.get("full_sync_threshold_hours", 8)
    if hours_since > threshold:
        print(f"\n>> Full sync recommended (>{threshold}h since last run)")


def cmd_sync_info():
    """Print compact pipeline instructions for Claude Code orchestration.

    Uses sync_prepare() internally to gather context, then prints a
    structured summary of queries to run and pipeline steps to follow.
    """
    ctx = sync_prepare()
    config = ctx["config"]
    all_queries = ctx["all_queries"]
    open_tasks = ctx["open_tasks"]
    pre_closed = ctx["pre_closed"]
    since = ctx["since_date"]

    if pre_closed:
        print(f"[pre-sync] Closed {len(pre_closed)} tasks marked done in Obsidian: {', '.join(pre_closed)}")

    inbox_ids = ctx.get("inbox_ids", [])
    if inbox_ids:
        print(f"[pre-sync] Imported {len(inbox_ids)} inbox task(s): {', '.join(inbox_ids)}")

    print("=== TaskNemo Sync ===")
    print(f"Since: {since} | Last run: {config.get('last_run', 'never')} | Open tasks: {len(open_tasks)}")
    print()

    # Check for 2-phase vs legacy mode
    if "phase1" in all_queries:
        # 2-phase display
        query_num = 1
        print("--- Phase 1: Discovery (run all in parallel) ---")
        for source, query in all_queries["phase1"].items():
            print(f"  {query_num}. [{source.title()} discovery] {query}")
            query_num += 1

        print()
        print("--- Phase 2: Detail (per-item, after Phase 1) ---")
        print("  For each discovered item, call:")
        print("    build_detail_queries(source, items, since_date, config)")
        print("  Process sent_items details FIRST for completion evidence.")
        print()

        print("--- Already-Targeted (run as-is) ---")
        if "transcript_discovery" in all_queries:
            print(f"  {query_num}. [Transcript discovery] {all_queries['transcript_discovery']}")
            query_num += 1
            print(f"  {query_num}. [Transcript extraction] {all_queries['transcript_extraction']}")
            query_num += 1
        if "doc_mentions" in all_queries:
            dm = all_queries["doc_mentions"]
            print(f"  {query_num}. [Doc mentions - email] {dm.get('email_notifications', '')}")
            query_num += 1
            print(f"  {query_num}. [Doc mentions - direct] {dm.get('direct_search', '')}")
            query_num += 1
        if "validation" in all_queries:
            print()
            print(f"--- Phase 3: Validation (run AFTER all extraction) ---")
            print(f"  {query_num}. [Validation] {all_queries['validation']}")
            query_num += 1
    else:
        # Legacy single-phase display
        query_num = 1
        print("WorkIQ queries (run all via ask_work_iq):")
        if "teams" in all_queries:
            print(f"  {query_num}. [Teams conversations] {all_queries['teams']['conversations']}")
            query_num += 1
        if "email" in all_queries:
            print(f"  {query_num}. [Email - all] {all_queries['email']['all']}")
            query_num += 1
        if "calendar" in all_queries:
            print(f"  {query_num}. [Calendar - all] {all_queries['calendar']['all']}")
            query_num += 1
            print(f"  {query_num}. [Transcript discovery] {all_queries['calendar']['transcript_discovery']}")
            query_num += 1
            print(f"  {query_num}. [Transcript extraction] {all_queries['calendar']['transcript_extraction']}")
            query_num += 1
        if "sent_items" in all_queries:
            print(f"  {query_num}. [Sent items] {all_queries['sent_items']}")
            query_num += 1
        if "outbound" in all_queries:
            print(f"  {query_num}. [Outbound unreplied] {all_queries['outbound']}")
            query_num += 1
        if "all_received" in all_queries:
            print(f"  {query_num}. [All received messages] {all_queries['all_received']}")
            query_num += 1
        if "key_contacts" in all_queries and all_queries["key_contacts"]:
            for name, q in all_queries["key_contacts"].items():
                print(f"  {query_num}. [Key contact: {name}] {q}")
                query_num += 1

    print(f"""
Pipeline (call in order):
  0. sync_prepare()             -> returns sync_context (already done above)
  1. Run WorkIQ queries (Phase 1 discovery, then Phase 2 detail per item)
  2. For each source response:
     - Extract items as [{{sender, title, link, direction, signal_type, already_done, extra}}]
     - Call process_source_items(source, items, sync_context)
     - For each item in result["to_create"]: call add_task(item, config)
  3. Build completion signals from conversation analysis:
     - Call build_completion_signals(completion_items, open_tasks)
  4. Call run_transitions(all_signals, sync_context)
  5. Run validation query — compare against extracted tasks, verify gaps
  6. Call finalize_sync(run_stats, sync_context)

CRITICAL: Always check sent items BEFORE creating tasks. Transcripts
are the richest task source — extract BOTH inbound and outbound.""")


def cmd_migrate():
    """Migrate existing tasks: add grouping fields, source fields, auto-group, rescore, re-render."""
    store = load_tasks()
    config = load_config()

    # Step 1: Add new fields to every task
    for task in store["tasks"]:
        task.setdefault("parent_id", None)
        task.setdefault("subtask_ids", [])
        if not task.get("thread_id"):
            task["thread_id"] = extract_thread_id(task.get("teams_link", ""))
        # Source fields (v2)
        task.setdefault("source", "teams")
        task.setdefault("source_link", "")
        task.setdefault("source_metadata", {})
        # Direction field (v3)
        task.setdefault("direction", "inbound")

    # Add new config keys if missing
    config.setdefault("sources_enabled", ["teams", "email", "calendar"])
    config.setdefault("email_query_template",
        "Show me all my emails since {since_date} that require action from me — "
        "things I need to reply to, review, approve, or follow up on. Exclude "
        "newsletters, FYI-only messages, and automated notifications. For each "
        "email, include the sender, subject, a brief summary of what's needed, "
        "and the Outlook link.")
    config.setdefault("email_completion_query_template",
        "Which of my action-required emails since {since_date} have been resolved? "
        "Look for emails where I already replied, the request was completed, or "
        "someone else handled it. Include the sender, subject, and evidence of "
        "resolution.")
    config.setdefault("calendar_query_template",
        "What meetings have I had since {since_date} that have action items "
        "assigned to me? Check meeting notes, transcripts, and follow-up "
        "messages. For each action item, include the meeting title, who assigned "
        "it, what the action item is, and the meeting link.")
    config.setdefault("scoring", {"calendar_boost": 5})
    config.setdefault("transcript_discovery_query_template",
        "Show me ALL my meetings since {since_date} that have a recording "
        "or transcript available. For each meeting, include the title, date, "
        "attendees, and the recording/transcript link.")
    config.setdefault("transcript_extraction_query_template",
        "For each of my meetings since {since_date} that has a transcript, "
        "read the transcript and extract ALL action items and commitments. "
        "For each one include: (1) what the action item is, (2) who committed "
        "to it — me or someone else, (3) any deadline mentioned, (4) the "
        "meeting title and link. Be exhaustive — include every commitment, "
        "even small ones.")
    config.setdefault("sent_items_query_template",
        "Check my sent emails and outgoing Teams messages since {since_date}. "
        "What actions have I already completed? Look for emails I sent, "
        "documents I shared, replies I gave, and messages where I delivered "
        "on a commitment. For each, include what I did, who I sent it to, "
        "when, and the link.")
    config.setdefault("outbound_query_template",
        "Check my sent emails and outgoing Teams messages since {since_date}. "
        "What are the things I asked other people to do that they have NOT "
        "responded to yet? Look for messages where I made a request, asked a "
        "question, or assigned something and the other person has not replied "
        "or acknowledged. For each, include the person, what I asked, when I "
        "sent it, and the link.")
    config.setdefault("all_received_query_template",
        "Show me ALL messages I received in ALL Teams chats (1:1, group chats, "
        "and channels) since {since_date}. Include: sender name, full message "
        "text, chat/channel name, timestamp, and the Teams link. Do not filter "
        "by reply status. Do not summarize — show actual message content.")
    config.setdefault("key_contacts", [])
    # v2 pipeline: query_mode controls raw vs smart WorkIQ queries
    config.setdefault("query_mode", "raw")

    # v2 scoring + alerts config
    config.setdefault("alerts_filename", "Task Alerts.md")
    config.setdefault("full_sync_threshold_hours", 8)

    # Initialize analytics.json if it doesn't exist
    if not os.path.exists(ANALYTICS_PATH):
        save_analytics(dict(_ANALYTICS_DEFAULT))
        print("[migrate] Created data/analytics.json")

    save_tasks(store)
    save_config(config)
    print(f"[migrate] Added grouping + source + direction fields to {len(store['tasks'])} tasks.")

    # Step 2: Auto-group by sender + thread_id
    groups = suggest_groups(store["tasks"])
    for g in groups:
        group_tasks(g["parent_id"], g["child_ids"], store)
        print(f"[migrate] Grouped: {g['parent_id']} <- {g['child_ids']}")

    if not groups:
        print("[migrate] No auto-groupings found.")

    # Step 3: Rescore all tasks
    for task in store["tasks"]:
        if task.get("state") != "closed":
            score_task(task, config)
    save_tasks(store)
    print("[migrate] Rescored all active tasks.")

    # Step 4: Re-render dashboard
    vault_path = config.get("vault_path", "")
    if vault_path:
        md = render_dashboard(store["tasks"], config)
        path = write_dashboard(md, vault_path, config.get("dashboard_filename", "TaskNemo.md"))
        print(f"[migrate] Dashboard written to {path}")
    else:
        print("[migrate] No vault_path configured; skipping dashboard write.")

    print("[migrate] Done.")


def cmd_pin(task_id):
    """Pin a task for priority boost, rescore, and print confirmation."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    analytics = load_analytics()
    pin_task(task_id, analytics)
    config = load_config()
    score_task(task, config, analytics)
    update_task(task_id, task)
    print(f"Pinned {task_id}: {task.get('title', '')} (score: {task['score']})")


def cmd_unpin(task_id):
    """Unpin a task, rescore, and print confirmation."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    analytics = load_analytics()
    unpin_task(task_id, analytics)
    config = load_config()
    score_task(task, config, analytics)
    update_task(task_id, task)
    print(f"Unpinned {task_id}: {task.get('title', '')} (score: {task['score']})")


def cmd_add(title, sender=None, source="manual", direction="inbound", due_hint=None, description=None):
    """Manually add a task from CLI or Claude Code."""
    config = load_config()
    task_dict = {
        "title": title,
        "sender": sender or "me",
        "source": source,
        "direction": direction,
    }
    if due_hint:
        task_dict["due_hint"] = due_hint
    if description:
        task_dict["description"] = description
    task_dict["state_history"] = [
        {"state": "open", "reason": "Manually added", "date": datetime.now().isoformat()}
    ]
    task_id = add_task(task_dict, config)
    print(f"Created {task_id}: {title}")
    return task_id


def cmd_init(force=False, vault_path=None):
    """First-time setup: create data files and config."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(CONFIG_PATH) and not force:
        print(f"Config already exists: {CONFIG_PATH}")
        print("Use --force to overwrite.")
        return
    if vault_path is None:
        vault_path = input("Obsidian vault path [~/Documents/TaskVault]: ").strip()
        if not vault_path:
            vault_path = os.path.join(os.path.expanduser("~"), "Documents", "TaskVault")
    # Load template config
    template_path = os.path.join(DATA_DIR, "config.template.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "vault_path": "",
            "dashboard_filename": "TaskNemo.md",
            "overlap_days": 2,
            "max_followup_queries": 5,
            "followup_age_threshold_days": 3,
            "conversation_query_template": "Show me all my Teams conversations since {since_date}",
            "completion_query_template": "Which of my Teams conversations since {since_date} have been resolved or completed, where someone said thanks or confirmed something was finished?",
            "auto_close_likely_done_days": 3,
            "auto_close_stale_days": 7,
            "auto_close_open_days": 10,
            "urgency_keywords": ["urgent", "asap", "eod", "eow", "today", "tomorrow", "blocker", "blocking", "critical", "immediately", "p0", "p1", "deadline", "overdue", "time-sensitive", "high priority"],
            "completion_keywords": ["thanks", "done", "shipped", "approved", "completed", "merged", "resolved", "closed", "fixed", "lgtm", "looks good"],
            "waiting_keywords": ["waiting", "pending", "blocked on", "need input", "awaiting", "depends on", "hold", "on hold"],
            "stakeholders": {},
            "sources_enabled": ["teams", "email", "calendar"],
            "query_mode": "raw",
            "email_query_template": "Show me ALL my emails since {since_date}. For each, include: sender, subject, body preview, date, whether I replied, and the Outlook link.",
            "email_completion_query_template": "Which of my action-required emails since {since_date} have been resolved? Look for emails where I already replied, the request was completed, or someone else handled it. Include the sender, subject, and evidence of resolution.",
            "calendar_query_template": "Show me ALL my calendar events since {since_date}. Include: title, date/time, attendees, any meeting notes, and the link.",
            "transcript_discovery_query_template": "Show me ALL my meetings since {since_date} that have a recording or transcript available. For each meeting, include the title, date, attendees, and the recording/transcript link.",
            "transcript_extraction_query_template": "For each of my meetings since {since_date} that has a transcript, read the transcript and extract ALL action items and commitments. For each one include: (1) what the action item is, (2) who committed to it — me or someone else, (3) any deadline mentioned, (4) the meeting title and link. Be exhaustive — include every commitment, even small ones.",
            "sent_items_query_template": "Check my sent emails and outgoing Teams messages since {since_date}. What actions have I already completed? Look for emails I sent, documents I shared, replies I gave, and messages where I delivered on a commitment. For each, include what I did, who I sent it to, when, and the link.",
            "outbound_query_template": "Show me ALL my sent messages and emails since {since_date} where the recipient has NOT replied. Include: recipient, what I said, when, and the link.",
            "all_received_query_template": "Show me ALL messages I received in ALL Teams chats (1:1, group chats, and channels) since {since_date}. Include: sender name, full message text, chat/channel name, timestamp, and the Teams link. Do not filter by reply status. Do not summarize — show actual message content.",
            "key_contacts": [],
            "scoring": {"calendar_boost": 5},
            "last_run": None,
            "next_task_id": 1,
            "alerts_filename": "Task Alerts.md",
            "full_sync_threshold_hours": 8,
        }
    config["vault_path"] = vault_path
    save_json(CONFIG_PATH, config)
    if not os.path.exists(TASKS_PATH) or force:
        save_json(TASKS_PATH, {"tasks": []})
    if not os.path.exists(RUN_LOG_PATH) or force:
        save_json(RUN_LOG_PATH, {"runs": []})
    print(f"Initialized task dashboard in {DATA_DIR}")
    print(f"  Vault path: {vault_path}")
    print(f"  Config:     {CONFIG_PATH}")
    print(f"  Tasks:      {TASKS_PATH}")
    print(f"  Run log:    {RUN_LOG_PATH}")
    print()
    print("Next steps:")
    print("  1. Edit data/config.json to add your stakeholders")
    print("  2. Run: python task_dashboard.py check")


def _deep_merge_defaults(template, current):
    """Merge template keys into current config, preserving existing values.

    Only adds keys that don't exist in current. For nested dicts, merges
    recursively (adds missing sub-keys without overwriting existing ones).
    """
    added = []
    for key, value in template.items():
        if key not in current:
            current[key] = value
            added.append(key)
        elif isinstance(value, dict) and isinstance(current[key], dict):
            sub_added = _deep_merge_defaults(value, current[key])
            added.extend(f"{key}.{k}" for k in sub_added)
    return added


def cmd_upgrade():
    """Merge new config keys from template into existing config.

    Preserves all user values (stakeholders, vault_path, etc.).
    Only adds keys present in the template but missing from config.
    Then runs migrate for task schema updates.
    """
    if not os.path.exists(CONFIG_PATH):
        print("No config found. Run 'python task_dashboard.py init' first.")
        return

    template_path = os.path.join(DATA_DIR, "config.template.json")
    if not os.path.exists(template_path):
        print("No config.template.json found — nothing to merge.")
        print("Running migrate for task schema updates...")
        cmd_migrate()
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    config = load_config()

    # Merge new keys from template (never overwrites existing values)
    added = _deep_merge_defaults(template, config)

    # Ensure query_strategy is set (upgrade from legacy)
    if "query_strategy" not in config:
        config["query_strategy"] = "two_phase"
        added.append("query_strategy")
    if "max_detail_queries_per_source" not in config:
        config["max_detail_queries_per_source"] = 25
        added.append("max_detail_queries_per_source")

    if added:
        save_config(config)
        print(f"[upgrade] Added {len(added)} new config key(s):")
        for key in added:
            print(f"  + {key}")
    else:
        print("[upgrade] Config is up to date — no new keys.")

    # Run task schema migration too
    print()
    cmd_migrate()


_INBOX_INLINE_FLAG_RE = re.compile(r"\s+--(\w+)\s+(.+?)(?=\s+--|$)")

_INBOX_TASK_RE = re.compile(r"^[-*]\s+\[?\s?\]?\s*(.+)$")


def _parse_inbox_tasks(task_lines, config):
    """Parse task lines and create tasks. Returns list of created task IDs."""
    created_ids = []
    for line in task_lines:
        if not line or line.startswith("#"):
            continue
        m = _INBOX_TASK_RE.match(line)
        if not m:
            continue
        raw_title = m.group(1).strip()
        if not raw_title:
            continue

        # Parse inline flags (--sender, --due)
        sender = "me"
        due_hint = None
        flags = _INBOX_INLINE_FLAG_RE.findall(raw_title)
        for flag_name, flag_value in flags:
            if flag_name == "sender":
                sender = flag_value.strip()
            elif flag_name == "due":
                due_hint = flag_value.strip()
        # Remove flags from title
        title = _INBOX_INLINE_FLAG_RE.sub("", raw_title).strip()
        if not title:
            continue

        task_dict = {
            "title": title,
            "sender": sender,
            "source": "manual",
            "direction": "inbound",
            "state_history": [
                {"state": "open", "reason": "Imported from inbox", "date": datetime.now().isoformat()}
            ],
        }
        if due_hint:
            task_dict["due_hint"] = due_hint
        task_id = add_task(task_dict, config)
        created_ids.append(task_id)
    return created_ids


def sync_inbox(vault_path, filename="Task Inbox.md"):
    """Import tasks from the Obsidian inbox file or dashboard inbox section.

    When filename is the dashboard file (e.g., TaskNemo.md), parses the
    embedded '## Task Inbox' section and clears it after import.
    Otherwise, treats the whole file as an inbox (legacy behavior).

    Each line matching '- [ ] text' or '- text' becomes a new task.
    Lines starting with # are ignored (headers/comments).
    Returns list of created task IDs.
    """
    path = os.path.join(vault_path, filename)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")

    config = load_config()

    # Check if this file has an embedded ## Task Inbox section
    inbox_start = None
    inbox_end = None
    for i, line in enumerate(lines):
        if line.strip() == "## Task Inbox":
            inbox_start = i
        elif inbox_start is not None and line.strip().startswith("## ") and i > inbox_start:
            inbox_end = i
            break
        elif inbox_start is not None and line.strip() == "---" and i > inbox_start + 1:
            inbox_end = i
            break

    if inbox_start is not None:
        # Parse only the inbox section from the dashboard
        section_end = inbox_end if inbox_end is not None else len(lines)
        task_lines = [l.strip() for l in lines[inbox_start + 1:section_end]
                      if l.strip() and not l.strip().startswith("#")]
        created_ids = _parse_inbox_tasks(task_lines, config)

        # Clear the inbox section (preserve header + instructions + empty bullet)
        if created_ids:
            new_section = [
                "## Task Inbox",
                "Add tasks below \u2014 they'll be imported on next sync or refresh.",
                "",
                "- ",
            ]
            new_lines = lines[:inbox_start] + new_section
            if inbox_end is not None:
                new_lines += lines[inbox_end:]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))

        return created_ids

    # Legacy behavior: whole file is an inbox
    header_lines = []
    task_lines = []
    in_header = True
    for line in lines:
        stripped = line.strip()
        if in_header and (stripped.startswith("#") or stripped == ""):
            header_lines.append(line + "\n")
        else:
            in_header = False
            task_lines.append(stripped)

    created_ids = _parse_inbox_tasks(task_lines, config)

    # Rewrite file to just the header
    if created_ids:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(header_lines)

    return created_ids


def cmd_refresh():
    """Lightweight refresh — no WorkIQ queries needed.

    1. Read back Obsidian completions (close checked tasks)
    2. Run state machine transitions (stale → needs_followup, likely_done → closed)
    3. Rescore all tasks
    4. Re-render dashboard + alerts

    Designed to run on a schedule (e.g., every 30 min via Task Scheduler).
    """
    config = load_config()
    analytics = load_analytics()
    vault_path = config.get("vault_path", "")
    dash_file = config.get("dashboard_filename", "TaskNemo.md")

    # Step 1: Read back Obsidian completions
    closed_ids = []
    if vault_path:
        closed_ids = sync_dashboard_completions(vault_path, dash_file)
        if closed_ids:
            print(f"[refresh] Closed from Obsidian: {closed_ids}")

    # Step 1b: Import inbox tasks
    inbox_ids = []
    if vault_path:
        inbox_ids = sync_inbox(vault_path)
        if inbox_ids:
            print(f"[refresh] Imported from inbox: {inbox_ids}")

    # Step 2: Run state machine (stale detection, auto-close likely_done)
    store = load_tasks()
    today = datetime.now().isoformat()
    transitions = evaluate_transitions(
        store["tasks"], followup_signals={}, today=today,
        conversation_signals=[], config=config,
    )
    if transitions:
        save_tasks(store)
        for tid, old, new, reason in transitions:
            print(f"[refresh] {tid}: {old} -> {new} ({reason})")
            # Record response times
            task_map = {t["id"]: t for t in store["tasks"]}
            if new in ("likely_done", "closed"):
                t = task_map.get(tid)
                if t:
                    created = datetime.fromisoformat(t.get("created", today))
                    hours = (datetime.fromisoformat(today) - created).total_seconds() / 3600
                    record_response_time(t.get("sender", ""), hours, analytics)

    # Step 3: Rescore all tasks
    score_all_tasks(config, analytics)

    # Step 4: Re-render dashboard
    if vault_path:
        all_tasks = load_tasks()["tasks"]
        md = render_dashboard(all_tasks, config, analytics=analytics)
        path = write_dashboard(md, vault_path, dash_file)
        print(f"[refresh] Dashboard written to {path}")

        # Write alerts if there were transitions
        if transitions:
            alerts_file = config.get("alerts_filename", "Task Alerts.md")
            alerts_md = render_alerts(transitions, [], {}, analytics)
            write_alerts(alerts_md, vault_path, alerts_file)
            print(f"[refresh] Alerts written")
    else:
        print("[refresh] No vault_path configured; skipping dashboard write.")

    # Step 5: Log run + sync log + notification
    run_stats = {
        "new_tasks": len(inbox_ids),
        "transitions": len(transitions),
        "merged": 0,
        "skipped": 0,
    }
    if closed_ids:
        run_stats["obsidian_closed"] = closed_ids
    if inbox_ids:
        run_stats["inbox_imported"] = inbox_ids
    log_run(run_stats)

    if vault_path:
        run_log = load_run_log()
        sync_md = render_sync_log(run_log["runs"])
        write_sync_log(sync_md, vault_path)

    summary = _build_change_summary(len(inbox_ids), len(closed_ids), len(transitions))
    if summary:
        _notify("TaskNemo", summary)

    changes = len(closed_ids) + len(transitions)
    if changes == 0:
        print("[refresh] No changes.")
    print("[refresh] Done.")


def cmd_watch():
    """Poll the dashboard file for changes and auto-refresh on edits.

    Watches the Obsidian dashboard file mtime every 1 second. When a change
    is detected, waits 2 seconds (debounce) then runs cmd_refresh().
    """
    config = load_config()
    vault_path = config.get("vault_path", "")
    dash_file = config.get("dashboard_filename", "TaskNemo.md")
    if not vault_path:
        print("[watch] No vault_path configured.")
        return
    dashboard_path = os.path.join(vault_path, dash_file)
    if not os.path.exists(dashboard_path):
        print(f"[watch] Dashboard not found: {dashboard_path}")
        return

    print(f"[watch] Watching {dashboard_path} for changes (Ctrl+C to stop)...")
    last_mtime = os.path.getmtime(dashboard_path)
    try:
        while True:
            time.sleep(1)
            try:
                current_mtime = os.path.getmtime(dashboard_path)
            except OSError:
                continue
            if current_mtime != last_mtime:
                print("[watch] Change detected, waiting 2s...")
                time.sleep(2)
                cmd_refresh()
                # Re-read mtime after refresh (our own write updates it)
                last_mtime = os.path.getmtime(dashboard_path)
    except KeyboardInterrupt:
        print("\n[watch] Stopped.")


def main():
    if len(sys.argv) < 2:
        cmd_sync_info()
        return

    command = sys.argv[1].lower()

    try:
        if command == "init":
            force = "--force" in sys.argv[2:]
            vault_path = None
            for i, arg in enumerate(sys.argv[2:], 2):
                if arg == "--vault-path" and i + 1 < len(sys.argv):
                    vault_path = sys.argv[i + 1]
            cmd_init(force=force, vault_path=vault_path)
        elif command == "sync":
            cmd_sync_info()
        elif command == "status":
            cmd_status()
        elif command == "list":
            cmd_list()
        elif command == "close" and len(sys.argv) >= 3:
            cmd_close(sys.argv[2].upper())
        elif command == "pin" and len(sys.argv) >= 3:
            cmd_pin(sys.argv[2].upper())
        elif command == "unpin" and len(sys.argv) >= 3:
            cmd_unpin(sys.argv[2].upper())
        elif command == "check":
            cmd_check()
        elif command == "migrate":
            cmd_migrate()
        elif command == "upgrade":
            cmd_upgrade()
        elif command == "refresh":
            cmd_refresh()
        elif command == "watch":
            cmd_watch()
        elif command == "add":
            import argparse
            parser = argparse.ArgumentParser(prog=f"{sys.argv[0]} add", description="Manually add a task")
            parser.add_argument("title", help="Task title")
            parser.add_argument("--sender", "-s", default="me", help="Who assigned/requested this task")
            parser.add_argument("--due", "-d", default=None, dest="due_hint", help="Due date hint (e.g. 'next Friday')")
            parser.add_argument("--desc", default=None, dest="description", help="Task description")
            parser.add_argument("--direction", default="inbound", choices=["inbound", "outbound"], help="Task direction")
            parser.add_argument("--source", default="manual", help="Task source label")
            args = parser.parse_args(sys.argv[2:])
            cmd_add(args.title, sender=args.sender, source=args.source, direction=args.direction,
                    due_hint=args.due_hint, description=args.description)
        else:
            print(f"Usage: python {sys.argv[0]} [init|sync|status|list|close|pin|unpin TASK-ID|check|migrate|upgrade|refresh|watch|add]")
    except FileNotFoundError as e:
        if "data" in str(e).replace("\\", "/"):
            print(f"Data file not found: {e}")
            print("Run 'python task_dashboard.py init' to set up.")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
