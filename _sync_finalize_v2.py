"""Validation, completion signals, transitions, and finalize for Mar 16 v2."""
import json
import pickle
from task_dashboard import (
    sync_prepare, process_source_items, add_task, build_completion_signals,
    run_transitions, finalize_sync, load_config, save_config, list_tasks, get_task
)

# Reload state
with open('data/_sync_state_v2.pkl', 'rb') as f:
    state = pickle.load(f)
all_new_tasks = state['all_new_tasks']
all_signals = state['all_signals']
run_stats = state['run_stats']

ctx = sync_prepare()

# ============================================================
# PHASE 3: VALIDATION -- net-new items from WorkIQ cross-check
# ============================================================
validation_items = [
    {
        'sender': 'Ishneet Grover',
        'title': 'Prepare pitch for Design LT on Voice Notes direction',
        'link': 'https://teams.microsoft.com/l/message/19:56497877df3948efbfd54a66bb58ec10@thread.v2/1773650213643',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Ishneet Grover: Shiva we need to prepare a pitch for Design LT. You committed to review proposal in product review forum.',
            'thread_id': '19:56497877df3948efbfd54a66bb58ec10@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Vishnu Gogula',
        'title': 'Share Playlist spec/1-pager with Vishnu (target 3/27)',
        'link': 'https://teams.microsoft.com/l/message/19:2b0a0ee875684cb49ed26f3e9cb15da6@thread.v2/1773649097220',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Vishnu asked: Do share the 1-pager/Spec whenever it is ready. AO line item spec targeted for 3/27.',
            'due_hint': 'March 27',
            'thread_id': '19:2b0a0ee875684cb49ed26f3e9cb15da6@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Rahul Bhuptani',
        'title': 'Share voice insights from Copilot field session document',
        'link': 'https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Rahul asked: Could you please share insights for voice from the document?',
            'thread_id': '19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
    {
        'sender': 'Rahul Bhuptani',
        'title': 'Share plan for voice catch-up prompt with Rahul',
        'link': 'https://teams.microsoft.com/l/message/19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2/1773634767816',
        'direction': 'inbound',
        'signal_type': '',
        'already_done': False,
        'extra': {
            'source': 'teams',
            'description': 'Rahul asked: Shiva, Ayush - can you please share the plan for voice catchup prompt with me tomorrow?',
            'thread_id': '19:05c64c4226ca4326b01fc45aef28e4b4@thread.v2',
            'extracted_date': '2026-03-16',
        }
    },
]

result = process_source_items('validation', validation_items, ctx)
print(f'VALIDATION: to_create={len(result["to_create"])}, merged={len(result["merged_ids"])}, skipped={result["skipped"]}')

validation_additions = []
for item in result['to_create']:
    task_id = add_task(item, ctx['config'])
    validation_additions.append(task_id)
    all_new_tasks.append(task_id)
    run_stats['new_tasks'] += 1
    print(f'  + {task_id}: {item["title"]} [{item.get("direction","")}]')
for mid in result['merged_ids']:
    print(f'  ~ merged into {mid}')
run_stats['validation_additions'] = validation_additions
run_stats['source_counts']['validation'] = len(validation_items)
run_stats['merged'] += len(result['merged_ids'])
print()

# ============================================================
# BUILD COMPLETION SIGNALS
# ============================================================
completion_evidence = [
    {
        'sender': 'Tiffany Barnes',
        'topic': 'Voice notes storage retention',
        'thread_id': '19:184033c7-583c-43ca-9715-234b229a32f8_27e21d95-d37b-4024-a823-b2d9c44db61a@unq.gbl.spaces',
        'evidence': 'Answered all storage, retention, Copilot memory questions in Teams. Shared feedback survey.',
    },
    {
        'sender': 'Joe Gallagher',
        'topic': 'BofA Dictate policy disabled',
        'thread_id': '19:d14245c03ef241c2a4876b85452ac6b6@thread.v2',
        'evidence': 'Joe confirmed: send summary and close the case. Pankesh confirmed update.',
    },
    {
        'sender': 'Bharath Tumu',
        'topic': 'AI PM automations agent ideas list',
        'thread_id': '19:27e21d95-d37b-4024-a823-b2d9c44db61a_a5838170-efba-41da-b2b0-32296eef2703@unq.gbl.spaces',
        'evidence': 'Shared detailed agent ideas list. Bharath acknowledged.',
    },
]

open_tasks = list_tasks(states={'open', 'needs_followup', 'waiting'})
signals = build_completion_signals(completion_evidence, open_tasks)
all_signals.extend(signals)
print(f'Completion signals matched: {len(signals)}')
for s in signals:
    print(f'  {s["task_id"]}: {s["signal_type"]} - {s.get("signal", "")[:80]}')
print()

# ============================================================
# RUN TRANSITIONS
# ============================================================
print('Running transitions...')
tr_result = run_transitions(all_signals, ctx)
transitions = tr_result['transitions']
final_stats = tr_result['run_stats']

# Merge our tracking into final stats
final_stats['new_tasks'] = run_stats['new_tasks']
final_stats['source_counts'] = run_stats['source_counts']
final_stats['validation_additions'] = run_stats.get('validation_additions', [])
final_stats['merged'] = run_stats['merged']
final_stats['skipped'] = run_stats['skipped']

print(f'Transitions: {len(transitions)}')
for task_id, old_state, new_state, reason in transitions:
    print(f'  {task_id}: {old_state} -> {new_state} ({reason})')
print()

# ============================================================
# FINALIZE SYNC
# ============================================================
print('Finalizing sync...')
all_new_task_objs = []
for tid in all_new_tasks:
    t = get_task(tid)
    if t:
        all_new_task_objs.append(t)

path = finalize_sync(final_stats, ctx, transitions=transitions, new_tasks=all_new_task_objs)
print(f'Dashboard written to: {path}')
print()
print('=== FINAL RUN STATS ===')
print(json.dumps(final_stats, indent=2))
print()
print(f'Total new tasks: {final_stats["new_tasks"]}')
print(f'Total transitions: {final_stats["transitions"]}')
print(f'Total merged: {final_stats["merged"]}')
print(f'Total skipped: {final_stats["skipped"]}')
print(f'Validation additions: {final_stats.get("validation_additions", [])}')
