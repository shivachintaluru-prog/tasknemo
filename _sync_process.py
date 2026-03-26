"""One-shot sync processing script — first sync from scratch, March 26 2026."""
import json
from tasknemo.pipeline import (
    sync_prepare, process_source_items, build_completion_signals,
    run_transitions, finalize_sync,
)
from tasknemo.tasks import add_task

ctx = sync_prepare()
config = ctx["config"]
run_stats = ctx["run_stats"]

print(f"Since: {ctx['since_date']} (ISO: {ctx['since_date_iso']}), Open tasks: {len(ctx['open_tasks'])}")

# === TEAMS CHATS ===
chat_items = [
    {"sender": "Mohit Anand", "title": "Answer EY voice questions: image gen policies, known voice issues, voice options, user limits",
     "link": "https://teams.microsoft.com/l/message/19:335ae6beb2f24acb9af2149def6ef7a2@thread.v2/1774521021079?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: EY Mobile deck", "extracted_date": "2026-03-26",
               "thread_id": "19:335ae6beb2f24acb9af2149def6ef7a2@thread.v2"}},
    {"sender": "Mohit Anand", "title": "Add slide with EY mobile voice answers to enterprise connect deck",
     "link": "https://teams.microsoft.com/l/message/19:335ae6beb2f24acb9af2149def6ef7a2@thread.v2/1774527024927?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: EY Mobile deck", "extracted_date": "2026-03-26",
               "thread_id": "19:335ae6beb2f24acb9af2149def6ef7a2@thread.v2"}},
    {"sender": "Subasini Annamalai", "title": "Share commute survey in voice notes group",
     "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1774426121061?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Rahuls PM Team", "extracted_date": "2026-03-25",
               "thread_id": "19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2"}},
    {"sender": "Lan Mi", "title": "Ensure voice notes match Bebop design style before WW flight in April",
     "link": "https://teams.microsoft.com/l/message/19:a94343bdb4b34dc88866f3bdcd595c7c@thread.v2/1774500525836?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Record as input to chat", "extracted_date": "2026-03-26",
               "thread_id": "19:a94343bdb4b34dc88866f3bdcd595c7c@thread.v2", "due_hint": "before April WW flight"}},
    {"sender": "Arjun Patel", "title": "Finalize entry point for record in +menu with PM alignment from Liu/Hao",
     "link": "https://teams.microsoft.com/l/message/19:a94343bdb4b34dc88866f3bdcd595c7c@thread.v2/1774413276165?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Record as input to chat", "extracted_date": "2026-03-25",
               "thread_id": "19:a94343bdb4b34dc88866f3bdcd595c7c@thread.v2"}},
    {"sender": "Arjun Patel", "title": "Start PM alignment conversation with Liu/Hao on voice notes as input modality",
     "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1774323082863?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice notes entry point", "extracted_date": "2026-03-24",
               "thread_id": "19:56497877df3948efbfd54a66bb58ec10@thread.v2"}},
    {"sender": "Kanishk Kunal", "title": "Provide projected MAU for Chat+Voice scenarios in June for capacity allocation",
     "link": "https://teams.microsoft.com/l/message/19:75530622eadf4a669e57741d90e9d5c6@thread.v2/1774344639536?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice Leads", "extracted_date": "2026-03-24",
               "thread_id": "19:75530622eadf4a669e57741d90e9d5c6@thread.v2"}},
    {"sender": "Shiva Chintaluru", "title": "Confirm PM alignment items: Camera+Images merge and Voice notes in +menu",
     "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1774499481605?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "outbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice notes entry point", "extracted_date": "2026-03-26",
               "thread_id": "19:56497877df3948efbfd54a66bb58ec10@thread.v2"}},
]

# === EMAIL ===
email_items = [
    {"sender": "Manoj Gupta", "title": "Review OCM functionality for Outlook and check Arindams M3CA docs",
     "link": "https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEMAABV3dgFhEhrT5Kqtsq4o0ilAAgb8wXYAAA%3d",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Re: Get up to speed | M3CA (Manoj Gupta)", "extracted_date": "2026-03-26"}},
    {"sender": "Corp Identity Governance", "title": "Renew BizChatLTDash_Kusto_Reader data eligibility before April 25",
     "link": "https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEMAABV3dgFhEhrT5Kqtsq4o0ilAAgb8wXaAAA%3d",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Data Eligibility expiring", "extracted_date": "2026-03-26", "due_hint": "April 25, 2026"}},
    {"sender": "Himani Arora", "title": "Approve/deny SharePoint access request for AI first PM team forum",
     "link": "https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEMAABV3dgFhEhrT5Kqtsq4o0ilAAgb8wXRAAA%3d",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: SharePoint access (Himani Arora)", "extracted_date": "2026-03-26"}},
    {"sender": "CCH Notifications", "title": "Update Voice Notes release date and status in CCH",
     "link": "",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Action Required - update release date for Voice Notes", "extracted_date": "2026-03-25"}},
    {"sender": "Microsoft Digital Compliance", "title": "Fix PBI Workspace E+D IDC Strategy Worktracks compliance issues",
     "link": "",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: PBI Workspace non-compliant", "extracted_date": "2026-03-23"}},
    {"sender": "Microsoft Device Compliance", "title": "Update Windows operating system to supported version by April 8",
     "link": "",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: OS update required", "extracted_date": "2026-03-22", "due_hint": "April 8, 2026"}},
    {"sender": "Meghan MacKrell", "title": "Provide updated voice notes timeline for Comm 19648",
     "link": "https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEJAABV3dgFhEhrT5Kqtsq4o0ilAAgbf6wqAAA%3d",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Re: Comm id 19648 voice notes", "extracted_date": "2026-03-25"}},
    {"sender": "Subasini Annamalai", "title": "Review and respond to CarPlay Evals email",
     "link": "",
     "direction": "inbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Re: CarPlay Evals", "extracted_date": "2026-03-26"}},
]

# === CALENDAR / TRANSCRIPT ACTION ITEMS (my commitments) ===
transcript_mine = [
    {"sender": "Shiva Chintaluru", "title": "Consult privacy team (Seela) on audio file retention policy",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Finalize transcript vs audio upload flow - submit transcript immediately upload audio async",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Design user notification toast for file save location during upload",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Design recording time-limit UX nudge at 100min behavior at 120min cap",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Define UX for network loss during recording upload and resume behavior",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Coordinate with OCM and Notebook teams to enable create page in OCM mobile",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Track voice action availability date - add to slide if no date by Thursday",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Mobile Business update (Mar 25)", "extracted_date": "2026-03-25", "due_hint": "Thursday March 26"}},
    {"sender": "Shiva Chintaluru", "title": "Prepare CELA review materials for voice notes privacy and data handling",
     "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Meeting: Voice notes CELA review (Mar 26)", "extracted_date": "2026-03-26"}},
]

# === CALENDAR / TRANSCRIPT (outbound - waiting on others) ===
transcript_outbound = [
    {"sender": "Shiva Chintaluru", "title": "Pankesh to confirm transcription API endpoint",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes team sync (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Eva Keyes to add morning phone-check analysis to commute survey deck",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice Commute Survey Readout (Mar 25)", "extracted_date": "2026-03-25"}},
    {"sender": "Shiva Chintaluru", "title": "Vishnu Lei to sync with Poornima on Bajaj Notebook UX this week",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Weekly Audio Overview Shiproom (Mar 26)", "extracted_date": "2026-03-26", "due_hint": "this week"}},
    {"sender": "Shiva Chintaluru", "title": "Rashid Gaurav to provide async ETA for notification readiness",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Weekly Audio Overview Shiproom (Mar 26)", "extracted_date": "2026-03-26"}},
    {"sender": "Shiva Chintaluru", "title": "Amit to get MP3-to-MP4 effort estimate from Priya",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Weekly Audio Overview Shiproom (Mar 26)", "extracted_date": "2026-03-26"}},
    {"sender": "Shiva Chintaluru", "title": "Mohit Agrawal to run naming A/B test or default to Record for Notebooks",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes and live capture in Notebooks (Mar 26)", "extracted_date": "2026-03-26"}},
    {"sender": "Shiva Chintaluru", "title": "Yana Terukhova to draft and circulate strategy recommendation for voice notebooks",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "calendar",
     "extra": {"source": "calendar", "source_context": "Transcript: Voice notes and live capture in Notebooks (Mar 26)", "extracted_date": "2026-03-26"}},
    {"sender": "Shiva Chintaluru", "title": "Pankesh to share API/service for COGS estimation",
     "link": "https://teams.microsoft.com/l/message/19:75530622eadf4a669e57741d90e9d5c6@thread.v2/1774410137315?context=%7B%22contextType%22:%22chat%22%7D",
     "direction": "outbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice Leads", "extracted_date": "2026-03-26",
               "thread_id": "19:75530622eadf4a669e57741d90e9d5c6@thread.v2"}},
    {"sender": "Shiva Chintaluru", "title": "Arindam to investigate live activity widget voice perf degrade at 10% GA",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice Leads", "extracted_date": "2026-03-25",
               "thread_id": "19:75530622eadf4a669e57741d90e9d5c6@thread.v2"}},
    {"sender": "Shiva Chintaluru", "title": "Arjun Patel to spec out record in +menu UX with Jane from OCM design",
     "link": "", "direction": "outbound", "signal_type": "", "already_done": False, "source": "teams",
     "extra": {"source": "teams", "source_context": "Chat: Voice notes entry point", "extracted_date": "2026-03-24",
               "thread_id": "19:56497877df3948efbfd54a66bb58ec10@thread.v2"}},
    {"sender": "Subasini Annamalai", "title": "Wait for Katherine Gu on earcon audio feedback implementation timeline for RT Voice",
     "link": "",
     "direction": "outbound", "signal_type": "", "already_done": False, "source": "email",
     "extra": {"source": "email", "source_context": "Email: Re: Audio feedback RT Voice", "extracted_date": "2026-03-25"}},
]

# === COMPLETION EVIDENCE ===
completion_items = [
    {"sender": "Shiva Chintaluru", "topic": "EY PG Roadmap Meeting Copilot Desktop and Mobile", "thread_id": "", "evidence": "Replied to EY/PG Roadmap email Mar 26 to Bharath, Mohit, Jeet, Vidarth"},
    {"sender": "Shiva Chintaluru", "topic": "SEVAL high failure rate Voice scenario 500 error", "thread_id": "", "evidence": "Forwarded SEVAL issue to Bharath Mar 24"},
    {"sender": "Shiva Chintaluru", "topic": "Capture voice notes Copilot mobile app comm 19648", "thread_id": "", "evidence": "Replied to Meghan MacKrell Mar 25 with tentative timing"},
    {"sender": "Shiva Chintaluru", "topic": "Live activity widget voice GA status", "thread_id": "19:75530622eadf4a669e57741d90e9d5c6@thread.v2", "evidence": "Replied to Lokesh - 10pct GA, root cause identified, Arindam investigating"},
    {"sender": "Shiva Chintaluru", "topic": "VoiceNotes LiveCapture alignment", "thread_id": "", "evidence": "Shared alignment doc with Mohit Agrawal Mar 23"},
]

# === PROCESS ALL SOURCES ===
all_new_tasks = []
all_signals = []

for source_name, items in [("teams", chat_items), ("email", email_items), ("calendar", transcript_mine), ("calendar", transcript_outbound)]:
    result = process_source_items(source_name, items, ctx)
    run_stats["source_counts"][source_name] = run_stats["source_counts"].get(source_name, 0) + len(items)
    for task_item in result["to_create"]:
        task_id = add_task(task_item, config)
        all_new_tasks.append({"id": task_id, "title": task_item["title"], "sender": task_item.get("sender", "")})
        run_stats["new_tasks"] += 1
    all_signals.extend(result["signals"])
    print(f"{source_name}: {len(items)} items -> {len(result['to_create'])} new, {len(result['merged_ids'])} merged, {result['skipped']} skipped")

# === COMPLETION SIGNALS ===
comp_signals = build_completion_signals(completion_items, ctx["open_tasks"])
all_signals.extend(comp_signals)
print(f"Completion signals: {len(comp_signals)} matched")

# === TRANSITIONS ===
trans_result = run_transitions(all_signals, ctx)
transitions = trans_result["transitions"]
run_stats = trans_result["run_stats"]
run_stats["validation_additions"] = 0
print(f"Transitions: {len(transitions)}")

# === FINALIZE ===
path = finalize_sync(run_stats, ctx, transitions=transitions, new_tasks=all_new_tasks)
print(f"Dashboard: {path}")
print()
print("=== SYNC SUMMARY ===")
print(f"New tasks: {run_stats['new_tasks']}")
print(f"Merged:    {run_stats['merged']}")
print(f"Skipped:   {run_stats['skipped']}")
print(f"Transitions: {run_stats['transitions']}")
print(f"Sources:   {json.dumps(run_stats['source_counts'])}")
print()
print("New tasks created:")
for t in all_new_tasks:
    print(f"  {t['id']}: {t['title']}")
