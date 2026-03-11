# TaskNemo — Claude Code Skill

Extracts tasks from Teams, email, calendar, and transcripts (via WorkIQ MCP),
manages lifecycle with a state machine, scores priorities, and renders a
markdown dashboard for Obsidian.

---

## Pipeline Steps

### Step 0 — Prepare

```python
from task_dashboard import sync_prepare
ctx = sync_prepare()
# Returns: config, since_date, all_queries, open_tasks, pre_closed, run_stats
```

Reads back Obsidian completions, calculates the since-date (last_run minus
overlap_days), builds all WorkIQ queries, and loads open tasks.

### Step 1 — Run WorkIQ Queries (2-Phase)

**Phase 1 — Discovery:** Run all queries from `ctx["all_queries"]["phase1"]` in parallel.
These are lightweight enumeration queries. Extract structured discovery items from each
response (chat names, email subjects, etc.).

**Phase 2 — Detail:** For each source with discovery items, call:
```python
from task_dashboard import build_detail_queries
queries = build_detail_queries(source, items, ctx["since_date"], ctx["config"])
```
Run returned detail queries via `ask_work_iq`. Process **sent_items details FIRST** —
completion evidence prevents false-positive task creation.

**Optimization:** Skip detail queries for clearly non-actionable items (newsletters,
bot messages, large channel broadcasts).

**Already-targeted queries** (run as-is, no phase split):
- `transcript_discovery` + `transcript_extraction` — already 2-step
- `doc_mentions` — already targeted

**Phase 3 — Validation:** After all extraction and `process_source_items()` calls,
run `ctx["all_queries"]["validation"]` via `ask_work_iq`. Compare WorkIQ's task list
against already-extracted tasks. For any net-new items, verify against raw data
before creating. Log findings in `run_stats["validation_additions"]`.

**Legacy mode:** If `config["query_strategy"] == "single_phase"`, `all_queries`
returns the old flat structure — run all queries directly without phases.

### Step 2 — Process Source Items

```python
from task_dashboard import process_source_items, add_task
result = process_source_items(source, items, ctx)
for item in result["to_create"]:
    add_task(item, ctx["config"])
```

For each WorkIQ response, extract items matching the **Item Schema** below,
then call `process_source_items`. It deduplicates against existing tasks and
returns `to_create` (new) and `merged` (updated existing) lists.

### Step 3 — Build Completion Signals

```python
from task_dashboard import build_completion_signals
signals = build_completion_signals(completion_items, ctx["open_tasks"])
```

Match conversation/email completion evidence back to open tasks using
thread IDs and sender+topic fuzzy matching.

### Step 4 — Run Transitions

```python
from task_dashboard import run_transitions
result = run_transitions(signals, ctx)
# Returns: transitions (list of tuples), run_stats (updated)
```

Evaluates the state machine: stale → needs_followup, completion signal →
likely_done, likely_done age → closed, etc. Then rescores all tasks and
updates config.last_run.

### Step 5 — Finalize

```python
from task_dashboard import finalize_sync
path = finalize_sync(result["run_stats"], ctx,
                     transitions=result["transitions"],
                     new_tasks=new_task_list)
```

Renders the dashboard markdown, writes it to the Obsidian vault, writes
Task Alerts.md with deltas, and logs the run.

---

## Item Schema

Each item extracted from a WorkIQ response should be a dict with these keys:

```python
{
    "sender": "Person Name",         # who created/assigned the task
    "title": "Brief task summary",   # what needs to be done
    "link": "https://...",           # source URL (Teams/Outlook/Calendar)
    "direction": "inbound",          # "inbound" = someone asked me
                                     # "outbound" = I asked someone
    "signal_type": "",               # "completion" | "waiting" | "" (new task)
    "already_done": False,           # True if sent-items show it's handled
    "extra": {                       # optional additional context
        "due_hint": "EOD Friday",
        "description": "...",
        "source": "calendar",        # teams | email | calendar | transcript
        "thread_id": "19:abc@thread.v2",
        "extracted_date": "2026-03-10",  # date the message was sent (ISO format)
    }
}
```

---

## Judgment Rules

1. **Sent items first.** Always process sent_items before other sources.
   If sent items show you already handled something, mark `already_done: True`
   so `process_source_items` skips or closes it.

2. **Transcripts are the richest source.** Meeting transcripts often contain
   commitments that never appear in chat or email. Always scan all transcribed
   meetings and extract BOTH directions (what I committed to, what others
   committed to).

3. **Direction semantics.**
   - `"inbound"` — someone asked me to do something (I own the action)
   - `"outbound"` — I asked someone else (they own, I'm waiting)
   Outbound tasks land in the "Waiting on Others" dashboard section.

4. **Cross-source dedup.** The same task can surface in Teams chat, email,
   and a meeting transcript. `process_source_items` handles dedup by
   matching on sender + title similarity + thread ID. When a match is found,
   the existing task gets an alternate_links entry and a multi_source scoring
   boost.

5. **Completion evidence.** Look for keywords like "thanks", "done",
   "shipped", "approved" in conversation context. Match them back to open
   tasks via thread IDs first, then sender+topic fuzzy matching.

7. **Document mentions.** Notification emails with subjects like "X mentioned
   you in Y" contain the actual comment text in the body. Parse the email body
   for: who mentioned you, what they said (verbatim), which document, and any
   explicit ask. Also run a direct WorkIQ search for document @mentions.
   Extract tasks ONLY from explicit asks in the raw comment text. Both signals
   feed into `process_source_items()` as source `"doc_mentions"`.

8. **Date boundary enforcement.** WorkIQ often returns messages outside the
   requested time window (especially for group chats where it returns full
   history). When extracting items from Phase 2 detail responses:
   - Check each message's timestamp against `ctx["since_date"]`
   - **Skip** any message clearly older than the since_date window
   - Set `extra.extracted_date` to the message's date (ISO format, e.g., "2026-03-10")
   - If a message has no timestamp, use best judgment but err on the side of skipping
   - `process_source_items()` will also reject items with `extracted_date` before the window

9. **Unknown sender lookup.** When processing a task from someone NOT in
   `config["stakeholders"]`, query WorkIQ: *"Who is [Person Name]? What is
   their role, title, and reporting relationship to me?"* Based on the
   response, add them to stakeholders with an appropriate role and weight:
   - VP / skip-level → `"skip"`, weight 9
   - Direct manager → `"manager"`, weight 7–8
   - Cross-team partner / PM → `"partner"`, weight 5
   - Peer / IC → `"peer"`, weight 3
   - External / unknown → `"external"`, weight 1
   Save the updated config so future syncs score them correctly.
   This ensures new contacts are prioritized properly from their very first
   message — no manual config needed.

6. **State machine.** Tasks flow through:
   `open → waiting → needs_followup → likely_done → closed`
   - `closed` is terminal (no reopening)
   - `likely_done` auto-closes after 3 days with no contradiction
   - `needs_followup` auto-closes after 14 stale days

---

## CLI Commands

| Command | Description |
|---|---|
| `python task_dashboard.py init` | Set up data files and config (first-time setup) |
| `python task_dashboard.py upgrade` | Merge new config keys from template + migrate task schema |
| `python task_dashboard.py` | Print sync instructions (same as `sync`) |
| `python task_dashboard.py sync` | Print pipeline queries + instructions |
| `python task_dashboard.py status` | Task counts by state |
| `python task_dashboard.py list` | Active tasks sorted by score |
| `python task_dashboard.py close TASK-ID` | Manually close a task |
| `python task_dashboard.py pin TASK-ID` | Pin a task (+20 score boost) |
| `python task_dashboard.py unpin TASK-ID` | Unpin a task |
| `python task_dashboard.py check` | Quick status check (no WorkIQ calls) |
| `python task_dashboard.py migrate` | Add new fields to existing tasks |
| `python task_dashboard.py refresh` | Lightweight refresh — close checked tasks, run state machine, re-render |
| `python task_dashboard.py watch` | Poll dashboard file for changes, auto-refresh on edit (Ctrl+C to stop) |
| `python task_dashboard.py add "title"` | Manually add a task (--sender, --due, --desc, --direction) |

---

## Manual Task Creation

Three ways to add tasks outside the automated pipeline:

### 1. CLI

```bash
python task_dashboard.py add "Review Danny's proposal" --sender "Danny Xu"
python task_dashboard.py add "Book team offsite venue" --due "next Friday"
python task_dashboard.py add "Follow up with Juhee" --desc "AI roadmap discussion"
```

Options: `--sender`/`-s`, `--due`/`-d`, `--desc`, `--direction` (inbound/outbound), `--source`.

### 2. Claude Code

Tell Claude: "add a task to follow up with Danny on the proposal"

Claude calls `cmd_add()` directly — no CLI needed.

### 3. Obsidian Inbox

Write tasks in `Task Inbox.md` in your vault — they're imported on every `refresh` or `watch` cycle.

```markdown
# Task Inbox
Add tasks below — they'll be imported on next refresh.

- Review Danny's proposal
- [ ] Book team offsite venue
- Follow up with Juhee on AI roadmap --sender Juhee --due Friday
```

Inline flags `--sender Name` and `--due hint` are parsed and stripped from the title. After import, the file is cleared (header preserved).
