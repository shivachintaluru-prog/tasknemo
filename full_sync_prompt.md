Run a full TaskNemo sync. Follow the pipeline in SKILL.md exactly:

1. `sync_prepare()` — get context, queries, read back Obsidian completions
2. Run ALL WorkIQ queries from `ctx["all_queries"]` — **sent_items first**, then the rest in parallel
3. Extract structured items from each WorkIQ response using the Item Schema in SKILL.md
4. For any sender NOT in `config["stakeholders"]`, query WorkIQ to find out who they are (title, role, relationship) and add them with an appropriate weight. Save config.
5. `process_source_items()` for each source, then `add_task()` for each `to_create` item
6. `build_completion_signals()` from sent_items evidence matched to open tasks
7. `run_transitions()` — state machine + rescore
8. `finalize_sync()` — render dashboard + alerts to Obsidian vault

Be thorough with transcript extraction — transcripts are the richest source. Extract BOTH directions (inbound + outbound). Mark items as `already_done: True` if sent_items show they're handled.
