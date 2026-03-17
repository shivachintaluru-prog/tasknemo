"""One-shot sync run for March 16, 2026."""
import json
from task_dashboard import (
    sync_prepare, process_source_items, add_task, build_completion_signals,
    run_transitions, finalize_sync, load_config, save_config
)

# Re-run sync_prepare to get fresh context with updated config
ctx = sync_prepare()
print(f'Since date ISO: {ctx["since_date_iso"]}')
print(f'Open tasks: {len(ctx["open_tasks"])}')
print()

all_new_tasks = []
all_signals = []
run_stats = ctx['run_stats']

# ============================================================
# SOURCE: transcript (richest source - both directions)
# ============================================================
transcript_items = [
    # MY commitments (inbound)
    {
        'sender': 'Claire Liu',
        'title': 'Share get-me-up-to-speed prompt with Claire for review',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire asked Shiva to share the get-me-up-to-speed prompt for review and pass-through',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Propose candidate quality metrics/goals for voice',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire said if your team has proposals for quality metrics/goals, feel free to share',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Subasini Annamalai',
        'title': 'Update voice evals deck: add eval dimensions, callout mobile testing',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Subasini gave deck feedback: Add eval dimensions, Callout that this was tested on mobile',
            'extracted_date': '2026-03-12',
        }
    },
    # OTHERS' commitments (outbound - I am waiting)
    {
        'sender': 'Claire Liu',
        'title': 'Claire to share quality tracking deck',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire said: I can share you the deck used to track quality issues',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Claire to mitigate live-site voice interruptions by end of March',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire committed: We want to quickly mitigate the current live site by end of March',
            'due_hint': 'end of March',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Claire to determine root cause and ETA for voice regressions',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire said: Hopefully by next week we can at least have a conclusion',
            'due_hint': 'next week',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Claire to check Pineapple SDF readiness and share integration instructions',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire said: I will check with the work team and get finalized instructions. Target March 16',
            'due_hint': 'March 16',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Claire to verify Voice SUA enablement behind feature flag',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire said: I can double check with my dev team if Voice SUA can be enabled in Uni app via feature flag',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Claire Liu',
        'title': 'Claire to check on voice-quality goal metrics internally',
        'link': 'https://microsoft-my.sharepoint-df.com/personal/shchint_microsoft_com/Documents/Recordings/Weekly%20Voice%20Sync-20260312_073431UTC-Meeting%20Recording.mp4?web=1',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'transcript',
            'description': 'Claire checked with Xiaoyu and Hao and committed to verify concrete quality metrics/goals',
            'extracted_date': '2026-03-12',
        }
    },
]

result = process_source_items('transcript', transcript_items, ctx)
print(f'TRANSCRIPT: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')
for item in result['to_create']:
    task_id = add_task(item, ctx['config'])
    all_new_tasks.append(task_id)
    run_stats['new_tasks'] += 1
    print(f'  + {task_id}: {item["title"]} [{item.get("direction","")}]')
all_signals.extend(result.get('signals', []))
run_stats['source_counts']['transcript'] = len(transcript_items)

# ============================================================
# SOURCE: teams (chat messages)
# ============================================================
teams_items = [
    {
        'sender': 'Pranav Vijayvaran',
        'title': 'Help Pranav get Teams Mobile voice stack architecture and metrics',
        'link': 'https://teams.microsoft.com/l/message/19:054c75823f624407b26280222b7f2682@thread.v2/1773303604120?context=%7B%22contextType%22:%22chat%22%7D',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Pranav asked for help connecting with Teams Mobile people for voice communication stack architecture, fundamental metrics. Kanishk also asked to sync on WebRTC readiness criteria for Deepak review.',
            'thread_id': '19:054c75823f624407b26280222b7f2682@thread.v2',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Mohit Jindal',
        'title': 'Review PR 4923547: Adding WebRTC Log Files in OCV Feedback',
        'link': 'https://office.visualstudio.com/Office/_git/Office/pullrequest/4923547',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Mohit Jindal submitted PR for ACS WebRTC log upload in OCV feedback. Behind FG. Needs review on zip file name and modifications.',
            'thread_id': '19:054c75823f624407b26280222b7f2682@thread.v2',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Ayush Sharma',
        'title': 'Raise with Bharath: heads-up to Hao about get-up-to-speed PR approval for DF',
        'link': 'https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816?context=%7B%22contextType%22:%22chat%22%7D',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Ayush flagged: need to give Hao a heads up about get-up-to-speed feature and support (PR approval) needed to take it to DF',
            'thread_id': '19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Ayush Sharma',
        'title': 'Raise with Bharath: IRIS segment creation delays from DS single-person dependency',
        'link': 'https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816?context=%7B%22contextType%22:%22chat%22%7D',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Ayush flagged: IRIS segment creation has delays from DS side because of single person dependency that needs to be corrected. Raise with Bharath.',
            'thread_id': '19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Pankesh Kumar',
        'title': 'Pankesh to share current voice notes stack details',
        'link': 'https://teams.microsoft.com/l/message/19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2/1773639496352?context=%7B%22contextType%22:%22chat%22%7D',
        'direction': 'outbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Shiva asked Pankesh to share current stack details in VoiceNotes intro chat',
            'thread_id': '19:meeting_NjQxMGNiZTgtNDliZS00ZjA0LTk5MjYtMDcyODczMTk1NjBk@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
]

result = process_source_items('teams', teams_items, ctx)
print(f'TEAMS: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')
for item in result['to_create']:
    task_id = add_task(item, ctx['config'])
    all_new_tasks.append(task_id)
    run_stats['new_tasks'] += 1
    print(f'  + {task_id}: {item["title"]} [{item.get("direction","")}]')
all_signals.extend(result.get('signals', []))
run_stats['source_counts']['teams'] = len(teams_items)

# ============================================================
# SOURCE: email
# ============================================================
email_items = [
    {
        'sender': 'Noa Ghersin',
        'title': 'Review Noa draft customer messaging for Micron before Monday 3/16 send',
        'link': 'https://outlook.office365.com/owa/?ItemID=AAMkAGNlNWQ2YjQwLWMwMGItNGZkZC1hYjVlLWE5MWMwNDFiYzAyNwBGAAAAAAC8yb4WlQqzS6H0%2fLhRkPGrBwBV3dgFhEhrT5Kqtsq4o0ilAAAAAAEJAABV3dgFhEhrT5Kqtsq4o0ilAAgSr3lBAAA%3d&exvsurl=1&viewmodel=ReadMessageItem',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'email',
            'description': 'Noa drafted customer messaging for Micron based on your CarPlay timeline. She said she will share with Micron on Monday 3/16 unless you flag concerns.',
            'due_hint': 'Monday March 16',
            'extracted_date': '2026-03-13',
        }
    },
]

result = process_source_items('email', email_items, ctx)
print(f'EMAIL: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')
for item in result['to_create']:
    task_id = add_task(item, ctx['config'])
    all_new_tasks.append(task_id)
    run_stats['new_tasks'] += 1
    print(f'  + {task_id}: {item["title"]} [{item.get("direction","")}]')
all_signals.extend(result.get('signals', []))
run_stats['source_counts']['email'] = len(email_items)

# ============================================================
# SOURCE: doc_mentions
# ============================================================
doc_items = [
    {
        'sender': 'Saumitra Agarwal',
        'title': 'Share ZQ newsletter completion status and transition to Vidarth',
        'link': 'https://microsoftapc.sharepoint.com/teams/M365App/_layouts/15/Doc.aspx?sourcedoc=%7B76584564-8383-44AB-B757-C40ED2D313F9%7D',
        'direction': 'inbound',
        'signal_type': 'completion',
        'already_done': True,
        'extra': {
            'source': 'doc_mentions',
            'description': 'Saumitra asked: can you share if this is completed, and transition further to Vidarth. You already replied and transitioned.',
            'extracted_date': '2026-03-13',
            'evidence': 'Shiva replied to doc comment and transitioned ZQ to Vidarth in newsletter',
        }
    },
]

result = process_source_items('doc_mentions', doc_items, ctx)
print(f'DOC_MENTIONS: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')
run_stats['source_counts']['doc_mentions'] = len(doc_items)

# ============================================================
# SOURCE: sent_items (completion signals only)
# ============================================================
sent_completion_items = [
    {
        'sender': 'Tiffany Barnes',
        'title': 'Voice notes storage/retention Q&A',
        'link': '',
        'direction': 'inbound',
        'signal_type': 'completion',
        'already_done': True,
        'extra': {
            'source': 'sent_items',
            'evidence': 'Answered all storage, retention, Copilot memory questions in Teams',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Joe Gallagher',
        'title': 'BofA Dictate policy scope resolution',
        'link': '',
        'direction': 'inbound',
        'signal_type': 'completion',
        'already_done': True,
        'extra': {
            'source': 'sent_items',
            'evidence': 'Policy validated and working. Joe confirmed closing the support case.',
            'extracted_date': '2026-03-14',
        }
    },
    {
        'sender': 'Noa Ghersin',
        'title': 'CarPlay voice navigation timeline reply',
        'link': '',
        'direction': 'inbound',
        'signal_type': 'completion',
        'already_done': True,
        'extra': {
            'source': 'sent_items',
            'evidence': 'Replied with CarPlay voice timeline (end of April). Noa drafted customer messaging.',
            'extracted_date': '2026-03-13',
        }
    },
    {
        'sender': 'Vidarth Jaikrishnan',
        'title': 'ZQ newsletter status and transition',
        'link': '',
        'direction': 'inbound',
        'signal_type': 'completion',
        'already_done': True,
        'extra': {
            'source': 'sent_items',
            'evidence': 'Transitioned ZQ item to Vidarth. Clarified eng work done in DF, campaign pending.',
            'extracted_date': '2026-03-13',
        }
    },
]

result = process_source_items('sent_items', sent_completion_items, ctx)
print(f'SENT_ITEMS: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')
all_signals.extend(result.get('signals', []))
run_stats['source_counts']['sent_items'] = len(sent_completion_items)

print()
print('=== RUN STATS SO FAR ===')
print(json.dumps(run_stats, indent=2))
print()
print(f'Total new tasks created: {len(all_new_tasks)}')
print(f'Total signals collected: {len(all_signals)}')

# Save for next steps
import pickle
with open('data/_sync_state.pkl', 'wb') as f:
    pickle.dump({
        'all_new_tasks': all_new_tasks,
        'all_signals': all_signals,
        'run_stats': run_stats,
        'ctx': {k: v for k, v in ctx.items() if k != 'all_tasks'},
    }, f)
print('\nSync state saved for continuation.')
