"""Current sync run - process all extracted items."""
from task_dashboard import sync_prepare, process_source_items, add_task, save_config
import json

ctx = sync_prepare()
config = ctx["config"]

# Add unknown stakeholders
new_sh = {
    "Silvia Montaruli": {"role": "external", "weight": 2, "title": "Technical PM 2, CS ABS TechStrat Italy"},
    "Nishant Sharma": {"role": "partner", "weight": 5, "title": "Principal SWE Manager, M365 APP TRIAD"},
    "Praveen Sinha": {"role": "peer", "weight": 3, "title": "Senior Product Designer, M365 APP TRIAD"},
    "Anand Rajashekaran": {"role": "partner", "weight": 5, "title": "Principal Group PM, Notebooks IDC"},
}
for name, info in new_sh.items():
    if name not in config["stakeholders"]:
        config["stakeholders"][name] = info
        print(f"Added: {name} ({info['role']}, w={info['weight']})")
save_config(config)

teams_items = [
    {"sender": "Silvia Montaruli", "title": "Reply to Silvia about Feature 628936 availability (admin policy, MC post, tenant availability)", "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a2de5acd-eb22-46f1-b06e-dc92ec962ead@unq.gbl.spaces/1773700658131", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-17", "source_context": "Chat: Silvia Montaruli (1:1)", "description": "Silvia from Tech Strategy asks about Feature 628936: tenant availability, admin policy, MC post"}},
    {"sender": "Ajay Challagalla", "title": "Reply to Ajay about Voice availability for Starter users and limits", "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_f02a487a-e055-4225-9b6e-ff43143a03b8@unq.gbl.spaces/1773655619206", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Ajay Challagalla (1:1)", "description": "Ajay asks: When is Voice live for Starter users? What are limits?"}},
    {"sender": "Bharath Tumu", "title": "Tech convergence analysis: Voice Notes vs Notebook Live Capture", "link": "https://teams.microsoft.com/l/message/19:969cea310d36485398a4a6de5b7003bc@thread.v2/1773455152676", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-14", "source_context": "Chat: Close on Live notes and Voice notes in MCA", "description": "Bharath asked Shiva/Mohit to determine which tech to leverage and converge. Ron flagged overlap."}},
    {"sender": "Bharath Tumu", "title": "Send Bharath the PM Studio / TaskNemo list he requested", "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773454395603", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-14", "source_context": "Chat: Bharath directs weekly sync", "description": "Bharath: Shiva, did you get a chance to send me the list"}},
    {"sender": "Saumitra Agarwal", "title": "Add April sprint items to sprint planning excel", "link": "https://teams.microsoft.com/l/message/19:meeting_YWJjZjJiNTAtODQ0ZS00ODJjLTllMjYtYWM4NmY3NDMzZmFk@thread.v2/1773640561994", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-17", "source_context": "Chat: Bharath directs weekly sync", "due_hint": "This week (Saumitra OOF next week)", "description": "Saumitra tagged Shiva: start adding Apr sprint items to excel"}},
    {"sender": "Mohit Agrawal", "title": "Assess CELA/legal risk for transcription feature - VP/CVP approval needed", "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773639496352", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Copilot VoiceNotes intro", "description": "Mohit flagged Otter AI lawsuits risk. VP/CVP needs to approve CELA risk."}},
    {"sender": "Mohit Agrawal", "title": "Get Live Capture technical architecture doc from Subhojeet", "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773671135102", "direction": "outbound", "signal_type": "waiting", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Copilot VoiceNotes intro", "description": "Asked Mohit for Live Capture architecture doc. Mohit asked Subhojeet."}},
    {"sender": "Praveen Sinha", "title": "Waiting on Praveen for workspaces ownership info from Notebooks designer", "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773650213643", "direction": "outbound", "signal_type": "waiting", "already_done": False, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Voice notes entry point", "description": "Praveen checking with Notebooks designer. Ishneet said Workspaces is with Ryan L and Jing."}},
    {"sender": "Noa Ghersin", "title": "CarPlay availability for Micron - Noa confirming June timeline", "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_61add666-e1e9-46f3-9c04-f99d27edf22c@unq.gbl.spaces/1773698221032", "direction": "inbound", "signal_type": "completion", "already_done": True, "extra": {"source": "teams", "extracted_date": "2026-03-17", "source_context": "Chat: Noa Ghersin (1:1)", "evidence": "Noa confirming June for CarPlay to Micron. Thanks sent."}},
    {"sender": "Nishant Sharma", "title": "Intune policy verification for Voice Notes", "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_90f4b746-6e43-4cb0-b893-f2a3d24144a2@unq.gbl.spaces/1773667087108", "direction": "inbound", "signal_type": "completion", "already_done": True, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Nishant Sharma (1:1)", "evidence": "Confirmed working as expected. No issue."}},
    {"sender": "Mohit Jindal", "title": "iOS notification settings sync with Mohit Jindal", "link": "https://teams.microsoft.com/l/message/19:24aa3701-66f6-4fdc-b280-c7b6e4916fe1_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces/1773645614446", "direction": "inbound", "signal_type": "completion", "already_done": True, "extra": {"source": "teams", "extracted_date": "2026-03-16", "source_context": "Chat: Mohit Jindal (1:1)", "evidence": "No need for catchup. Posted details in group. Call completed."}},
]

transcript_items = [
    {"sender": "Shiva Chintaluru", "title": "Create sprint tasks to track voice notes investigations", "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316_060029UTC-Meeting%20Recording.mp4?web=1", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "transcript", "extracted_date": "2026-03-16", "source_context": "Meeting: Voice notes team sync (Mar 16)", "description": "Self-committed: Drop epic link, create sprint tasks."}},
    {"sender": "Shiva Chintaluru", "title": "Update Bank of America escalation email and close it", "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316_060029UTC-Meeting%20Recording.mp4?web=1", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "transcript", "extracted_date": "2026-03-16", "source_context": "Meeting: Voice notes team sync (Mar 16)", "description": "Self-committed: Post update in BofA email thread and close escalation."}},
    {"sender": "Saumitra Agarwal", "title": "Define Bebop version of Voice Notes - placement and principles", "link": "https://teams.microsoft.com/l/meeting/details?eventId=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwFRAAgI3oLu94mAAEYAAAAAvMm_FpUKs0uh9Py4UZDxqwcAVd3YBYRIa0_SqrbKuKNIpQAAAAABDQAAVd3YBYRIa0_SqrbKuKNIpQAIDh_KawAAEA%3d%3d", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "transcript", "extracted_date": "2026-03-16", "source_context": "Meeting: Spec Review Forum (Mar 16)", "due_hint": "End of April", "description": "Define Bebop version of Voice Notes. Shiva, Arjun, Praveen own this."}},
    {"sender": "Silky Gambhir", "title": "Waiting on Silky for UX latency options (A vs B) for transcription", "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316_060029UTC-Meeting%20Recording.mp4?web=1", "direction": "outbound", "signal_type": "waiting", "already_done": False, "extra": {"source": "transcript", "extracted_date": "2026-03-16", "source_context": "Meeting: Voice notes team sync (Mar 16)", "description": "Asked Silky to return with UX options for transcription latency."}},
    {"sender": "Pankesh Kumar", "title": "Waiting on Pankesh for engineering comparison write-up (Notebook vs Live Chat)", "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316_060029UTC-Meeting%20Recording.mp4?web=1", "direction": "outbound", "signal_type": "waiting", "already_done": False, "extra": {"source": "transcript", "extracted_date": "2026-03-16", "source_context": "Meeting: Voice notes team sync (Mar 16)", "description": "Pankesh acknowledged: one-paragraph engineering comparison of tech stacks."}},
]

email_items = [
    {"sender": "Microsoft", "title": "Review new device enrollment (Action Required)", "link": "", "direction": "inbound", "signal_type": "", "already_done": False, "extra": {"source": "email", "extracted_date": "2026-03-16", "source_context": "Email: Microsoft - Action Requested: Review new device enrollment", "description": "Action Required email about new device enrollment review."}},
]

all_new = []
all_signals = []

for source, items in [("teams", teams_items), ("transcript", transcript_items), ("email", email_items)]:
    result = process_source_items(source, items, ctx)
    ctx["run_stats"]["source_counts"][source] = len(items)
    print(f"{source.upper()}: items={len(items)} create={len(result['to_create'])} merged={len(result['merged_ids'])} skipped={result['skipped']}")
    for item in result["to_create"]:
        task_id = add_task(item, config)
        all_new.append(task_id)
        ctx["run_stats"]["new_tasks"] += 1
        print(f"  + {task_id}: {item.get('title', '')[:70]}")
    all_signals.extend(result["signals"])

print(f"\nTotals: new={ctx['run_stats']['new_tasks']} merged={ctx['run_stats']['merged']} skipped={ctx['run_stats']['skipped']}")
print(f"Source counts: {json.dumps(ctx['run_stats']['source_counts'])}")
print(f"Signals: {len(all_signals)}")
print("\nNew task IDs:", [t["id"] for t in all_new])
