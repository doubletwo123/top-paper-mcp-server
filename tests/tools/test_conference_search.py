"""Tests for conference search functionality — dual-path (arXiv + OpenReview)."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from top_paper_mcp_server.tools.conference_search import (
    handle_conference_search,
    handle_unified_search,
    ConferencePriority,
    CONFERENCE_PRIORITY,
    CONFERENCE_CATEGORIES,
    _get_conference_priority,
    _get_category,
)
from top_paper_mcp_server.tools.conferences.base import PaperMetadata

MOCK_PAPER = PaperMetadata(
    paper_id="or_12345",
    title="Test Paper for CVPR 2024",
    authors=["Test Author"],
    abstract="Test abstract content",
    year=2024,
    conference="CVPR",
    url="https://openreview.net/forum?id=or_12345",
    pdf_url="https://openreview.net/pdf?id=or_12345",
)

MOCK_ARXIV_RESULT = {
    "id": "2401.12345",
    "title": "Test Paper for CVPR 2024",
    "authors": ["Test Author"],
    "abstract": "[EXTERNAL CONTENT] Test abstract content",
    "categories": ["cs.CV"],
    "published": "2024-01-15T00:00:00Z",
    "url": "http://arxiv.org/pdf/2401.12345",
    "resource_uri": "arxiv://2401.12345",
}


@pytest.fixture
def mock_openreview():
    """Patch OpenReview source with mock."""
    mock_source = MagicMock()
    mock_source.search = AsyncMock(return_value=[MOCK_PAPER])
    with patch(
        "top_paper_mcp_server.tools.conference_search.openreview_source",
        mock_source,
    ):
        yield mock_source


@pytest.fixture
def mock_arxiv():
    """Patch arXiv search with mock."""
    with patch(
        "top_paper_mcp_server.tools.conference_search._raw_arxiv_search",
        AsyncMock(return_value=[MOCK_ARXIV_RESULT]),
    ):
        yield


# ---------------------------------------------------------------------------
# ConferencePriority Tests
# ---------------------------------------------------------------------------


def test_conference_priority_ordering():
    """Test that conference priorities follow expected ordering."""
    assert ConferencePriority.CVPR > ConferencePriority.ICCV
    assert ConferencePriority.ICCV > ConferencePriority.NeurIPS
    assert ConferencePriority.NeurIPS > ConferencePriority.ICLR
    assert ConferencePriority.ICLR > ConferencePriority.ICML
    assert ConferencePriority.ICML > ConferencePriority.ECCV


def test_all_conferences_have_priority():
    """Test that every conference in CONFERENCE_CATEGORIES has a priority."""
    for confs in CONFERENCE_CATEGORIES.values():
        for conf in confs:
            assert conf in CONFERENCE_PRIORITY, f"{conf} missing priority"


def test_conference_categories_coverage():
    """Test that all conferences in CONFERENCE_PRIORITY are categorized."""
    all_categorized = set()
    for confs in CONFERENCE_CATEGORIES.values():
        all_categorized.update(confs)
    for conf in CONFERENCE_PRIORITY:
        assert conf in all_categorized, f"{conf} not categorized"


def test_get_conference_priority():
    """Test priority lookup function."""
    assert _get_conference_priority("CVPR") == 100
    assert _get_conference_priority("cvpr") == 100
    assert _get_conference_priority("NeurIPS") == 90
    assert _get_conference_priority("unknown") == 0


def test_get_category():
    """Test category lookup function."""
    assert _get_category("CVPR") == "computer_vision"
    assert _get_category("NeurIPS") == "machine_learning"
    assert _get_category("ACL") == "nlp"
    assert _get_category("AAAI") == "ai"
    assert _get_category("unknown") is None


# ---------------------------------------------------------------------------
# handle_conference_search Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_conference_search(mock_openreview, mock_arxiv):
    """Test searching a single conference with dual-path."""
    result = await handle_conference_search(
        {"query": "transformer", "conference": "CVPR", "year": 2024, "max_results": 5}
    )

    content = json.loads(result[0].text)
    assert content["total_results"] >= 1
    assert content["conference"] == "CVPR"
    assert content["year"] == 2024
    assert len(content["papers"]) >= 1


@pytest.mark.asyncio
async def test_search_missing_params():
    """Test search without required params returns error."""
    result = await handle_conference_search(
        {"query": "test", "conference": "", "year": None}
    )

    content = json.loads(result[0].text)
    assert "error" in content


@pytest.mark.asyncio
async def test_search_all_concurrent(mock_openreview, mock_arxiv):
    """Test search_all=True searches multiple conferences concurrently."""
    result = await handle_conference_search(
        {
            "query": "attention",
            "conference": "",
            "year": 2024,
            "search_all": True,
            "conferences": ["CVPR", "NeurIPS"],
            "max_results": 5,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content
    assert "conference_results" in content


@pytest.mark.asyncio
async def test_search_by_category(mock_openreview, mock_arxiv):
    """Test search_all with category filter."""
    result = await handle_conference_search(
        {
            "query": "vision",
            "conference": "",
            "year": 2024,
            "search_all": True,
            "categories": ["computer_vision"],
            "max_results": 5,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content


@pytest.mark.asyncio
async def test_search_no_valid_conferences():
    """Test search with invalid conference list."""
    result = await handle_conference_search(
        {
            "query": "test",
            "conference": "",
            "year": 2024,
            "search_all": True,
            "conferences": ["INVALID_CONF"],
            "max_results": 5,
        }
    )

    content = json.loads(result[0].text)
    assert "error" in content


@pytest.mark.asyncio
async def test_search_max_results_capped(mock_openreview, mock_arxiv):
    """Test that max_results is capped at 50."""
    result = await handle_conference_search(
        {
            "query": "test",
            "conference": "CVPR",
            "year": 2024,
            "max_results": 1000,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content


# ---------------------------------------------------------------------------
# handle_unified_search Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unified_search_all(mock_openreview, mock_arxiv):
    """Test unified search across all conferences."""
    result = await handle_unified_search(
        {
            "query": "deep learning",
            "year": 2024,
            "conferences": ["CVPR", "NeurIPS"],
            "max_results_per_conference": 3,
            "total_results": 10,
        }
    )

    content = json.loads(result[0].text)
    assert content["total_results"] >= 1
    assert "papers" in content
    assert "conference_results" in content


@pytest.mark.asyncio
async def test_unified_search_by_category(mock_openreview, mock_arxiv):
    """Test unified search filtered by category."""
    result = await handle_unified_search(
        {
            "query": "object detection",
            "year": 2024,
            "categories": ["computer_vision"],
            "max_results_per_conference": 2,
            "total_results": 5,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content


@pytest.mark.asyncio
async def test_unified_search_no_query():
    """Test unified search requires query."""
    result = await handle_unified_search(
        {"query": "", "year": 2024, "total_results": 5}
    )

    content = json.loads(result[0].text)
    assert "error" in content


@pytest.mark.asyncio
async def test_unified_search_no_valid_conferences():
    """Test unified search with invalid conferences."""
    result = await handle_unified_search(
        {
            "query": "test",
            "year": 2024,
            "conferences": ["INVALID"],
            "max_results_per_conference": 5,
            "total_results": 10,
        }
    )

    content = json.loads(result[0].text)
    assert "error" in content


@pytest.mark.asyncio
async def test_unified_search_total_results_capped(mock_openreview, mock_arxiv):
    """Test that total_results is capped at 100."""
    result = await handle_unified_search(
        {
            "query": "test",
            "year": 2024,
            "conferences": ["CVPR"],
            "max_results_per_conference": 5,
            "total_results": 5000,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content


@pytest.mark.asyncio
async def test_unified_search_max_per_conference_capped(mock_openreview, mock_arxiv):
    """Test that max_results_per_conference is capped at 20."""
    result = await handle_unified_search(
        {
            "query": "test",
            "year": 2024,
            "conferences": ["CVPR"],
            "max_results_per_conference": 100,
            "total_results": 20,
        }
    )

    content = json.loads(result[0].text)
    assert "papers" in content
