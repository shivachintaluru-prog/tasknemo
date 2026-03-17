"""Dedup — normalize, hash, jaccard, cross-source match/merge."""

import hashlib
from datetime import datetime


STOP_WORDS = {
    "a", "an", "the", "to", "for", "of", "in", "on", "at", "is", "it",
    "and", "or", "but", "with", "by", "from", "up", "about", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "out", "off", "over", "under", "again", "further", "then", "once",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "this", "that", "these",
    "those", "am", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "shall", "should",
    "may", "might", "must", "can", "could", "not", "no", "nor", "so",
    "too", "very", "just", "also",
}


def normalize_text(text):
    """Lowercase and strip whitespace."""
    return text.strip().lower()


def normalize_title_words(title):
    """Lowercase, remove stop words, sort remaining words."""
    words = normalize_text(title).split()
    filtered = sorted(w for w in words if w not in STOP_WORDS)
    return " ".join(filtered)


def compute_dedup_hash(sender, title, extracted_date):
    """SHA-256 hash of sender|normalized_title|date, truncated to 16 chars."""
    norm_sender = normalize_text(sender)
    norm_title = normalize_title_words(title)
    norm_date = normalize_text(extracted_date)
    payload = f"{norm_sender}|{norm_title}|{norm_date}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def jaccard_similarity(set_a, set_b):
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def fuzzy_match(new_title, existing_tasks, threshold=0.7):
    """Check if new_title fuzzy-matches any existing task title."""
    new_words = set(normalize_title_words(new_title).split())
    for task in existing_tasks:
        existing_words = set(normalize_title_words(task["title"]).split())
        if jaccard_similarity(new_words, existing_words) >= threshold:
            return task
    return None


def is_duplicate(new_hash, existing_tasks):
    """Check if a hash already exists in the task store."""
    return any(t.get("dedup_hash") == new_hash for t in existing_tasks)


# ---------------------------------------------------------------------------
# Cross-Source Matching
# ---------------------------------------------------------------------------


def find_cross_source_match(new_task_dict, existing_tasks, threshold=0.5):
    """Find a matching task across sources using sender + fuzzy title."""
    new_sender = normalize_text(new_task_dict.get("sender", ""))
    new_title = new_task_dict.get("title", "")
    if not new_sender or not new_title:
        return None

    candidates = [
        t for t in existing_tasks
        if normalize_text(t.get("sender", "")) == new_sender
    ]
    if not candidates:
        return None

    return fuzzy_match(new_title, candidates, threshold=threshold)


def merge_cross_source_signal(existing_task, new_source, new_link):
    """Merge a cross-source signal into an existing task."""
    existing_task["times_seen"] = existing_task.get("times_seen", 1) + 1
    existing_task["updated"] = datetime.now().isoformat()

    meta = existing_task.setdefault("source_metadata", {})
    alt_links = meta.setdefault("alternate_links", [])

    link_entry = {"source": new_source, "link": new_link}
    if not any(a.get("link") == new_link for a in alt_links):
        alt_links.append(link_entry)


def merge_duplicates(tasks):
    """Merge duplicate non-closed tasks sharing thread_id or meeting_title."""
    from collections import defaultdict

    non_closed = [t for t in tasks if t.get("state") != "closed"]

    groups = defaultdict(list)
    for t in non_closed:
        thread = t.get("thread_id", "")
        meeting = t.get("source_metadata", {}).get("meeting_title", "")
        sender = normalize_text(t.get("sender", ""))
        if thread:
            groups[f"thread:{thread}"].append(t)
        if meeting:
            groups[f"meeting:{meeting}"].append(t)
        if sender:
            groups[f"sender:{sender}"].append(t)

    merged_results = []
    already_merged = set()

    for _key, group in groups.items():
        if len(group) < 2:
            continue

        group.sort(key=lambda x: x.get("created", ""), reverse=True)

        for i in range(len(group)):
            if group[i]["id"] in already_merged:
                continue
            merged_ids = []
            words_i = set(normalize_title_words(group[i].get("title", "")).split())
            for j in range(i + 1, len(group)):
                if group[j]["id"] in already_merged:
                    continue
                words_j = set(normalize_title_words(group[j].get("title", "")).split())
                if jaccard_similarity(words_i, words_j) >= 0.7:
                    older = group[j]
                    older["state"] = "closed"
                    older["state_history"] = older.get("state_history", [])
                    older["state_history"].append({
                        "state": "closed",
                        "reason": f"Merged into {group[i]['id']}",
                        "date": datetime.now().isoformat(),
                    })
                    older["updated"] = datetime.now().isoformat()
                    merged_ids.append(older["id"])
                    already_merged.add(older["id"])

            if merged_ids:
                keeper = group[i]
                desc = keeper.get("description", "") or ""
                merge_note = "Merged: " + ", ".join(merged_ids)
                if desc:
                    keeper["description"] = desc + " | " + merge_note
                else:
                    keeper["description"] = merge_note
                merged_results.append((keeper["id"], merged_ids))
                already_merged.add(keeper["id"])

    return merged_results
