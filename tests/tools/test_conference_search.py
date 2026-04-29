"""Tests for conference search functionality."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from top_paper_mcp_server.tools.conference_search import (
    handle_conference_search,
    handle_unified_search,
    ConferencePriority,
    CONFERENCE_PRIORITY,
    CONFERENCE_CATEGORIES,
    CONFERENCE_SOURCE_MAP,
    _get_conference_priority,
    _get_category,
    _get_source,
)
from top_paper_mcp_server.tools.conferences.base import PaperMetadata


class MockConferenceSource:
    """Mock conference source for testing."""

    def __init__(self, name="mock"):
        self._name = name

    @property
    def name(self):
        return self._name

    async def search(self, query, conference, year, max_results=10):
        return [
            PaperMetadata(
                paper_id="12345",
                title=f"Test Paper for {conference} {year}",
                authors=["Test Author"],
                abstract="Test abstract content",
                year=year,
                conference=conference,
                url=f"https://example.com/{conference}/{year}/12345",
                pdf_url=f"https://example.com/{conference}/{year}/12345.pdf",
            )
        ]

    async def get_paper(self, paper_id, conference):
        return PaperMetadata(
            paper_id=paper_id,
            title=f"Test Paper {paper_id}",
            authors=["Test Author"],
            abstract="Test abstract",
            year=2024,
            conference=conference,
            url=f"https://example.com/{conference}/{paper_id}",
            pdf_url=f"https://example.com/{conference}/{paper_id}.pdf",
        )

    async def download_paper(self, paper_id, conference):
        return {
            "status": "success",
            "content": f"Full paper content for {paper_id} from {conference}",
            "source": "html",
            "year": 2024,
        }


@pytest.fixture
def mock_sources():
    """Patch all conference sources with mock."""
    with (
        patch(
            "top_paper_mcp_server.tools.conference_search.cvf_source",
            MockConferenceSource("cvf"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_search.openreview_source",
            MockConferenceSource("openreview"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_search.eccv_source",
            MockConferenceSource("eccv"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_search.acm_source",
            MockConferenceSource("acm"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_search.mlanthology_source",
            MockConferenceSource("mlanthology"),
        ),
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
    """Test that every conference in SOURCE_MAP has a priority."""
    for conf in CONFERENCE_SOURCE_MAP:
        assert conf in CONFERENCE_PRIORITY, f"{conf} missing priority"


def test_conference_categories_coverage():
    """Test that all conferences in SOURCE_MAP (except ACM) are categorized."""
    all_categorized = set()
    for confs in CONFERENCE_CATEGORIES.values():
        all_categorized.update(confs)
    for conf in CONFERENCE_PRIORITY:
        if conf == "ACM":
            continue
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
async def test_single_conference_search(mock_sources):
    """Test searching a single conference."""
    result = await handle_conference_search(
        {"query": "transformer", "conference": "CVPR", "year": 2024, "max_results": 5}
    )

    content = json.loads(result[0].text)
    assert content["total_results"] >= 1
    assert content["conference"] == "CVPR"
    assert content["year"] == 2024
    assert len(content["papers"]) >= 1
    paper = content["papers"][0]
    assert "CVPR" in paper["title"]


@pytest.mark.asyncio
async def test_search_missing_params():
    """Test search without required params returns error."""
    result = await handle_conference_search(
        {"query": "test", "conference": "", "year": None}
    )

    content = json.loads(result[0].text)
    assert "error" in content


@pytest.mark.asyncio
async def test_search_all_concurrent(mock_sources):
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
async def test_search_by_category(mock_sources):
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
async def test_search_max_results_capped(mock_sources):
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
async def test_unified_search_all(mock_sources):
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
async def test_unified_search_by_category(mock_sources):
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
async def test_unified_search_total_results_capped(mock_sources):
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
async def test_unified_search_max_per_conference_capped(mock_sources):
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


# ---------------------------------------------------------------------------
# _get_source Tests
# ---------------------------------------------------------------------------


def test_get_source_valid():
    """Test getting source for valid conferences."""
    source = _get_source("CVPR")
    assert source is not None

    source = _get_source("NeurIPS")
    assert source is not None

    source = _get_source("ICLR")
    assert source is not None


def test_get_source_invalid():
    """Test getting source for invalid conference raises ValueError."""
    with pytest.raises(ValueError, match="Unknown conference"):
        _get_source("INVALID_CONF")
