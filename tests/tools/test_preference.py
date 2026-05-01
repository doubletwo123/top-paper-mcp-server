"""Tests for the preference memory store."""

import pytest
import json
from pathlib import Path
from top_paper_mcp_server.tools.preference import (
    PreferenceStore,
    compute_reward,
    _DEFAULT_WEIGHT,
)


@pytest.fixture
def store(tmp_path):
    """Create a PreferenceStore with a temp file."""
    path = tmp_path / "preferences.json"
    return PreferenceStore(path=path)


# ---------------------------------------------------------------------------
# compute_reward Tests
# ---------------------------------------------------------------------------


def test_compute_reward_download():
    assert compute_reward({}, "download") == 1.0


def test_compute_reward_read():
    assert compute_reward({}, "read") == 2.0


def test_compute_reward_shown():
    assert compute_reward({}, "search_shown") == -0.1


def test_compute_reward_unknown():
    assert compute_reward({}, "unknown") == 0.0


# ---------------------------------------------------------------------------
# PreferenceStore basic Tests
# ---------------------------------------------------------------------------


def test_store_initial_state(store):
    assert store.interaction_count == 0
    assert store.term_weights == {}
    assert store.category_weights == {}


def test_store_load_nonexistent(store):
    store.load()  # should not raise
    assert store.interaction_count == 0


def test_store_save_and_load(store):
    store.record_reward(["attention", "transformer"], 1.0)
    assert store.interaction_count == 1

    # Reload from disk
    store2 = PreferenceStore(path=store._path)
    store2.load()
    assert store2.interaction_count == 1
    assert "attention" in store2.term_weights
    assert "transformer" in store2.term_weights


def test_store_records_category_weights(store):
    store.record_reward(["test"], 1.0, categories=["cs.CV", "cs.AI"])
    assert "cs.CV" in store.category_weights
    assert "cs.AI" in store.category_weights


# ---------------------------------------------------------------------------
# record_reward Tests
# ---------------------------------------------------------------------------


def test_record_reward_updates_weights(store):
    store.record_reward(["attention"], 1.0)
    w = store.term_weights["attention"]
    # w = 0.5 + 0.3 * (1.0 - 0.5) = 0.5 + 0.15 = 0.65
    assert abs(w - 0.65) < 0.01


def test_record_reward_negative(store):
    store.record_reward(["noise"], -0.1)
    w = store.term_weights["noise"]
    # w = 0.5 + 0.3 * (-0.1 - 0.5) = 0.5 - 0.18 = 0.32
    assert abs(w - 0.32) < 0.01


def test_record_reward_increments_count(store):
    store.record_reward(["a"], 1.0)
    store.record_reward(["b"], 1.0)
    store.record_reward(["c"], 1.0)
    assert store.interaction_count == 3


def test_record_reward_learning_rate_decays(store):
    """Learning rate should decrease as interaction count grows."""
    for i in range(20):
        store.record_reward(["term"], 1.0)

    # After 20 interactions, lr should be lower than initial 0.3
    lr = store._learning_rate()
    assert lr < 0.3
    assert lr >= 0.05  # floor


def test_record_reward_empty_terms(store):
    store.record_reward([], 1.0)
    assert store.interaction_count == 0  # no-op


# ---------------------------------------------------------------------------
# select_terms Tests
# ---------------------------------------------------------------------------


def test_select_terms_cold_start(store):
    """With < 5 interactions, should return all candidates."""
    candidates = ["a", "b", "c", "d"]
    selected = store.select_terms(candidates, original_query="a", top_k=3)
    assert selected == ["a", "b", "c"]


def test_select_terms_includes_original(store):
    """Original query should always be in the result."""
    # Warm up with enough interactions
    for _ in range(10):
        store.record_reward(["x"], 1.0)

    candidates = ["original", "variant1", "variant2"]
    selected = store.select_terms(candidates, original_query="original", top_k=2)
    assert "original" in selected


def test_select_terms_empty_candidates(store):
    selected = store.select_terms([], original_query="query", top_k=3)
    assert selected == ["query"]


def test_select_terms_respects_top_k(store):
    candidates = ["a", "b", "c", "d", "e"]
    selected = store.select_terms(candidates, original_query="a", top_k=2)
    assert len(selected) <= 2


def test_select_terms_prefers_high_weight(store):
    """Terms with higher weights should be selected more often."""
    # Build strong preference for "good_term"
    for _ in range(30):
        store.record_reward(["good_term"], 2.0)
        store.record_reward(["bad_term"], -0.1)

    # Run selection many times and count occurrences
    candidates = ["query", "good_term", "bad_term", "neutral"]
    counts = {"good_term": 0, "bad_term": 0, "neutral": 0}
    for _ in range(100):
        selected = store.select_terms(candidates, original_query="query", top_k=2)
        for s in selected:
            if s in counts:
                counts[s] += 1

    # good_term should appear much more often than bad_term
    assert counts["good_term"] > counts["bad_term"]
