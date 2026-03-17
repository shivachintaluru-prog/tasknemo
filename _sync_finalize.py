"""Validation, completion signals, transitions, and finalize."""
import json
from task_dashboard import (
    sync_prepare, process_source_items, add_task, get_task,
    build_completion_signals, run_transitions, finalize_sync,
    load_config, save_config, load_tasks, list_tasks
)

ctx = sync_prepare()
run_stats = ctx['run_stats']
run_stats['new_tasks'] = 13
run_stats['merged'] = 1
run_stats['skipped'] = 6
run_stats['source_counts'] = {
    'transcript': 9, 'teams': 5, 'email': 1,
    'doc_mentions': 1, 'sent_items': 4,
}

# ============================================================
# VALIDATION ADDITIONS
# ============================================================
validation_items = [
    {
        'sender': 'Bharath Tumu',
        'title': 'Compile AI/PM automations list for show-and-tell demo',
        'link': 'https://teams.microsoft.com/l/message/19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces/1773388970728',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Bharath asked for a list of AI/PM automations. You committed: I will get a list.',
            'thread_id': '19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces',
            'extracted_date': '2026-03-14',
        }
    },
    {
        'sender': 'Bharath Tumu',
        'title': 'Sync with Mohit Anand on Voice Notes vs Voice feature overlap',
        'link': 'https://teams.microsoft.com/l/message/19:2e5188f8b38b46f38bf263b11980d3b9@thread.v2/1773280232709',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Bharath asked to assess Voice Notes vs Voice overlap. You committed to block time and add Mohit.',
            'thread_id': '19:2e5188f8b38b46f38bf263b11980d3b9@thread.v2',
            'extracted_date': '2026-03-12',
        }
    },
    {
        'sender': 'Mahima Singh',
        'title': 'Update March 20 newsletter (20260320 M365 Copilot Mobile Update)',
        'link': '',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'email',
            'description': 'Mahima mentioned you for March 20 newsletter updates',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Mohit Anand',
        'title': 'Respond to Loop mention in M365 Copilot Mobile PM Monthly',
        'link': '',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'doc_mentions',
            'description': 'Mohit Anand mentioned you in Monthly PM Loop paragraph. Input needed.',
            'extracted_date': '2026-03-14',
        }
    },
    {
        'sender': 'Subasini Annamalai',
        'title': 'Triage ADO bug 9212947: Big increase in navigation complaints',
        'link': 'https://dev.azure.com/office/e853b87d-318c-4879-bedc-5855f3483b54/_workitems/edit/9212947',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'ADO bug assigned to you: Big increase in users complaining about navigation. State: New.',
            'extracted_date': '2026-03-14',
        }
    },
]

result = process_source_items('validation', validation_items, ctx)
print(f"VALIDATION: to_create={len(result['to_create'])}, merged={len(result['merged_ids'])}, skipped={result['skipped']}")

validation_additions = []
for item in result['to_create']:
    task_id = add_task(item, ctx['config'])
    validation_additions.append(task_id)
    run_stats['new_tasks'] += 1
    print(f"  + {task_id}: {item['title']} [{item.get('direction','')}]")
run_stats['validation_additions'] = validation_additions
run_stats['source_counts']['validation'] = len(validation_items)
run_stats['merged'] += len(result['merged_ids'])
run_stats['skipped'] += result['skipped']

print()

# ============================================================
# BUILD COMPLETION SIGNALS
# ============================================================
completion_evidence = [
    {
        'sender': 'Tiffany Barnes',
        'topic': 'Voice notes storage retention',
        'thread_id': '19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces',
        'evidence': 'Answered all storage, retention, Copilot memory questions in Teams',
    },
    {
        'sender': 'Joe Gallagher',
        'topic': 'BofA Dictate policy disabled',
        'thread_id': '19:d14245c03ef241c2a4876b85452ac6b6@thread.v2',
        'evidence': 'Policy validated and working. Joe confirmed closing the case.',
    },
    {
        'sender': 'Noa Ghersin',
        'topic': 'CarPlay voice navigation Micron',
        'thread_id': '',
        'evidence': 'Replied with timeline. Noa drafted customer messaging.',
    },
    {
        'sender': 'Vidarth Jaikrishnan',
        'topic': 'ZQ newsletter transition',
        'thread_id': '19:27e21d95-d37b-4024-a823-b2d9c44db61a_6df2635a-6bcb-4862-b1e4-ad1aab39f63d@unq.gbl.spaces',
        'evidence': 'Transitioned ZQ item to Vidarth. Eng done in DF.',
    },
    {
        'sender': 'Saumitra Agarwal',
        'topic': 'newsletter doc comment ZQ completion',
        'thread_id': '',
        'evidence': 'Replied to doc comment and transitioned ZQ to Vidarth',
    },
]

open_tasks = list_tasks(states={'open', 'needs_followup', 'waiting'})
signals = build_completion_signals(completion_evidence, open_tasks)
print(f"Completion signals matched: {len(signals)}")
for s in signals:
    print(f"  {s['task_id']}: {s['signal_type']} - {s.get('signal', '')[:80]}")

# ============================================================
# RUN TRANSITIONS
# ============================================================
print()
print("Running transitions...")
tr_result = run_transitions(signals, ctx)
transitions = tr_result['transitions']
final_stats = tr_result['run_stats']
# Merge our tracking into final stats
final_stats['new_tasks'] = run_stats['new_tasks']
final_stats['source_counts'] = run_stats['source_counts']
final_stats['validation_additions'] = run_stats['validation_additions']
final_stats['merged'] = run_stats['merged']
final_stats['skipped'] = run_stats['skipped']

print(f"Transitions: {len(transitions)}")
for task_id, old_state, new_state, reason in transitions:
    print(f"  {task_id}: {old_state} -> {new_state} ({reason})")

# ============================================================
# FINALIZE SYNC
# ============================================================
print()
print("Finalizing sync...")
all_new_task_objs = []
all_new_ids = [
    'TASK-309','TASK-310','TASK-311','TASK-312','TASK-313','TASK-314',
    'TASK-315','TASK-316','TASK-317','TASK-318','TASK-319','TASK-320','TASK-321',
] + validation_additions
for tid in all_new_ids:
    t = get_task(tid)
    if t:
        all_new_task_objs.append(t)

path = finalize_sync(final_stats, ctx, transitions=transitions, new_tasks=all_new_task_objs)
print(f"Dashboard written to: {path}")
print()
print("=== FINAL RUN STATS ===")
print(json.dumps(final_stats, indent=2))
print()
print(f"Total new tasks: {final_stats['new_tasks']}")
print(f"Total transitions: {final_stats['transitions']}")
print(f"Total merged: {final_stats['merged']}")
print(f"Total skipped: {final_stats['skipped']}")
print(f"Validation additions: {final_stats.get('validation_additions', [])}")
