---
name: sync
description: Run full TaskNemo sync — fetch Teams, Email, Calendar via MCP, extract tasks, process pipeline
argument-hint: "[--full]"
---

# TaskNemo Full Sync

Run the complete task sync pipeline. This fetches data from Teams, Email, and Calendar via MCP tools, extracts action items, deduplicates against existing tasks, runs state transitions, and updates the task store.

Arguments: $ARGUMENTS
- `--full` — use a wider lookback window (7 days instead of default overlap)

## Step 1: Prepare Sync Context

```bash
cd C:/Users/shchint/tasknemo
python -c "
from tasknemo.pipeline import sync_prepare
import json
ctx = sync_prepare()
print(json.dumps({
    'since_date': ctx['since_date'],
    'since_date_iso': ctx['since_date_iso'],
    'open_task_count': len(ctx['open_tasks']),
    'last_run': ctx['config'].get('last_run'),
}, indent=2))
"
```

Note the `since_date_iso` (e.g. `2026-04-05`) — use it for all MCP queries below.

## Step 2: Phase 1 Discovery (run ALL in parallel)

Call these MCP tools **simultaneously**:

### 2a. Teams Chats
Call `mcp__teams__ListChats` with `userUpns: []` and `top: 50`.
Filter the results to chats with `lastUpdatedDateTime` >= since_date_iso.

### 2b. Received Emails
Call `mcp__mail__SearchMessagesQueryParameters` with:
```
?$filter=receivedDateTime ge {since_date_iso}T00:00:00Z&$orderby=receivedDateTime desc&$top=50&$select=id,subject,from,receivedDateTime,isRead,hasAttachments,webLink,conversationId
```

### 2c. Sent Emails
Call `mcp__mail__SearchMessagesQueryParameters` with:
```
?$filter=sentDateTime ge {since_date_iso}T00:00:00Z and from/emailAddress/address eq 'shchint@microsoft.com'&$orderby=sentDateTime desc&$top=50&$select=id,subject,toRecipients,sentDateTime,webLink,conversationId
```

### 2d. Calendar Events
Call `mcp__calendar__ListCalendarView` with:
- `startDateTime`: `{since_date_iso}T00:00:00`
- `endDateTime`: today + 1 day in ISO format

### 2e. Actionable Email Search
Call `mcp__mail__SearchMessages` with:
```
action items and requests sent to me since {since_date} that need my response or action
```

## Step 3: Phase 2 Detail — Read Key Chat Messages

For the **top 10 most recently active** Teams chats from Step 2a, call `mcp__teams__ListChatMessages` with each chat's `id`. Focus on chats with topics related to work (skip social/birthday chats).

## Step 4: Extract Action Items

From ALL gathered data, extract items in this exact schema. Be thorough — extract BOTH inbound (assigned to user) and outbound (waiting on others):

```python
{
    "sender": "Person Name",           # who created/assigned the task
    "title": "Brief action item",       # concise task title
    "link": "https://...",              # Teams/Outlook link to source
    "direction": "inbound",             # "inbound" = assigned to me, "outbound" = waiting on others
    "signal_type": "",                  # leave empty unless completion evidence
    "already_done": False,              # True if sent items show this is completed
    "source": "teams",                  # "teams", "email", or "calendar"
    "extra": {
        "source": "teams",             # same as above
        "source_context": "Chat: ...", # e.g. "Chat: Voice Leads" or "Email: Re: Subject"
        "extracted_date": "2026-04-06", # ISO date when the item was created
        "thread_id": "19:abc@thread.v2", # Teams thread ID if available
        "due_hint": "Friday"            # deadline hint if mentioned (optional)
    }
}
```

### Extraction Rules
- **Teams chats**: Extract asks, action items, @mentions requesting action. Skip casual messages.
- **Emails**: Focus on direct asks, approvals needed, compliance deadlines. Skip newsletters, external spam, social emails.
- **Calendar/Transcripts**: Extract commitments made in meetings — both "I will do X" (inbound) and "Person will do X" (outbound/waiting).
- **Sent items**: Use as completion evidence — if user already replied/acted on something, mark `already_done: True` or create completion signals.

### Completion Evidence
Build a separate list of completion items from sent emails and outbound messages:
```python
{
    "sender": "Shiva Chintaluru",
    "topic": "Topic that was resolved",
    "thread_id": "",  # if known
    "evidence": "Replied to X on date Y"
}
```

## Step 5: Process Through Pipeline

Save extracted items to Python lists and run the pipeline:

```python
cd C:/Users/shchint/tasknemo
python -c "
import json
from tasknemo.pipeline import (
    sync_prepare, process_source_items, build_completion_signals,
    run_transitions, finalize_sync,
)
from tasknemo.tasks import add_task

ctx = sync_prepare()
config = ctx['config']
run_stats = ctx['run_stats']

# Group items by source
teams_items = [...]      # paste extracted Teams items
email_items = [...]      # paste extracted Email items
calendar_items = [...]   # paste extracted Calendar items (inbound)
outbound_items = [...]   # paste extracted outbound/waiting items
completion_items = [...]  # paste completion evidence

all_new_tasks = []
all_signals = []

for source_name, items in [('teams', teams_items), ('email', email_items), ('calendar', calendar_items), ('calendar', outbound_items)]:
    result = process_source_items(source_name, items, ctx)
    run_stats['source_counts'][source_name] = run_stats['source_counts'].get(source_name, 0) + len(items)
    for task_item in result['to_create']:
        task_id = add_task(task_item, config)
        all_new_tasks.append({'id': task_id, 'title': task_item['title'], 'sender': task_item.get('sender', '')})
        run_stats['new_tasks'] += 1
    all_signals.extend(result['signals'])
    print(f'{source_name}: {len(items)} items -> {len(result[\"to_create\"])} new, {len(result[\"merged_ids\"])} merged, {result[\"skipped\"]} skipped')

comp_signals = build_completion_signals(completion_items, ctx['open_tasks'])
all_signals.extend(comp_signals)
print(f'Completion signals: {len(comp_signals)} matched')

trans_result = run_transitions(all_signals, ctx)
transitions = trans_result['transitions']
run_stats = trans_result['run_stats']
run_stats['validation_additions'] = 0
print(f'Transitions: {len(transitions)}')

finalize_sync(run_stats, ctx, transitions=transitions, new_tasks=all_new_tasks)

print()
print('=== SYNC COMPLETE ===')
print(f'New: {run_stats[\"new_tasks\"]} | Merged: {run_stats[\"merged\"]} | Skipped: {run_stats[\"skipped\"]} | Transitions: {run_stats[\"transitions\"]}')
print(f'Sources: {json.dumps(run_stats[\"source_counts\"])}')
for t in all_new_tasks:
    print(f'  {t[\"id\"]}: {t[\"title\"]}')
"
```

## Step 6: Restart Web Server

Check if the server is running and restart it:
```bash
curl -s http://127.0.0.1:8511/api/sync/status 2>/dev/null && echo "Server running" || (cd C:/Users/shchint/tasknemo && python -m tasknemo.cli serve &)
```

## Step 7: Print Summary

Print a clear summary:
- How many new tasks created (by source)
- How many merged with existing
- How many state transitions
- Key new tasks with IDs
- Server health status
