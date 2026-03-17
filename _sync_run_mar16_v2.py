"""Full sync processing for March 16, 2026 run (evening)."""
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

    # Add Silky Gambhir to stakeholders
    if "Silky Gambhir" not in config["stakeholders"]:
        config["stakeholders"]["Silky Gambhir"] = {
            "role": "peer", "weight": 3, "title": "Senior Software Engineer"
        }
        save_config(config)
        print("Added Silky Gambhir to stakeholders")

    # === TEAMS INBOUND ITEMS ===
    teams_items = [
        {
            "sender": "Joe Gallagher",
            "title": "Update and close Bank of America Dictate/VoiceNotes escalation thread",
            "link": "https://teams.microsoft.com/l/message/19:d14245c03ef241c2a4876b85452ac6b6@thread.v2/1773632295045",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "thread_id": "19:d14245c03ef241c2a4876b85452ac6b6@thread.v2",
                      "extracted_date": "2026-03-14",
                      "description": "BofA customer DCR - Voice Notes creates audio with sensitive info, need disable policy on iOS. Joe asks for summary to close case."}
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
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Tiffany asked clarifying follow-ups on Voice Notes access and research depth."}
        },
        {
            "sender": "Bharath Tumu",
            "title": "Prepare agent/automation demos for show-and-tell",
            "link": "https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773638638456",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Bharath wants agent/automation items for show-and-tell."}
        },
        {
            "sender": "Mohit Agrawal",
            "title": "Address CELA/legal risk concerns for VoiceNotes (Otter.ai lawsuit)",
            "link": "https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773639496352",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "teams", "extracted_date": "2026-03-16",
                      "description": "Mohit shared Otter.ai lawsuit link and CELA escalation in VoiceNotes intro thread."}
        },
    ]

    # === OUTBOUND ITEMS (waiting on others) ===
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

    # === TRANSCRIPT ITEMS ===
    transcript_items = [
        {
            "sender": "Shiva Chintaluru",
            "title": "Finalize UX direction: waveform-only feedback for voice notes transcription",
            "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316.mp4",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Self-commitment: Design UX with waveform-only, no visible live transcription text."}
        },
        {
            "sender": "Shiva Chintaluru",
            "title": "Update and close Bank of America escalation email thread",
            "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316.mp4",
            "direction": "inbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Self-commitment from transcript: update and close BofA escalation thread."}
        },
        {
            "sender": "Silky Gambhir",
            "title": "Waiting: UX options (A/B) comparing live vs batch transcription",
            "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316.mp4",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Silky to prepare UX options comparing live vs batch transcription with latency data."}
        },
        {
            "sender": "Pankesh Kumar",
            "title": "Waiting: Close open tech discussions with Lokesh/Shreyansh",
            "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316.mp4",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "due_hint": "today",
                      "description": "Pankesh committed to closing open tech discussions today."}
        },
        {
            "sender": "Pankesh Kumar",
            "title": "Waiting: Engineering comparison paragraph - Live Chat vs Notebooks stack",
            "link": "https://microsoftapc-my.sharepoint.com/personal/pankeshkumar_microsoft_com/Documents/Recordings/Voice%20notes%20team%20sync-20260316.mp4",
            "direction": "outbound", "signal_type": "", "already_done": False,
            "extra": {"source": "transcript", "extracted_date": "2026-03-16",
                      "description": "Pankesh/Eng to provide one paragraph comparing tech stacks."}
        },
    ]

    # === COMPLETION EVIDENCE ===
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
    ]

    # === PROCESS ALL SOURCES ===
    all_new_tasks = []
    all_signals = []

    print("\n=== Processing teams items ===")
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
        "teams": len(teams_items),
        "outbound": len(outbound_items),
        "transcript": len(transcript_items),
        "completion_evidence": len(completion_items),
        "email": 0,
        "doc_mentions": 0,
        "calendar": 9,
    }
    ctx["run_stats"]["new_tasks"] = len(all_new_tasks)

    print("\n=== Source counts ===")
    print(json.dumps(ctx["run_stats"]["source_counts"], indent=2))
    for src, count in ctx["run_stats"]["source_counts"].items():
        if count == 0:
            print(f"  WARNING: {src}: 0 items (potential coverage gap)")

    print(f"\nTotal new tasks: {len(all_new_tasks)}")
    print(f"Total signals: {len(all_signals)}")

    # Save state
    with open("data/_sync_state_v2.pkl", "wb") as f:
        pickle.dump({
            "run_stats": ctx["run_stats"],
            "all_new_task_ids": all_new_tasks,
            "all_new_tasks": all_new_tasks,
            "all_signals": all_signals,
            "since_date": ctx["since_date"],
            "since_date_iso": ctx["since_date_iso"],
            "pre_closed": ctx["pre_closed"],
            "inbox_ids": ctx["inbox_ids"],
        }, f)
    print("Saved sync state")

if __name__ == "__main__":
    main()
