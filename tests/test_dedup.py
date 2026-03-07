"""Unit tests for dedup logic: hashing, normalization, fuzzy matching."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import (
    normalize_text,
    normalize_title_words,
    compute_dedup_hash,
    is_duplicate,
    fuzzy_match,
    jaccard_similarity,
)


class TestNormalization:
    def test_normalize_text_strips_and_lowercases(self):
        assert normalize_text("  Hello World  ") == "hello world"

    def test_normalize_text_empty(self):
        assert normalize_text("") == ""

    def test_normalize_title_removes_stop_words(self):
        result = normalize_title_words("Reply to the manager about the update")
        # "reply", "manager", "update" should remain; "to", "the", "about" removed
        assert "reply" in result
        assert "manager" in result
        assert "update" in result
        assert "the" not in result.split()
        assert "to" not in result.split()

    def test_normalize_title_sorts_words(self):
        result = normalize_title_words("Send update to Rahul")
        words = result.split()
        assert words == sorted(words)

    def test_normalize_title_empty(self):
        assert normalize_title_words("") == ""

    def test_normalize_title_all_stop_words(self):
        assert normalize_title_words("the a an to for") == ""


class TestDedupHash:
    def test_same_input_same_hash(self):
        h1 = compute_dedup_hash("Alice", "Reply to manager", "2026-03-01")
        h2 = compute_dedup_hash("Alice", "Reply to manager", "2026-03-01")
        assert h1 == h2

    def test_hash_is_16_chars(self):
        h = compute_dedup_hash("Bob", "Some task", "2026-03-01")
        assert len(h) == 16

    def test_case_insensitive(self):
        h1 = compute_dedup_hash("Alice Smith", "Reply to Manager", "2026-03-01")
        h2 = compute_dedup_hash("alice smith", "reply to manager", "2026-03-01")
        assert h1 == h2

    def test_different_sender_different_hash(self):
        h1 = compute_dedup_hash("Alice", "Some task", "2026-03-01")
        h2 = compute_dedup_hash("Bob", "Some task", "2026-03-01")
        assert h1 != h2

    def test_different_date_different_hash(self):
        h1 = compute_dedup_hash("Alice", "Some task", "2026-03-01")
        h2 = compute_dedup_hash("Alice", "Some task", "2026-03-02")
        assert h1 != h2

    def test_stop_word_order_invariant(self):
        # "Send update to Rahul" and "Update send to Rahul" normalize the same
        h1 = compute_dedup_hash("Me", "Send update to Rahul", "2026-03-01")
        h2 = compute_dedup_hash("Me", "Update send to Rahul", "2026-03-01")
        assert h1 == h2


class TestIsDuplicate:
    def test_duplicate_found(self):
        tasks = [{"dedup_hash": "abc123def456abcd"}, {"dedup_hash": "xyz789"}]
        assert is_duplicate("abc123def456abcd", tasks) is True

    def test_no_duplicate(self):
        tasks = [{"dedup_hash": "abc123def456abcd"}]
        assert is_duplicate("different_hash_00", tasks) is False

    def test_empty_store(self):
        assert is_duplicate("anything", []) is False


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert abs(sim - 0.5) < 0.01  # 2/4

    def test_both_empty(self):
        assert jaccard_similarity(set(), set()) == 1.0

    def test_one_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0


class TestFuzzyMatch:
    def test_match_found(self):
        existing = [
            {"title": "Reply to Rahul about status update", "id": "TASK-001"},
            {"title": "Share tracker with team", "id": "TASK-002"},
        ]
        match = fuzzy_match("Reply to Rahul: status update", existing, threshold=0.5)
        assert match is not None
        assert match["id"] == "TASK-001"

    def test_no_match(self):
        existing = [
            {"title": "Reply to Rahul about status update", "id": "TASK-001"},
        ]
        match = fuzzy_match("Completely different task about budgets", existing)
        assert match is None

    def test_empty_store(self):
        assert fuzzy_match("Any title", []) is None

    def test_threshold_boundary(self):
        existing = [{"title": "word1 word2 word3 word4", "id": "TASK-001"}]
        # Only 1 word overlap out of ~6 unique words → low similarity
        match = fuzzy_match("word1 something else entirely", existing, threshold=0.8)
        assert match is None
