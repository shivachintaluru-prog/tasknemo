"""Run the full sync pipeline — item extraction + processing."""
import json
from task_dashboard import (
    load_config, save_config, sync_prepare, process_source_items, add_task,
    build_completion_signals, run_transitions, finalize_sync,
)

def run_sync():
    ctx = sync_prepare()
    config = ctx["config"]
    run_stats = ctx["run_stats"]

    # Add unknown senders to stakeholders
    new_stakeholders = {
        "Shikha Verma": {"role": "peer", "weight": 3, "title": "Senior PM, M365 APP TRIAD"},
        "Parth Sangani": {"role": "partner", "weight": 5, "title": "Principal PM, E+D India"},
        "Sakshi Munjal": {"role": "peer", "weight": 3, "title": "PM 2, MSAI HYD"},
    }
    for name, info in new_stakeholders.items():
        if name not in config["stakeholders"]:
            config["stakeholders"][name] = info
            print(f"Added stakeholder: {name}")
    save_config(config)

    # === TRANSCRIPT items ===
    transcript_items = [
        # INBOUND (I committed) - Voice Team Scrum Mar 17
        {"sender": "Voice Team Scrum", "title": "Present Share-To telemetry findings in business review",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "today", "source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Voice Team Scrum", "title": "Update and circulate newsletter with correct dates",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Voice Team Scrum", "title": "Send email to Hao and Claire with voice pipeline details and demo",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Voice Team Scrum", "title": "Email segment/notification team to prioritize widget promotion blocker",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "today", "source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        # INBOUND - Voice notes team sync Mar 16
        {"sender": "Voice notes team sync", "title": "Drop epic link for investigation task tracking",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": True,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
        {"sender": "Voice notes team sync", "title": "Update Bank of America escalation email thread and close",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
        # INBOUND - Spec Review Forum Mar 16
        {"sender": "Spec Review Forum", "title": "Define Bebop version of voice notes placement and principles",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "before April", "source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Spec Review Forum (Mar 16)"}},
        {"sender": "Spec Review Forum", "title": "Add Bebopification tasks for owned experiences to sprint plan",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Spec Review Forum (Mar 16)"}},
        # OUTBOUND - Others committed to me (Voice Team Scrum Mar 17)
        {"sender": "Subasini Annamalai", "title": "Confirm CarPlay readiness and dependencies with Pankesh",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "today", "source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Subasini Annamalai", "title": "Prepare user feedback on device/voice quality for biz review",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "by 2-3 PM today", "source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Subasini Annamalai", "title": "Tag EDS owners for missing evaluation data",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        {"sender": "Subasini Annamalai", "title": "Speak with Jeet regarding feedback SDK changes",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-17",
                   "source_context": "Transcript: Voice Team Scrum (Mar 17)"}},
        # OUTBOUND - Voice notes team sync Mar 16
        {"sender": "Silky Gambhir", "title": "Investigate transcription performance batch vs fast and infra",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
        {"sender": "Silky Gambhir", "title": "Propose UX options A/B with latency trade-offs",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
        {"sender": "Arjun Patel", "title": "Schedule UX review with Julie and Nithin by Thursday",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "Thursday", "source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
        {"sender": "Pankesh Kumar", "title": "Provide 1-paragraph tech stack comparison for notebooks live chat",
         "link": "", "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                   "source_context": "Transcript: Voice notes team sync (Mar 16)"}},
    ]

    # === TEAMS (chat) items ===
    teams_items = [
        {"sender": "Mohit Agrawal", "title": "CELA legal risk review for transcription feature VP/CVP approval",
         "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773641258399",
         "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "teams", "extracted_date": "2026-03-16",
                   "source_context": "Chat: Copilot VoiceNotes intro (Bharath, Mohit, Anand, Silky, Pankesh)",
                   "description": "Otter AI lawsuit precedent - CELA engagement needed"}},
        {"sender": "Mohit Agrawal", "title": "Get Live-capture technical architecture document from Notebooks team",
         "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773685001376",
         "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "teams", "extracted_date": "2026-03-17",
                   "source_context": "Chat: Copilot VoiceNotes intro"}},
        {"sender": "Silvia Montaruli", "title": "Describe Intune policy for dictate/audio file feature 628936",
         "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a2de5acd-eb22-46f1-b06e-dc92ec962ead@unq.gbl.spaces/1773715844005",
         "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "teams", "extracted_date": "2026-03-17",
                   "source_context": "Chat: Silvia Montaruli (1:1)"}},
        {"sender": "Ayush Sharma", "title": "Add April sprint scope items to pinned doc",
         "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773731486623",
         "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "today", "source": "teams", "extracted_date": "2026-03-17",
                   "source_context": "Channel: Rahul's PM Team"}},
        {"sender": "Subasini Annamalai", "title": "Add April sprint scope items to pinned doc",
         "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773731486623",
         "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"due_hint": "today", "source": "teams", "extracted_date": "2026-03-17",
                   "source_context": "Channel: Rahul's PM Team"}},
        {"sender": "Ayush Sharma", "title": "Ground Get Me to Speed scenario with user feedback from 5 MSIT users",
         "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773716280183",
         "direction": "outbound", "signal_type": "", "already_done": False,
         "extra": {"source": "teams", "extracted_date": "2026-03-17",
                   "source_context": "Channel: Rahul's PM Team"}},
    ]

    # === EMAIL items ===
    email_items = [
        {"sender": "Account No Reply", "title": "Update Voice Notes CCH release date and status (CCH ID 112695)",
         "link": "", "direction": "inbound", "signal_type": "", "already_done": False,
         "extra": {"source": "email", "extracted_date": "2026-03-16",
                   "source_context": "Email: Action Required - update release date (maccount@microsoft.com)"}},
    ]

    # Process each source
    all_new_tasks = []
    all_signals = []
    for source_name, items in [("transcript", transcript_items), ("teams", teams_items), ("email", email_items)]:
        result = process_source_items(source_name, items, ctx)
        run_stats["source_counts"][source_name] = run_stats["source_counts"].get(source_name, 0) + len(items)
        for item in result["to_create"]:
            task_id = add_task(item, config)
            # item dict is mutated in-place by add_task (id, state, etc. added)
            all_new_tasks.append(item)
            run_stats["new_tasks"] += 1
        all_signals.extend(result["signals"])
        print(f"Source: {source_name} | Items: {len(items)} | New: {len(result['to_create'])} | Merged: {len(result['merged_ids'])} | Skipped: {result['skipped']}")

    print(f"\nTotal new tasks: {run_stats['new_tasks']}")
    print(f"Total merged: {run_stats['merged']}")
    print(f"Total skipped: {run_stats['skipped']}")
    print(f"Source counts: {json.dumps(run_stats['source_counts'])}")

    # === Completion signals from sent items evidence ===
    completion_evidence = [
        {"sender": "Noa Ghersin", "topic": "CarPlay Micron customer response",
         "thread_id": "", "evidence": "Sent Thanks Noa acknowledging CarPlay update will be communicated to Micron"},
        {"sender": "Tiffany Barnes", "topic": "Copilot Voice Notes storage retention value",
         "thread_id": "", "evidence": "Replied to Tiffany about Voice Notes value prop"},
    ]
    signals = build_completion_signals(completion_evidence, ctx["open_tasks"])
    all_signals.extend(signals)
    print(f"\nCompletion signals matched: {len(signals)}")
    for s in signals:
        print(f"  -> Task {s['task_id']}: {s['signal_type']}")

    # === Run transitions ===
    tr_result = run_transitions(all_signals, ctx)
    print(f"\nTransitions: {tr_result['run_stats']['transitions']}")
    for tid, old_st, new_st, reason in tr_result["transitions"]:
        print(f"  {tid}: {old_st} -> {new_st} ({reason})")

    # === Finalize ===
    run_stats["validation_additions"] = 0
    path = finalize_sync(run_stats, ctx,
                         transitions=tr_result["transitions"],
                         new_tasks=all_new_tasks)
    print(f"\nDashboard written to: {path}")
    print(f"\n=== SYNC COMPLETE ===")
    print(f"New tasks: {run_stats['new_tasks']}")
    print(f"Merged: {run_stats['merged']}")
    print(f"Skipped: {run_stats['skipped']}")
    print(f"Transitions: {run_stats['transitions']}")

    # Print new task details
    print("\n=== NEW TASKS ===")
    for t in all_new_tasks:
        print(f"  {t['id']}: [{t.get('direction','?')}] {t['title']} (sender: {t.get('sender','')})")

    return run_stats, all_new_tasks, tr_result

if __name__ == "__main__":
    run_sync()
