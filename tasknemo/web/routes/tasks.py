"""Task CRUD API — GET/POST/PATCH tasks, actions."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...tasks import get_task, list_tasks, update_task, add_task
from ...scoring import score_task, score_all_tasks
from ...state_machine import transition_task
from ...analytics import pin_task, unpin_task
from ..deps import get_config, get_analytics

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    sender: Optional[str] = "me"
    source: Optional[str] = "manual"
    direction: Optional[str] = "inbound"
    due_hint: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_hint: Optional[str] = None
    next_step: Optional[str] = None
    sender: Optional[str] = None
    user_priority: Optional[int] = None


class TransitionRequest(BaseModel):
    state: str
    reason: Optional[str] = ""


class BulkAction(BaseModel):
    ids: list[str]
    action: str  # "close", "pin", "unpin"


@router.get("/tasks")
def api_list_tasks(state: Optional[str] = None):
    states = {state} if state else None
    tasks = list_tasks(states=states)
    return {"tasks": tasks}


@router.get("/tasks/{task_id}")
def api_get_task(task_id: str):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks")
def api_create_task(body: TaskCreate):
    config = get_config()
    task_dict = {
        "title": body.title,
        "sender": body.sender or "me",
        "source": body.source or "manual",
        "direction": body.direction or "inbound",
        "state_history": [
            {"state": "open", "reason": "Created via web", "date": datetime.now().isoformat()}
        ],
    }
    if body.due_hint:
        task_dict["due_hint"] = body.due_hint
    if body.description:
        task_dict["description"] = body.description
    if body.priority:
        priority_map = {"high": 20, "medium": 10, "low": 0}
        task_dict["user_priority"] = priority_map.get(body.priority.lower(), 0)

    task_id = add_task(task_dict, config)

    # Auto-pin manual tasks
    if task_dict.get("source") == "manual":
        analytics = get_analytics()
        pin_task(task_id, analytics)

    # Score the new task
    task = get_task(task_id)
    analytics = get_analytics()
    score_task(task, config, analytics)
    update_task(task_id, task)

    return {"id": task_id, "task": task}


@router.patch("/tasks/{task_id}")
def api_update_task(task_id: str, body: TaskUpdate):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = update_task(task_id.upper(), updates)
    # Rescore if priority changed
    if 'user_priority' in updates and updated:
        config = get_config()
        analytics = get_analytics()
        score_task(updated, config, analytics)
        update_task(task_id.upper(), updated)
    return updated


@router.post("/tasks/{task_id}/close")
def api_close_task(task_id: str):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["state"] == "closed":
        raise HTTPException(status_code=400, detail="Already closed")
    transition_task(task, "closed", "Closed via web dashboard")
    task["closed_by"] = "user"
    update_task(task_id.upper(), task)
    return {"status": "closed", "task": task}


@router.post("/tasks/{task_id}/reopen")
def api_reopen_task(task_id: str):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["state"] != "closed":
        raise HTTPException(status_code=400, detail="Task is not closed")
    transition_task(task, "open", "Reopened via web dashboard")
    task.pop("closed_by", None)
    config = get_config()
    analytics = get_analytics()
    score_task(task, config, analytics)
    update_task(task_id.upper(), task)
    return {"status": "reopened", "task": task}


@router.post("/tasks/{task_id}/pin")
def api_pin_task(task_id: str):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    analytics = get_analytics()
    pin_task(task_id.upper(), analytics)
    config = get_config()
    score_task(task, config, analytics)
    update_task(task_id.upper(), task)
    return {"status": "pinned", "task": task}


@router.post("/tasks/{task_id}/unpin")
def api_unpin_task(task_id: str):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    analytics = get_analytics()
    unpin_task(task_id.upper(), analytics)
    config = get_config()
    score_task(task, config, analytics)
    update_task(task_id.upper(), task)
    return {"status": "unpinned", "task": task}


@router.post("/tasks/{task_id}/transition")
def api_transition_task(task_id: str, body: TransitionRequest):
    task = get_task(task_id.upper())
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    success = transition_task(task, body.state, body.reason or f"Transitioned to {body.state} via web")
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid transition from {task['state']} to {body.state}")
    if body.state == "closed":
        task["closed_by"] = "user"
    update_task(task_id.upper(), task)
    return {"status": "transitioned", "task": task}


@router.post("/tasks/bulk")
def api_bulk_action(body: BulkAction):
    results = []
    config = get_config()
    analytics = get_analytics()
    for tid in body.ids:
        task = get_task(tid.upper())
        if not task:
            results.append({"id": tid, "error": "not found"})
            continue
        if body.action == "close":
            if task["state"] != "closed":
                transition_task(task, "closed", "Bulk closed via web")
                task["closed_by"] = "user"
                update_task(tid.upper(), task)
            results.append({"id": tid, "status": "closed"})
        elif body.action == "pin":
            pin_task(tid.upper(), analytics)
            score_task(task, config, analytics)
            update_task(tid.upper(), task)
            results.append({"id": tid, "status": "pinned"})
        elif body.action == "unpin":
            unpin_task(tid.upper(), analytics)
            score_task(task, config, analytics)
            update_task(tid.upper(), task)
            results.append({"id": tid, "status": "unpinned"})
    return {"results": results}
