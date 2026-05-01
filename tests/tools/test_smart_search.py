"""Tests for smart search and feedback recording."""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from top_paper_mcp_server.tools.smart_search import (
    handle_smart_search,
    handle_record_feedback,
    _search_session_log,
    _log_search_results,
)


@pytest.fixture(autouse=True)
def clear_session_log():
    """Clear session log before each test."""
    _search_session_log.clear()
    yield
    _search_session_log.clear()


@pytest.fixture
def mock_arxiv_results():
    """Mock arXiv search to return consistent results."""
    results = [
        {"id": "2401.00001", "title": "Register Tokens for Vision Transformers", "abstract": "Test abstract"},
        {"id": "2401.00002", "title": "Attention Is All You Need", "abstract": "Test abstract 2"},
    ]
    with patch(
        "top_paper_mcp_server.tools.smart_search._raw_arxiv_search",
        AsyncMock(return_value=results),
    ):
        yield results


@pytest.fixture
def mock_preference_store(tmp_path):
    """Mock PreferenceStore to use temp directory."""
    mock_instance = MagicMock()
    mock_instance.load = MagicMock()
    mock_instance.interaction_count = 0
    mock_instance.select_terms = MagicMock(
        side_effect=lambda candidates, original_query, top_k=3: candidates[:top_k]
    )
    mock_instance.record_reward = MagicMock()
    with patch(
        "top_paper_mcp_server.tools.smart_search.PreferenceStore",
        return_value=mock_instance,
    ):
        yield mock_instance


# ---------------------------------------------------------------------------
# _log_search_results Tests
# ---------------------------------------------------------------------------


def test_log_search_results():
    papers = [
        {"id": "paper1", "title": "A"},
        {"id": "paper2", "title": "B"},
    ]
    _log_search_results(papers, ["term1", "term2"])
    assert set(_search_session_log["paper1"]) == {"term1", "term2"}
    assert set(_search_session_log["paper2"]) == {"term1", "term2"}


def test_log_search_results_merges():
    _search_session_log["paper1"] = ["old_term"]
    _log_search_results([{"id": "paper1"}], ["new_term"])
    assert "old_term" in _search_session_log["paper1"]
    assert "new_term" in _search_session_log["paper1"]


def test_log_search_results_empty():
    _log_search_results([], ["term"])
    assert len(_search_session_log) == 0


# ---------------------------------------------------------------------------
# handle_smart_search Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_search_no_query():
    result = await handle_smart_search({})
    content = json.loads(result[0].text)
    assert content["status"] == "error"


@pytest.mark.asyncio
async def test_smart_search_with_expansion(mock_arxiv_results, mock_preference_store):
    result = await handle_smart_search({"query": "register", "max_results": 5})
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert len(content["expanded_queries"]) >= 1
    assert content["total_results"] >= 1
    assert "extracted_keywords" in content


@pytest.mark.asyncio
async def test_smart_search_no_expand(mock_arxiv_results, mock_preference_store):
    result = await handle_smart_search({"query": "register", "expand": False, "max_results": 5})
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["expanded_queries"] == ["register"]


@pytest.mark.asyncio
async def test_smart_search_with_pre_expanded_queries(mock_arxiv_results, mock_preference_store):
    result = await handle_smart_search({
        "query": "register",
        "queries": ["register tokens", "registration", "learnable tokens"],
        "max_results": 5,
    })
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert len(content["expanded_queries"]) == 3


@pytest.mark.asyncio
async def test_smart_search_logs_for_feedback(mock_arxiv_results, mock_preference_store):
    await handle_smart_search({"query": "register", "max_results": 5})
    # Session log should have entries for returned papers
    assert len(_search_session_log) > 0


@pytest.mark.asyncio
async def test_smart_search_with_conference(mock_arxiv_results, mock_preference_store):
    """Conference mode should use dual-path search."""
    with patch(
        "top_paper_mcp_server.tools.smart_search._run_conference_queries",
        AsyncMock(return_value=[[{"id": "c1", "title": "Conf Paper", "abstract": "test"}]]),
    ):
        result = await handle_smart_search({
            "query": "register",
            "conference": "CVPR",
            "year": 2025,
            "max_results": 5,
        })
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content.get("conference") == "CVPR"


# ---------------------------------------------------------------------------
# handle_record_feedback Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_feedback_missing_paper_id():
    result = await handle_record_feedback({})
    content = json.loads(result[0].text)
    assert content["status"] == "error"


@pytest.mark.asyncio
async def test_record_feedback_invalid_action():
    result = await handle_record_feedback({"paper_id": "123", "action": "click"})
    content = json.loads(result[0].text)
    assert content["status"] == "error"


@pytest.mark.asyncio
async def test_record_feedback_no_session():
    """If paper not in session log, feedback is not recorded."""
    result = await handle_record_feedback({"paper_id": "unknown", "action": "download"})
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["terms_found"] is False


@pytest.mark.asyncio
async def test_record_feedback_success():
    """Feedback recorded when paper is in session log."""
    _search_session_log["paper123"] = ["register", "tokens"]

    with patch(
        "top_paper_mcp_server.tools.smart_search.PreferenceStore"
    ) as MockStore:
        mock_instance = MagicMock()
        mock_instance.load = MagicMock()
        mock_instance.interaction_count = 1
        mock_instance.record_reward = MagicMock()
        MockStore.return_value = mock_instance

        result = await handle_record_feedback({
            "paper_id": "paper123",
            "action": "download",
        })

    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["paper_id"] == "paper123"
    assert content["action"] == "download"
    assert content["reward"] == 1.0
    assert "register" in content["terms_reinforced"]


@pytest.mark.asyncio
async def test_record_feedback_read():
    """Read action gives higher reward."""
    _search_session_log["paper456"] = ["attention"]

    with patch(
        "top_paper_mcp_server.tools.smart_search.PreferenceStore"
    ) as MockStore:
        mock_instance = MagicMock()
        mock_instance.load = MagicMock()
        mock_instance.interaction_count = 1
        mock_instance.record_reward = MagicMock()
        MockStore.return_value = mock_instance

        result = await handle_record_feedback({
            "paper_id": "paper456",
            "action": "read",
        })

    content = json.loads(result[0].text)
    assert content["reward"] == 2.0
