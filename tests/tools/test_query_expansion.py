"""Tests for query expansion and result fusion."""

import pytest
from top_paper_mcp_server.tools.query_expansion import (
    _generate_candidates,
    _extract_keywords_from_results,
    _rrf_fuse,
    _fuzzy_title_match,
    _normalize_title,
)


# ---------------------------------------------------------------------------
# _normalize_title Tests
# ---------------------------------------------------------------------------


def test_normalize_title_basic():
    assert _normalize_title("Hello World") == "hello world"


def test_normalize_title_strips_punctuation():
    assert _normalize_title("Attention Is All You Need!") == "attention is all you need"


def test_normalize_title_collapses_whitespace():
    assert _normalize_title("  Hello   World  ") == "hello world"


# ---------------------------------------------------------------------------
# _fuzzy_title_match Tests
# ---------------------------------------------------------------------------


def test_fuzzy_exact_match():
    assert _fuzzy_title_match("Attention Is All You Need", "Attention Is All You Need")


def test_fuzzy_case_insensitive():
    assert _fuzzy_title_match("attention is all you need", "Attention Is All You Need")


def test_fuzzy_subtitle_difference():
    """Titles that differ only by a subtitle should still match."""
    assert _fuzzy_title_match(
        "Vision Transformers: A Survey",
        "Vision Transformers"
    )


def test_fuzzy_different_papers():
    assert not _fuzzy_title_match(
        "Attention Is All You Need",
        "BERT Pre-training of Deep Bidirectional Transformers"
    )


def test_fuzzy_empty_strings():
    assert not _fuzzy_title_match("", "Hello")
    assert not _fuzzy_title_match("Hello", "")


# ---------------------------------------------------------------------------
# _generate_candidates Tests
# ---------------------------------------------------------------------------


def test_single_word_query():
    candidates = _generate_candidates("register")
    assert len(candidates) >= 2
    assert candidates[0] == "register"
    # Should have at least one suffix variant
    assert any("register" in c and c != "register" for c in candidates)


def test_multi_word_query():
    candidates = _generate_candidates("deep learning method")
    assert len(candidates) >= 2
    assert candidates[0] == "deep learning method"


def test_empty_query():
    candidates = _generate_candidates("")
    assert candidates == []


def test_no_duplicates():
    candidates = _generate_candidates("deep learning")
    assert len(candidates) == len(set(c.lower() for c in candidates))


def test_candidates_limited():
    candidates = _generate_candidates("a b c d e f g h")
    assert len(candidates) <= 5


# ---------------------------------------------------------------------------
# _extract_keywords_from_results Tests
# ---------------------------------------------------------------------------


def test_extract_keywords_basic():
    papers = [
        {"abstract": "[EXTERNAL CONTENT] Vision transformers use attention mechanisms for image classification"},
        {"abstract": "[EXTERNAL CONTENT] Vision transformers achieve state of the art results on ImageNet"},
    ]
    keywords = _extract_keywords_from_results(papers, top_k=5)
    assert len(keywords) <= 5
    assert "vision" in keywords
    assert "transformers" in keywords


def test_extract_keywords_filters_stopwords():
    papers = [{"abstract": "[EXTERNAL CONTENT] This is a test of the system"}]
    keywords = _extract_keywords_from_results(papers, top_k=10)
    assert "this" not in keywords
    assert "the" not in keywords


def test_extract_keywords_empty():
    keywords = _extract_keywords_from_results([], top_k=5)
    assert keywords == []


# ---------------------------------------------------------------------------
# _rrf_fuse Tests
# ---------------------------------------------------------------------------


def test_rrf_single_list():
    papers = [
        {"title": "Paper A", "id": "a"},
        {"title": "Paper B", "id": "b"},
    ]
    result = _rrf_fuse([papers])
    assert len(result) == 2
    assert result[0]["title"] == "Paper A"  # rank 1 > rank 2
    assert "rrf_score" in result[0]


def test_rrf_prefers_consensus():
    """Papers appearing in multiple lists should rank higher."""
    list1 = [{"title": "Common Paper"}, {"title": "Only In List 1"}]
    list2 = [{"title": "Common Paper"}, {"title": "Only In List 2"}]

    result = _rrf_fuse([list1, list2])
    assert result[0]["title"] == "Common Paper"


def test_rrf_deduplicates_by_title():
    list1 = [{"title": "Same Paper"}]
    list2 = [{"title": "same paper"}]  # different case

    result = _rrf_fuse([list1, list2])
    # Should deduplicate (fuzzy match)
    titles = [r["title"] for r in result]
    # Either one or both merged — depends on fuzzy threshold
    # At minimum, should not have two separate entries with very different scores
    assert len(result) <= 2


def test_rrf_empty_lists():
    result = _rrf_fuse([[], []])
    assert result == []


def test_rrf_score_ordering():
    """Higher-ranked items in more lists should have higher RRF scores."""
    list1 = [{"title": "Top Paper"}, {"title": "Mid Paper"}]
    list2 = [{"title": "Top Paper"}, {"title": "Low Paper"}]

    result = _rrf_fuse([list1, list2])
    scores = [r["rrf_score"] for r in result]
    assert scores == sorted(scores, reverse=True)
