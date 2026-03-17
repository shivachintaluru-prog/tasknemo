"""Full sync processing for March 16, 2026 evening run."""
import json
import pickle
from task_dashboard import (
    sync_prepare, process_source_items, add_task,
    build_completion_signals, run_transitions, finalize_sync,
    load_config, save_config
)

def main():
    ctx = sync_prepare()
    config = ctx["config"]
    print(f"since_date_iso: {ctx['since_date_iso']}")
    print(f"open_tasks: {len(ctx['open_tasks'])}")
    print(f"all_tasks: {len(ctx['all_tasks'])}")

    # ============================================================
    # TEAMS INBOUND ITEMS
    # ============================================================
    teams_items = [
        {
            "sender": "Ajay Challagalla",
            "title": "Reply with Voice Notes timeline for Starter users and usage limits",
            "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_f02a487a-e055-4225-9b6e-ff43143a03b8@unq.gbl.spaces/1773655619206",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Ajay asks: when is Voice going live for Starter users? What are the limits?"}
        },
        {
            "sender": "Bharath Tumu",
            "title": "Take point with Mohit on Voice Notes vs OneNote live capture tech convergence",
            "link": "https://teams.microsoft.com/l/message/19:969cea310d36485398a4a6de5b7003bc@thread.v2/1773455152676",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:969cea310d36485398a4a6de5b7003bc@thread.v2",
                      "extracted_date": "2026-03-15",
                      "description": "Bharath asked Shiva/Mohit to determine which tech to leverage and converge. Ron flagged duplicate effort."}
        },
        {
            "sender": "Ron Pessner",
            "title": "Provide direction on Notebooks role in MCA workspace container",
            "link": "https://teams.microsoft.com/l/message/19:969cea310d36485398a4a6de5b7003bc@thread.v2/1773455152676",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:969cea310d36485398a4a6de5b7003bc@thread.v2",
                      "extracted_date": "2026-03-15",
                      "description": "Ron needs direction on container powering workspaces in MCA. If not Notebooks, rethink user journey."}
        },
        {
            "sender": "Tiffany Barnes",
            "title": "Answer follow-up questions on Voice Notes storage, access, research depth",
            "link": "https://teams.microsoft.com/l/message/19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces/1773635179809",
            "direction": "inbound", "signal_type": "", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Tiffany asked clarifying follow-ups. Already handled - shared survey artifact and answered access/privacy questions."}
        },
        {
            "sender": "Bharath Tumu",
            "title": "Prepare agent/automation demos for show-and-tell (Juhee all hands)",
            "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773638638456",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Bharath wants agent/automation items for show-and-tell. Shiva confirmed presenting Spec reviewer Agent."}
        },
        {
            "sender": "Mohit Agrawal",
            "title": "Address CELA/legal risk concerns for VoiceNotes (Otter.ai lawsuit)",
            "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773639496352",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Mohit shared Otter.ai lawsuit link. CELA escalation needed, VP/CVP approval required for risk."}
        },
        {
            "sender": "Rahul Bhuptani",
            "title": "Align with Pankesh on Voice stack/reliability line items for March",
            "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2",
                      "extracted_date": "2026-03-16",
                      "description": "Rahul: you and Pankesh should align on line items for March."}
        },
        {
            "sender": "Arjun Patel",
            "title": "Clarify Voice Notes entry point strategy (dedicated vs skill vs agent) for Juhee review",
            "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773650213643",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:56497877df3948efbfd54a66bb58ec10@thread.v2",
                      "extracted_date": "2026-03-16",
                      "description": "Arjun needs clarity on entry point positioning. Deck prepared for Juhee review."}
        },
        {
            "sender": "Ishneet Grover",
            "title": "Prepare pitch for Design LT addressing pushback on Voice Notes approach",
            "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773650213643",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:56497877df3948efbfd54a66bb58ec10@thread.v2",
                      "extracted_date": "2026-03-16",
                      "description": "Ishneet says there is pushback from Design LT. Need to prepare pitch for review."}
        },
        {
            "sender": "Mohit Agrawal",
            "title": "Respond to Live Capture technical architecture comparison request",
            "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773683166193",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Mohit claims Live Capture uses Transcription SDK. Shiva challenged claims, asked for architecture doc. Awaiting response."}
        },
    ]

    # ============================================================
    # TEAMS OUTBOUND ITEMS (waiting on others)
    # ============================================================
    outbound_items = [
        {
            "sender": "Shikha Verma",
            "title": "Tag Hao/Claire in OCM PM group with newsletter PR",
            "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Asked Shikha to tag Hao/Claire in OCM PM group with PR."}
        },
    ]

    # ============================================================
    # EMAIL ITEMS
    # ============================================================
    email_items = [
        {
            "sender": "CCH (maccount@microsoft.com)",
            "title": "Update Voice Notes release date and status in CCH (Release ID 112695)",
            "link": "https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEMAABV3dgFhEhrT5Kqtsq4o0ilAAgVK3zqAAA%3d",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "email", "extracted_date": "2026-03-16",
                      "description": "Weekly reminder: Voice Notes CCH entry shows release date 1/30/2026 In development. Needs update to current POR."}
        },
    ]

    # ============================================================
    # TRANSCRIPT ITEMS
    # ============================================================
    transcript_items = [
        {
            "sender": "Shiva Chintaluru",
            "title": "Finalize UX direction: waveform-only feedback for voice notes transcription",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwFRAAgI3oLu94mAAEYAAAAAvMm",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Self-commitment: Design UX with waveform-only, no visible live transcription text."}
        },
        {
            "sender": "Shiva Chintaluru",
            "title": "Update and close Bank of America escalation email thread",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-team-sync",
            "direction": "inbound", "signal_type": "", "already_done": True,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Self-commitment from transcript. ALREADY DONE per sent items - email closed on Mar 14."}
        },
        {
            "sender": "Shiva Chintaluru",
            "title": "Share sprint epic link (10311390) in Voice notes team sync chat",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-team-sync-epic",
            "direction": "inbound", "signal_type": "", "already_done": True,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Self-commitment. ALREADY DONE - epic link shared in chat."}
        },
        {
            "sender": "Shiva Chintaluru",
            "title": "Schedule and hold UX review meeting before proceeding with implementation",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-ux-review",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "due_hint": "Thursday",
                      "description": "Group agreed to prioritize UX review meeting on Thursday to unblock UX progress."}
        },
        {
            "sender": "Saumitra Agarwal",
            "title": "Define Bebop version of Voice Notes and align with Bebop design language",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=spec-review-forum",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "due_hint": "end of April",
                      "description": "Saumitra: define Bebop version of voice notes, ensure alignment with Bebop principles."}
        },
        {
            "sender": "Saumitra Agarwal",
            "title": "Add Bebop-ification work for Voice Notes into April sprint plan",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=spec-review-sprint",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "due_hint": "April sprints",
                      "description": "All feature owners must add Bebop work into sprint plans. Voice Notes Bebop readiness by end of April."}
        },
        # Outbound transcript items
        {
            "sender": "Silky Gambhir",
            "title": "Waiting: UX options (A/B) comparing live vs batch transcription with latency data",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-silky-ux",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Silky to prepare UX options comparing live vs batch transcription with upload latency and duration data."}
        },
        {
            "sender": "Silky Gambhir",
            "title": "Waiting: Test upload + transcription performance for P50/P90/P95 durations",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-silky-perf",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Silky to test and report upload/transcription times for P50/P90/P95 voice note durations."}
        },
        {
            "sender": "Silky Gambhir",
            "title": "Waiting: Investigate transcription infrastructure and ACS SDK reuse for batch",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-silky-infra",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Silky investigating whether ACS SDK integration can be reused for batch transcription."}
        },
        {
            "sender": "Pankesh Kumar",
            "title": "Waiting: Close open tech discussions with Lokesh/Shreyansh",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-pankesh-lokesh",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "due_hint": "today",
                      "description": "Pankesh committed to closing open tech discussions today."}
        },
        {
            "sender": "Pankesh Kumar",
            "title": "Waiting: Engineering comparison paragraph - Live Chat vs Notebooks stack",
            "link": "https://teams.microsoft.com/l/meeting/details?eventId=voice-notes-pankesh-compare",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Pankesh/Eng to provide one paragraph comparing tech stacks and reply on email thread."}
        },
    ]

    # ============================================================
    # COMPLETION EVIDENCE
    # ============================================================
    completion_items = [
        {
            "sender": "Shiva Chintaluru", "title": "Share epic link for voice notes investigations",
            "link": "https://teams.microsoft.com/l/message/19:meeting_NTczYzE4OWYt@thread.v2/1773640941336",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "evidence": "Epic 10311390 link shared in Voice notes team sync."}
        },
        {
            "sender": "Rahul Bhuptani", "title": "ADO line item / spec timing clarification",
            "link": "https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "evidence": "Rahul answered: no new row needed."}
        },
        {
            "sender": "Ishneet Grover", "title": "Workspaces ownership clarification",
            "link": "https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773650213643",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "evidence": "Ishneet confirmed Workspaces owned by Ryan L and Jing."}
        },
        {
            "sender": "Shiva Chintaluru", "title": "Close Bank of America escalation email",
            "link": "https://outlook.office365.com/owa/?ItemID=BofA-thread",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "email", "extracted_date": "2026-03-14",
                      "evidence": "Confirmed policy worked, asked to close thread."}
        },
        {
            "sender": "Noa Ghersin", "title": "Micron CarPlay communication approved",
            "link": "https://outlook.office365.com/owa/?ItemID=Micron-thread",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "email", "extracted_date": "2026-03-14",
                      "evidence": "Shiva approved messaging, said Yes this works."}
        },
        {
            "sender": "Nishant Sharma", "title": "Intune policy status confirmed working",
            "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_90f4b746-6e43-4cb0-b893-f2a3d24144a2@unq.gbl.spaces/1773667087108",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "evidence": "Confirmed no issue, policy working as expected."}
        },
        {
            "sender": "Tiffany Barnes", "title": "Voice Notes research artifact shared",
            "link": "https://teams.microsoft.com/l/message/19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces/1773635179809",
            "direction": "inbound", "signal_type": "completion", "already_done": True,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "evidence": "Shared feedback survey XLSX and answered all access/privacy questions."}
        },
    ]

    # ============================================================
    # PROCESS ALL SOURCES
    # ============================================================
    all_new_tasks = []
    all_signals = []

    print("\n=== Processing teams inbound items ===")
    result = process_source_items("teams", teams_items, ctx)
    print(f"to_create: {len(result['to_create'])}, merged: {len(result['merged_ids'])}, skipped: {result['skipped']}")
    for item in result["to_create"]:
        tid = add_task(item, config)
        all_new_tasks.append(tid)
        print(f"  + {tid}: {item['title']}")
    all_signals.extend(result["signals"])

    print("\n=== Processing outbound items ===")
    result = process_source_items("teams", outbound_items, ctx)
    print(f"to_create: {len(result['to_create'])}, merged: {len(result['merged_ids'])}, skipped: {result['skipped']}")
    for item in result["to_create"]:
        tid = add_task(item, config)
        all_new_tasks.append(tid)
        print(f"  + {tid}: {item['title']}")
    all_signals.extend(result["signals"])

    print("\n=== Processing email items ===")
    result = process_source_items("email", email_items, ctx)
    print(f"to_create: {len(result['to_create'])}, merged: {len(result['merged_ids'])}, skipped: {result['skipped']}")
    for item in result["to_create"]:
        tid = add_task(item, config)
        all_new_tasks.append(tid)
        print(f"  + {tid}: {item['title']}")
    all_signals.extend(result["signals"])

    print("\n=== Processing transcript items ===")
    result = process_source_items("transcript", transcript_items, ctx)
    print(f"to_create: {len(result['to_create'])}, merged: {len(result['merged_ids'])}, skipped: {result['skipped']}")
    for item in result["to_create"]:
        tid = add_task(item, config)
        all_new_tasks.append(tid)
        print(f"  + {tid}: {item['title']}")
    all_signals.extend(result["signals"])

    print("\n=== Processing completion items ===")
    result = process_source_items("teams", completion_items, ctx)
    print(f"to_create: {len(result['to_create'])}, merged: {len(result['merged_ids'])}, skipped: {result['skipped']}")
    all_signals.extend(result["signals"])

    # Source counts
    ctx["run_stats"]["source_counts"] = {
        "teams_inbound": len(teams_items),
        "teams_outbound": len(outbound_items),
        "email": len(email_items),
        "transcript": len(transcript_items),
        "completion_evidence": len(completion_items),
        "doc_mentions": 1,
        "calendar": 10,
    }
    ctx["run_stats"]["new_tasks"] = len(all_new_tasks)

    print("\n=== Source counts ===")
    for src, count in ctx["run_stats"]["source_counts"].items():
        flag = " *** COVERAGE GAP ***" if count == 0 else ""
        print(f"  {src}: {count}{flag}")

    print(f"\nTotal new tasks: {len(all_new_tasks)}")
    print(f"Total signals: {len(all_signals)}")
    print(f"New task IDs: {all_new_tasks}")

    # Save state for finalization
    with open("data/_sync_state_v2.pkl", "wb") as f:
        pickle.dump({
            "run_stats": ctx["run_stats"],
            "all_new_task_ids": all_new_tasks,
            "all_signals": all_signals,
            "since_date": ctx["since_date"],
            "since_date_iso": ctx["since_date_iso"],
            "pre_closed": ctx["pre_closed"],
            "inbox_ids": ctx["inbox_ids"],
            "ctx": {
                "config": config,
                "since_date": ctx["since_date"],
                "since_date_iso": ctx["since_date_iso"],
                "open_tasks": [t["id"] for t in ctx["open_tasks"]],
                "pre_closed": ctx["pre_closed"],
                "inbox_ids": ctx["inbox_ids"],
            },
        }, f)
    print("State saved to data/_sync_state_v2.pkl")


if __name__ == "__main__":
    main()
