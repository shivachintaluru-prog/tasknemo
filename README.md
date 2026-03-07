# TaskNemo

Automated pipeline: extract tasks from Teams, email, calendar, and transcripts (via WorkIQ MCP), manage their lifecycle, score priorities, and render a markdown dashboard for Obsidian.

## Quick Start

```bash
git clone <repo-url> && cd tasknemo
python task_dashboard.py init
python task_dashboard.py check
```

## Prerequisites

- Python 3.10+
- Windows 11 (for scheduled sync and toast notifications)
- Obsidian (optional, for viewing the rendered dashboard)
- Claude Code + WorkIQ MCP (for full automated sync)

Optional dependency (desktop toast notifications):

```bash
pip install -r requirements.txt
```

## Configure Stakeholders

After `init`, edit `data/config.json` to add your stakeholders:

```json
"stakeholders": {
  "jane doe": {
    "name": "Jane Doe",
    "title": "PM Manager",
    "role": "manager",
    "weight": 8
  }
}
```

Roles and typical weights:
- `manager` (7-8) — your direct manager
- `skip` (9) — skip-level manager
- `peer` (3) — teammates
- `partner` (5) — cross-team partners

Higher weight = higher priority score for tasks from that person.

## Modes

### Standalone (manual)

Use the CLI to add, close, and manage tasks. Run `refresh` to re-score and re-render.

### Full Sync (Claude Code + WorkIQ)

Claude Code orchestrates the pipeline: queries WorkIQ for new messages across Teams, email, calendar, and transcripts, then feeds them through the deterministic Python functions for dedup, scoring, state transitions, and rendering.

Run manually: `./full_sync.ps1`
Schedule: `./setup_full_sync_scheduler.ps1`

## CLI Commands

| Command | Description |
|---|---|
| `python task_dashboard.py init` | Set up data files and config (first-time setup) |
| `python task_dashboard.py sync` | Print pipeline queries + instructions |
| `python task_dashboard.py status` | Task counts by state |
| `python task_dashboard.py list` | Active tasks sorted by score |
| `python task_dashboard.py close TASK-ID` | Manually close a task |
| `python task_dashboard.py pin TASK-ID` | Pin a task (+20 score boost) |
| `python task_dashboard.py unpin TASK-ID` | Unpin a task |
| `python task_dashboard.py check` | Quick status check (no WorkIQ calls) |
| `python task_dashboard.py migrate` | Add new fields to existing tasks |
| `python task_dashboard.py refresh` | Lightweight refresh — close checked tasks, run state machine, re-render |
| `python task_dashboard.py watch` | Poll dashboard file for changes, auto-refresh on edit |
| `python task_dashboard.py add "title"` | Manually add a task (--sender, --due, --desc, --direction) |

## Manual Task Creation

### CLI

```bash
python task_dashboard.py add "Review proposal" --sender "Jane Doe"
python task_dashboard.py add "Book venue" --due "next Friday"
python task_dashboard.py add "Follow up with Alex" --desc "AI roadmap discussion"
```

### Claude Code

Tell Claude: "add a task to follow up with Jane on the proposal"

### Obsidian Inbox

Write tasks in `Task Inbox.md` in your vault — they're imported on every `refresh` or `watch` cycle.

```markdown
# Task Inbox
Add tasks below — they'll be imported on next refresh.

- Review the proposal
- [ ] Book team offsite venue
- Follow up with Jane on AI roadmap --sender Jane --due Friday
```

## Scheduling (optional)

```powershell
# Lightweight refresh every 30 min (weekdays, 8 AM - 6 PM)
.\setup_scheduler.ps1

# Full sync via Claude Code every 2 hours (weekdays, 9 AM - 7 PM)
.\setup_full_sync_scheduler.ps1
```

## Architecture

Claude Code is the orchestrator. The Python script (`task_dashboard.py`) provides deterministic functions: dedup, scoring, state transitions, and markdown rendering. Claude provides natural language understanding and WorkIQ MCP access for querying Teams, email, and calendar.

## Data Files

| File | Purpose |
|---|---|
| `data/config.json` | Stakeholder weights, vault path, query settings |
| `data/config.template.json` | Sanitized config template (checked in) |
| `data/tasks.json` | Task store (source of truth) |
| `data/run_log.json` | Audit trail per pipeline run |
| `data/analytics.json` | Response time and escalation analytics |

All data files except the template are gitignored.

## Running Tests

```bash
python -m pytest tests/ -v
```
