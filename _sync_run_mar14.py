"""Full sync script for March 14, 2026 — extracted from WorkIQ raw content."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_dashboard import (
    sync_prepare, process_source_items, build_completion_signals,
    run_transitions, finalize_sync, add_task, load_config, save_config,
    load_tasks, score_all_tasks
)

def prep_item(item):
    extra = item.get("extra", {})
    return {
        "sender": item.get("sender", ""),
        "title": item.get("title", ""),
        "teams_link": item.get("link", ""),
        "link": item.get("link", ""),
        "source": extra.get("source", "teams"),
        "direction": item.get("direction", "inbound"),
        "signal_type": item.get("signal_type", ""),
        "already_done": item.get("already_done", False),
        "description": extra.get("description", ""),
        "due_hint": extra.get("due_hint", ""),
        "source_context": extra.get("source_context", ""),
        "extra": extra,
    }

# ============================================================
# Step 0: sync_prepare
# ============================================================
ctx = sync_prepare()
config = ctx["config"]
print(f"Since: {ctx['since_date']} ({ctx['since_date_iso']})")
print(f"Open tasks: {len(ctx['open_tasks'])}")

# ============================================================
# TEAMS CHAT ITEMS (from Phase 2 detail queries)
# ============================================================
teams_items = [
    {
        "sender": "Tiffany Barnes",
        "title": "Update CCH feature ID 100782: change PM owner, PMM to Yana Terukhova, update release dates",
        "link": "https://teams.microsoft.com/l/message/19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces/1773289027805?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Tiffany: update voice notes in CCH (feature ID 100782) - change PM owner, change PMM from Tranissa to Yana Terukhova, update release details. Far off dates, report reviewed by marketing and eng LT.",
            "due_hint": "today",
            "extracted_date": "2026-03-12",
        },
    },
    {
        "sender": "Tiffany Barnes",
        "title": "Answer Voice Notes product questions for biz planning (storage, transcripts, launch rationale)",
        "link": "https://teams.microsoft.com/l/message/19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces/1773289027805?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Tiffany: answer product questions today - where are audio recordings uploaded, storage count, transcript format, why launch given Teams Copilot exists. Needed for biz planning.",
            "due_hint": "today",
            "extracted_date": "2026-03-13",
        },
    },
    {
        "sender": "Bharath Tumu",
        "title": "Compile list of AI-first PM session items for show-and-tell demo",
        "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773388970728?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Bharath: demo all AI work - collecting metrics etc. Give list of items for show and tell. Sent proposed list, awaiting confirmation to add to agenda.",
            "extracted_date": "2026-03-13",
        },
    },
    {
        "sender": "Jeet Patel",
        "title": "Reschedule AI PM call to second half or move 15 min",
        "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_c96c676f-c814-4c5c-af06-ef2ed22760e7@unq.gbl.spaces/1773372440635?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Jeet: move AI PM call to second half or at least 15 min, has Juhee review till 11:45.",
            "extracted_date": "2026-03-13",
        },
    },
    {
        "sender": "Ron Pessner",
        "title": "Clarify Voice Notes vs Notebooks live notes alignment and overlap",
        "link": "https://teams.microsoft.com/l/message/19:969cea310d36485398a4a6de5b7003bc@thread.v2/1773265787523?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Ron Pessner (CVP): Vishu shared NB team work on capturing notes, seems similar to voice notes - is there awareness and alignment? Bharath will circle back after talking to Anand.",
            "extracted_date": "2026-03-12",
        },
    },
    {
        "sender": "Ishneet Grover",
        "title": "Prepare Design LT pitch for Voice Notes approach (pushback on current approach)",
        "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773247741903?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Ishneet: need to prepare pitch for Design LT, lot of pushback on current Voice Notes approach.",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Pankesh Kumar",
        "title": "Meet with Rajan on CarPlay investigation before Apple meeting",
        "link": "https://teams.microsoft.com/l/message/19:0fc74a5ac3e2414789730a5d193eec6f@thread.v2/1773385121960?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": True,  # Already met and discussed
        "extra": {
            "source": "teams",
            "description": "Pankesh: Meet Rajan (Carplay lead). Already discussed: real-time voice not supported until Apple provides support. Shiva cautioned against unsupported audio type.",
            "extracted_date": "2026-03-13",
        },
    },
    # Outbound items (waiting on others)
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Bharath confirmation on show-and-tell agenda items",
        "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773388970728?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Asked Bharath: Should I add these to the Show & tell agenda? No response yet.",
            "extracted_date": "2026-03-13",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Ishneet on Workspaces/Bebop POC for Voice Notes alignment",
        "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773371308911?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Asked Ishneet: Who is POC for Workspaces in Bebop? Notebook team working on voice notes-like feature, need alignment.",
            "extracted_date": "2026-03-13",
        },
    },
    # BoA escalation resolution signal
    {
        "sender": "Joe Gallagher",
        "title": "Bank of America dictate escalation - policy fix confirmed",
        "link": "https://teams.microsoft.com/l/message/19:d14245c03ef241c2a4876b85452ac6b6@thread.v2/1773393291096?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "completion",
        "already_done": True,
        "extra": {
            "source": "teams",
            "description": "BoA confirmed policy fix works in QA. Tenant ID obtained. Customer approved ticket closure.",
            "extracted_date": "2026-03-13",
            "evidence": "Customer confirmed policy behavior fixed in QA, approved closure of support ticket.",
        },
    },
    # Voice Notes metrics (I drove investigation)
    {
        "sender": "Shiva Chintaluru",
        "title": "Voice Notes metrics telemetry accuracy investigation",
        "link": "",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Challenged Voice Notes metrics accuracy (250 taps, 128 recordings, 11 uploads). Demanded unsampled click-level telemetry. Shared ADX dashboards. Susheel investigating upload errors.",
            "extracted_date": "2026-03-11",
        },
    },
    # WebRTC blocker tracking
    {
        "sender": "Shiva Chintaluru",
        "title": "Track WebRTC echo and noise suppression as MSIT/DF blockers",
        "link": "https://teams.microsoft.com/l/message/19:8620ef7b2633423ab3496789f4787134@thread.v2/1773297084177?context=%7B%22contextType%22:%22chat%22%7D",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "teams",
            "description": "Flagged WebRTC echo and noise suppression as MSIT/DF/GA blockers. Known MSIT-blocking bug prevents consistent Noise Suppression model enablement. Pushed for unified tracking query.",
            "extracted_date": "2026-03-12",
        },
    },
]

# ============================================================
# TRANSCRIPT ITEMS (Voice Notes Team Sync + Juhee Review Prep)
# ============================================================
transcript_items = [
    # Inbound (I committed to)
    {
        "sender": "Shiva Chintaluru",
        "title": "Update Voice Notes team sync invitee list - remove older people",
        "link": "",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Pankesh requested cleanup of invitee list.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Respond to Voice SDK PM with top issues/asks by Monday March 16",
        "link": "",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Consolidate top issues and respond to Voice SDK PM owner by coming Monday.",
            "meeting_title": "Voice Notes Team Sync",
            "due_hint": "Monday March 16",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Share Voice Notes review slides with Ishneet and broader group",
        "link": "",
        "direction": "inbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Juhee Review Prep Mar 11: Share slides with Ishneet and group for awareness.",
            "meeting_title": "Juhee Review Prep",
            "extracted_date": "2026-03-11",
        },
    },
    # Outbound (others committed to)
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Pankesh to provide overall Voice Notes timeline by Friday EOD",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Pankesh committed to provide date/timeline for new stack + UX by Friday EOD.",
            "meeting_title": "Voice Notes Team Sync",
            "due_hint": "Friday EOD March 14",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Pankesh to implement open-transcript-in-web code changes",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Pankesh committed to web code changes for opening transcript file in web.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Sakshi to check Create/My Creations L2 status on Android",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Sakshi to verify if voice notes is L1 or L2 from Create/My Creations on Android.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Rajan to share iOS CMM ID status with Yingping Wu",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Rajan to share iOS CMM ID details with Yingping Wu to confirm missing steps.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Sakshi to share APK for audio format testing + results",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Sakshi to share APK for audio format/perf testing and investigation results.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Rajan to assess chunk upload pipeline reliability",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Rajan to check reliability of chunk upload pipeline via telemetry.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
    {
        "sender": "Shiva Chintaluru",
        "title": "Waiting: Ghanim to implement multi-window on OCM side",
        "link": "",
        "direction": "outbound",
        "signal_type": "",
        "already_done": False,
        "extra": {
            "source": "transcript",
            "description": "From Voice Notes Team Sync Mar 11: Ghanim committed to implementing multi-window on OCM side.",
            "meeting_title": "Voice Notes Team Sync",
            "extracted_date": "2026-03-11",
        },
    },
]

# ============================================================
# Completion evidence from sent items
# ============================================================
completion_evidence = [
    {"sender": "Shiva Chintaluru", "topic": "Bank of America dictate escalation", "thread_id": "", "evidence": "BoA confirmed policy fix works in QA. Tenant ID obtained. Customer approved ticket closure. PR 4787392 shared with exec visibility."},
    {"sender": "Shiva Chintaluru", "topic": "Voice Notes metrics telemetry", "thread_id": "", "evidence": "Challenged accuracy, demanded unsampled click-level telemetry. Shared ADX dashboards and Kusto queries. Susheel investigating upload errors."},
    {"sender": "Shiva Chintaluru", "topic": "WebRTC echo noise suppression", "thread_id": "", "evidence": "Flagged as MSIT/DF blockers. Asked for unified tracking query. Kanishk aligned on filing blockers."},
    {"sender": "Shiva Chintaluru", "topic": "Voice Notes entry point positioning deck", "thread_id": "", "evidence": "Shared positioning as primary entry point under + menu. Shared deck slide #33 and Figma. Plan to review in product review forum."},
    {"sender": "Shiva Chintaluru", "topic": "CarPlay audio type investigation", "thread_id": "", "evidence": "Met with Pankesh and Rajan. Cautioned against unsupported audio type. Apple dependency identified."},
    {"sender": "Shiva Chintaluru", "topic": "Juhee review prep alignment", "thread_id": "", "evidence": "Met with Arjun. Agreed on presentation order. Discovery first, then experience."},
    {"sender": "Shiva Chintaluru", "topic": "docking station Bharath", "thread_id": "", "evidence": "Checked desk. Only Hyper one, no HP dock. Replied to Bharath."},
    {"sender": "Shiva Chintaluru", "topic": "VoiceNotes intro Notebooks team", "thread_id": "", "evidence": "Organized VoiceNotes Intro meeting with Bharath, Anand, Mohit. Discussed transcription SDK, Augloop workflow."},
    {"sender": "Shiva Chintaluru", "topic": "CCH feature update voice notes", "thread_id": "", "evidence": "Tried to access CCH but could not edit - Shikha on maternity leave. Tiffany added name, now need to update dates."},
]

# ============================================================
# Process through pipeline
# ============================================================
all_new = []
all_signals = []
source_counts = {}

for source_name, items in [("teams", teams_items), ("transcript", transcript_items)]:
    prepped = [prep_item(i) for i in items]
    result = process_source_items(source_name, prepped, ctx)
    source_counts[source_name] = len(items)
    for item in result["to_create"]:
        tid = add_task(item, config)
        all_new.append(tid)
        print(f"  + {tid}: {item.get('title', '')[:80]}")
    if result.get("merged_ids"):
        print(f"  ~ {source_name}: merged into {result['merged_ids']}")
    if result["skipped"]:
        print(f"  - {source_name}: skipped {result['skipped']} items")
    all_signals.extend(result.get("signals", []))

source_counts["email"] = 0
source_counts["calendar_transcripts"] = 5
source_counts["doc_mentions"] = 0
ctx["run_stats"]["source_counts"] = source_counts

print(f"\nSource counts: {json.dumps(source_counts)}")
print(f"New tasks created: {len(all_new)}")
if source_counts["email"] == 0:
    print("FLAG: email returned 0 items (no human emails since Mar 11)")
if source_counts["doc_mentions"] == 0:
    print("FLAG: doc_mentions returned 0 items (API limitation on comment extraction)")

# ============================================================
# Build completion signals
# ============================================================
open_tasks = [t for t in load_tasks()["tasks"] if t.get("state") != "closed"]
comp_signals = build_completion_signals(completion_evidence, open_tasks)
print(f"\nCompletion signals matched: {len(comp_signals)}")
for s in comp_signals:
    print(f"  {s['task_id']}: {s['signal'][:80]}")

# ============================================================
# Collect all signals for transitions
# ============================================================
for cs in comp_signals:
    all_signals.append({
        "sender": "",
        "topic": cs.get("signal", ""),
        "thread_id": "",
        "signal_type": "completion",
        "signal": cs["signal"],
        "teams_link": "",
    })

# ============================================================
# Run transitions
# ============================================================
print(f"\nRunning transitions (signals: {len(all_signals)})...")
trans_result = run_transitions(all_signals, ctx)
transitions = trans_result.get("transitions", [])
print(f"Transitions: {len(transitions)}")
for t in transitions:
    print(f"  {t[0]}: {t[1]} -> {t[2]} ({t[3][:60]})")

# ============================================================
# Finalize
# ============================================================
ctx["run_stats"]["new_tasks"] = len(all_new)
ctx["run_stats"]["sources_queried"] = ["teams", "email", "calendar", "sent_items", "transcripts", "doc_mentions"]
ctx["run_stats"]["validation_additions"] = 0  # Will update after validation
path = finalize_sync(ctx["run_stats"], ctx,
                     transitions=transitions,
                     new_tasks=[t for t in load_tasks()["tasks"] if t["id"] in all_new])

print(f"\nDashboard: {path}")
print(f"Stats: {json.dumps(ctx['run_stats'], indent=2)}")
print("Sync complete (pre-validation).")
