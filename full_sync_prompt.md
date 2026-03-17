Run a full TaskNemo sync. Follow the pipeline in SKILL.md exactly:

1. `sync_prepare()` — get context, queries, read back Obsidian completions, import inbox tasks
2. **Phase 1 — Discovery:** Run all `ctx["all_queries"]["phase1"]` queries in parallel via `ask_work_iq`. Extract structured discovery items from each response (chat names with type/participants, email subjects with sender/date, sent items with recipient/subject/reply status, calendar events with transcript flag).
3. Extract discovery items from each Phase 1 response into structured lists.
4. **Phase 2 — Sent items detail FIRST:** Call `build_detail_queries("sent_items", items, since_date, config)` and run those queries. Extract completion evidence — what you already did, who replied, etc.
5. **Phase 2 — Chats + email detail:** Call `build_detail_queries("chats", items, ...)` and `build_detail_queries("email", items, ...)`. Run detail queries. Skip non-actionable items (newsletters, bot messages, large channel broadcasts).
   **IMPORTANT: WorkIQ often returns full chat history regardless of the date filter in the query. You MUST check each message's timestamp and only extract items from messages sent on or after the since_date. Set `extra.extracted_date` for each item. Discard anything older.**
6. **Already-targeted queries** (run as-is): `transcript_discovery` + `transcript_extraction`, `doc_mentions`
7. Deduplicate across all sources — same task can appear in chat, email, and transcript
8. For any sender NOT in `config["stakeholders"]`, query WorkIQ to find out who they are (title, role, relationship) and add them with an appropriate weight. Save config.
9. `process_source_items()` for each source, then `add_task()` for each `to_create` item
10. **Phase 3 — Validation:** Run `ctx["all_queries"]["validation"]` via `ask_work_iq`. Compare WorkIQ's task list against extracted tasks. For any net-new items WorkIQ surfaces that weren't already captured, verify against raw data before creating. Do NOT blindly trust WorkIQ's interpretive summaries. Log additions in `run_stats["validation_additions"]`.
11. `build_completion_signals()` from sent_items evidence matched to open tasks
12. `run_transitions()` — state machine + rescore
13. `finalize_sync()` — render dashboard + alerts to Obsidian vault

Track `run_stats["source_counts"]` — record item counts per source after extraction. If any source returns 0 items when you expected data, flag it as a potential coverage gap.

Be thorough with transcript extraction — transcripts are the richest source. Extract BOTH directions (inbound + outbound). Mark items as `already_done: True` if sent_items show they're handled.

Every item MUST include `extra.source_context` — a short human-readable breadcrumb so users can find the original message:
- **Teams chat**: chat name or participant list, e.g. `"Chat: Arjun, Claire, Shiva"`
- **Email**: subject line, e.g. `"Email: Re: Voice Notes launch plan"`
- **Calendar/transcript**: meeting title, e.g. `"Meeting: Voice Notes Team Sync"`
- **Flagged email**: subject, e.g. `"Flagged: Privacy Fundamentals evaluation"`

CRITICAL: Raw content first, WorkIQ interpretation second. Every task must trace to explicit words in a message, not a WorkIQ narrative.
