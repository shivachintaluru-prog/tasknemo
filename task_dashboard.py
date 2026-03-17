"""
TaskNemo — Task Extraction and Priority Dashboard

Re-export shim: all logic lives in tasknemo/ package.
This file re-exports every public symbol so that existing tests
and scripts (`from task_dashboard import ...`) continue to work.

When attributes are set on this module (e.g., monkeypatch in tests),
they are propagated to the originating sub-module so internal calls
see the patched version.
"""

import sys as _sys
import types as _types

import tasknemo.store as _store
import tasknemo.analytics as _analytics
import tasknemo.dedup as _dedup
import tasknemo.grouping as _grouping
import tasknemo.tasks as _tasks
import tasknemo.queries as _queries
import tasknemo.scoring as _scoring
import tasknemo.state_machine as _state_machine
import tasknemo.rendering as _rendering
import tasknemo.notifications as _notifications
import tasknemo.pipeline as _pipeline
import tasknemo.cli as _cli

# Store
from tasknemo.store import (
    SCRIPT_DIR, DATA_DIR, CONFIG_PATH, TASKS_PATH, RUN_LOG_PATH, ANALYTICS_PATH,
    _ANALYTICS_DEFAULT,
    load_json, save_json,
    load_config, save_config,
    load_tasks, save_tasks,
    load_run_log, save_run_log,
    load_analytics, save_analytics,
)

# Analytics
from tasknemo.analytics import (
    record_response_time, get_response_time_factor,
    record_mention, get_escalation_bonus,
    pin_task, unpin_task, get_pin_bonus,
)

# Dedup
from tasknemo.dedup import (
    STOP_WORDS,
    normalize_text, normalize_title_words,
    compute_dedup_hash, jaccard_similarity,
    fuzzy_match, is_duplicate,
    find_cross_source_match, merge_cross_source_signal,
    merge_duplicates,
)

# Grouping
from tasknemo.grouping import (
    extract_thread_id, build_search_fallback,
    suggest_groups, group_tasks, ungroup_task,
)

# Tasks
from tasknemo.tasks import (
    next_task_id, add_task, get_task, list_tasks, update_task,
)

# Queries
from tasknemo.queries import (
    calculate_since_date,
    build_workiq_queries, build_followup_queries, build_completion_query,
    build_email_queries, build_calendar_query, build_transcript_queries,
    build_sent_items_query, build_outbound_query,
    build_all_received_query, build_inbound_dms_query,
    build_key_contact_queries, build_doc_mentions_queries,
    build_discovery_queries, build_detail_queries, build_validation_query,
    _build_chats_detail_queries, _build_email_detail_queries,
    _build_sent_items_detail_queries,
    _build_all_queries_legacy, build_all_queries,
    build_flagged_emails_query, build_planner_query,
)

# Scoring
from tasknemo.scoring import (
    score_task, score_all_tasks, parse_due_hint,
)

# State machine
from tasknemo.state_machine import (
    VALID_STATES, VALID_TRANSITIONS,
    transition_task, match_conversation_to_tasks, evaluate_transitions,
)

# Rendering
from tasknemo.rendering import (
    TASK_TYPES,
    _format_age, _compute_idle_days, _is_due_within, _compute_confidence,
    classify_task_type, _generate_next_action,
    _shorten_meeting_title, _extract_container_key, _compute_focus_priority,
    _build_links_line,
    _render_task_item_v1, _render_task_item_v2, _render_task_item,
    _CHECKED_TASK_RE, sync_dashboard_completions,
    render_dashboard_v1, render_dashboard_v2, render_dashboard,
    write_dashboard,
    render_alerts, write_alerts,
    render_sync_log, write_sync_log,
)

# Notifications
from tasknemo.notifications import _notify, _build_change_summary

# Pipeline
from tasknemo.pipeline import (
    sync_prepare, process_source_items, build_completion_signals,
    run_transitions, finalize_sync, log_run,
)

# CLI
from tasknemo.cli import (
    cmd_status, cmd_list, cmd_close, cmd_check, cmd_sync_info,
    cmd_migrate, cmd_pin, cmd_unpin, cmd_add, cmd_find,
    cmd_init, cmd_upgrade, cmd_refresh, cmd_watch,
    cmd_serve, cmd_tray, cmd_install_tray,
    _deep_merge_defaults, _parse_inbox_tasks, sync_inbox,
    _INBOX_INLINE_FLAG_RE, _INBOX_TASK_RE,
    main,
)


# ---------------------------------------------------------------------------
# Attribute propagation: when tests do monkeypatch.setattr("task_dashboard.X", mock),
# propagate to the sub-module that originally defined X so internal calls see it.
# ---------------------------------------------------------------------------

_ATTR_TO_MODULE = {}

# Build the reverse map: attribute name -> list of sub-modules that define it
for _mod in [_store, _analytics, _dedup, _grouping, _tasks, _queries,
             _scoring, _state_machine, _rendering, _notifications,
             _pipeline, _cli]:
    for _name in dir(_mod):
        if not _name.startswith("__"):
            _ATTR_TO_MODULE.setdefault(_name, []).append(_mod)


class _ShimModule(_types.ModuleType):
    """Module that propagates attribute assignments to originating sub-modules."""

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        # Propagate to all sub-modules that define this attribute
        for mod in _ATTR_TO_MODULE.get(name, []):
            setattr(mod, name, value)


if __name__ != "__main__":
    _this = _sys.modules[__name__]
    _shim = _ShimModule(__name__)
    _shim.__dict__.update(vars(_this))
    _shim.__file__ = __file__
    _shim.__spec__ = globals().get("__spec__")
    _sys.modules[__name__] = _shim
else:
    main()
