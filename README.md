# TaskNemo

AI-powered task tracker that auto-syncs from Teams, Email, and Calendar via Claude Code. Web dashboard at `localhost:8511`.

## Quick Start

```bash
git clone https://github.com/shivachintaluru-prog/tasknemo.git && cd tasknemo
pip install -r requirements.txt
python -m tasknemo.cli init
python -m tasknemo.cli serve
```

Open [http://localhost:8511](http://localhost:8511) in your browser.

## Prerequisites

- Python 3.10+
- Claude Code (for automated sync via Teams, Mail, and Calendar MCP tools)

## How It Works

Claude Code orchestrates the sync pipeline: queries Teams chats, emails, and calendar transcripts via MCP tools, extracts action items, and feeds them through deterministic Python functions for dedup, scoring, state transitions, and task lifecycle management. Everything is served through a web dashboard.

### Sync Pipeline

1. **Discovery** -- Query Teams chats, emails, calendar events, and sent items
2. **Extraction** -- Extract action items, commitments, and completion evidence
3. **Processing** -- Dedup against existing tasks, merge cross-source signals
4. **Transitions** -- Auto-close stale items, detect completions, update states
5. **Finalize** -- Log the run, send desktop notification

Run a sync by telling Claude Code: `run full sync and restart the server`

## Web Dashboard

Start the server:

```bash
python -m tasknemo.cli serve
```

The dashboard is available at `http://localhost:8511` with API endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/dashboard` | Full dashboard data (JSON) |
| `GET /api/tasks` | All tasks with filtering |
| `PATCH /api/tasks/{id}` | Update a task |
| `GET /api/analytics` | Response time and escalation analytics |
| `GET /api/sync/status` | Last sync time and health |
| `POST /api/sync/refresh` | Trigger a lightweight refresh |
| `GET /api/config` | Current configuration |
| `GET /api/export/markdown` | Dashboard as markdown |

## CLI Commands

| Command | Description |
|---|---|
| `init` | First-time setup (creates data files, prompts for sync frequency) |
| `serve` | Start the web dashboard (default: `localhost:8511`) |
| `tray` | Start with system tray icon |
| `sync` | Print sync pipeline queries and instructions |
| `status` | Task counts by state |
| `list` | Active tasks sorted by priority score |
| `check` | Quick status check (no external queries) |
| `refresh` | Run state transitions and re-score (no external queries) |
| `close TASK-ID` | Manually close a task |
| `pin TASK-ID` | Pin a task (+20 score boost) |
| `unpin TASK-ID` | Unpin a task |
| `add "title"` | Manually add a task (`--sender`, `--due`, `--desc`, `--priority`) |
| `find "query"` | Search tasks (`--sender`, `--topic`) |

All commands: `python -m tasknemo.cli <command>`

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
- `manager` (7-8) -- your direct manager
- `skip` (9) -- skip-level manager
- `peer` (3) -- teammates
- `partner` (5) -- cross-team partners

Higher weight = higher priority score for tasks from that person.

## Data Files

| File | Purpose |
|---|---|
| `data/config.json` | Stakeholder weights, sync frequency, query settings |
| `data/config.template.json` | Sanitized config template (checked in) |
| `data/tasks.json` | Task store (source of truth) |
| `data/run_log.json` | Audit trail per pipeline run |
| `data/analytics.json` | Response time and escalation analytics |

All data files except the template are gitignored.

## Running Tests

```bash
python -m pytest tests/ -v
```
