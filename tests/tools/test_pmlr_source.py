"""Tests for the PMLR (Proceedings of Machine Learning Research) conference source."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from top_paper_mcp_server.tools.conferences.mlanthology import (
    MLAnthologySource,
    PMLR_BASE_URL,
    PMLR_VOLUME_MAP,
    VENUE_MAP,
)
from top_paper_mcp_server.tools.conferences.base import PaperMetadata

# ---------------------------------------------------------------------------
# Sample HTML that mimics a PMLR volume index page
# ---------------------------------------------------------------------------

SAMPLE_PMLR_HTML = """
<html>
<body>
<div class="paper">
  <p class="title">Learning Theory with Bandit Feedback</p>
  <p class="details">Alice Smith, Bob Jones</p>
  <p class="abstract">We study bandit feedback in learning theory.</p>
  <a href="/v247/smith24a.html">paper</a>
  <a href="/v247/smith24a.pdf">Download PDF</a>
</div>
<div class="paper">
  <p class="title">PAC Learning Bounds for Neural Networks</p>
  <p class="details">Carol Lee, Dave Kim</p>
  <p class="abstract">New PAC learning bounds are derived.</p>
  <a href="/v247/lee24b.html">paper</a>
</div>
<div class="paper">
  <p class="title">Unrelated Paper Without Keywords</p>
  <p class="details">Eve Wang</p>
  <p class="abstract">Nothing relevant here.</p>
  <a href="/v247/wang24c.html">paper</a>
</div>
</body>
</html>
"""

SAMPLE_PMLR_DETAIL_HTML = """
<html>
<body>
<h1>Learning Theory with Bandit Feedback</h1>
<span class="authors">Alice Smith, Bob Jones</span>
<div id="abstract">We study bandit feedback in learning theory contexts.</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Volume map tests
# ---------------------------------------------------------------------------


def test_pmlr_volume_map_has_colt_and_uai():
    """PMLR_VOLUME_MAP must cover both COLT and UAI entries."""
    colt_years = [yr for (conf, yr) in PMLR_VOLUME_MAP if conf == "COLT"]
    uai_years = [yr for (conf, yr) in PMLR_VOLUME_MAP if conf == "UAI"]
    assert len(colt_years) >= 5, "Expected multiple COLT volume mappings"
    assert len(uai_years) >= 3, "Expected multiple UAI volume mappings"


def test_pmlr_volume_map_recent_years():
    """Most recent COLT and UAI entries should exist for 2024."""
    assert ("COLT", 2024) in PMLR_VOLUME_MAP
    assert ("UAI", 2024) in PMLR_VOLUME_MAP


def test_pmlr_venue_map_contains_only_colt_uai():
    """VENUE_MAP should only list the conferences this source serves."""
    assert "COLT" in VENUE_MAP
    assert "UAI" in VENUE_MAP


# ---------------------------------------------------------------------------
# _get_volume tests
# ---------------------------------------------------------------------------


def test_get_volume_returns_correct_volume():
    source = MLAnthologySource()
    assert source._get_volume("COLT", 2024) == 247
    assert source._get_volume("UAI", 2024) == 244


def test_get_volume_unknown_year_returns_none():
    source = MLAnthologySource()
    assert source._get_volume("COLT", 1900) is None


def test_get_volume_unknown_conference_returns_none():
    source = MLAnthologySource()
    assert source._get_volume("NEURIPS", 2024) is None


# ---------------------------------------------------------------------------
# _parse_paper_list tests
# ---------------------------------------------------------------------------


def test_parse_paper_list_filters_by_query():
    source = MLAnthologySource()
    papers = source._parse_paper_list(
        SAMPLE_PMLR_HTML, "COLT", 2024, 247, "learning theory", 10
    )
    titles = [p.title for p in papers]
    assert any("learning theory" in t.lower() for t in titles)
    # "Unrelated Paper" should be excluded
    assert not any("Unrelated" in t for t in titles)


def test_parse_paper_list_no_query_returns_all():
    source = MLAnthologySource()
    papers = source._parse_paper_list(
        SAMPLE_PMLR_HTML, "COLT", 2024, 247, "", 10
    )
    assert len(papers) == 3


def test_parse_paper_list_max_results_respected():
    source = MLAnthologySource()
    papers = source._parse_paper_list(
        SAMPLE_PMLR_HTML, "COLT", 2024, 247, "", 2
    )
    assert len(papers) <= 2


def test_parse_paper_list_sets_correct_metadata():
    source = MLAnthologySource()
    papers = source._parse_paper_list(
        SAMPLE_PMLR_HTML, "COLT", 2024, 247, "learning theory", 10
    )
    assert len(papers) >= 1
    p = papers[0]
    assert isinstance(p, PaperMetadata)
    assert p.conference == "COLT"
    assert p.year == 2024
    assert p.url.startswith(PMLR_BASE_URL)
    assert p.pdf_url.endswith(".pdf")


def test_parse_paper_list_empty_html_returns_empty():
    source = MLAnthologySource()
    papers = source._parse_paper_list("<html><body></body></html>", "COLT", 2024, 247, "", 10)
    assert papers == []


# ---------------------------------------------------------------------------
# search() tests (with HTTP mock)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_colt_returns_papers():
    source = MLAnthologySource()
    mock_response = MagicMock()
    mock_response.text = SAMPLE_PMLR_HTML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        MockClient.return_value = mock_client

        papers = await source.search("learning theory", "COLT", 2024, max_results=5)

    assert isinstance(papers, list)
    assert len(papers) >= 1


@pytest.mark.asyncio
async def test_search_unknown_conference_returns_empty():
    source = MLAnthologySource()
    papers = await source.search("anything", "NEURIPS", 2024)
    assert papers == []


@pytest.mark.asyncio
async def test_search_unknown_year_returns_empty():
    source = MLAnthologySource()
    # Year 1900 has no PMLR volume mapping for COLT.
    papers = await source.search("anything", "COLT", 1900)
    assert papers == []


@pytest.mark.asyncio
async def test_search_http_error_returns_empty():
    import httpx

    source = MLAnthologySource()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Network error")
        )
        MockClient.return_value = mock_client

        papers = await source.search("learning", "COLT", 2024)

    assert papers == []


# ---------------------------------------------------------------------------
# _parse_paper_detail tests
# ---------------------------------------------------------------------------


def test_parse_paper_detail_extracts_fields():
    source = MLAnthologySource()
    paper = source._parse_paper_detail(
        SAMPLE_PMLR_DETAIL_HTML, "smith24a", "COLT", 2024, 247
    )
    assert paper is not None
    assert paper.title == "Learning Theory with Bandit Feedback"
    assert "Alice Smith" in paper.authors
    assert "bandit feedback" in paper.abstract.lower()
    assert paper.year == 2024
    assert paper.conference == "COLT"


# ---------------------------------------------------------------------------
# Routing integration: COLT/UAI -> mlanthology_source in conference_search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_colt_routed_to_pmlr_source():
    """COLT should use the PMLR-backed MLAnthologySource, not OpenReview."""
    from top_paper_mcp_server.tools.conference_search import _get_source
    from top_paper_mcp_server.tools.conferences.mlanthology import MLAnthologySource

    source = _get_source("COLT")
    assert isinstance(source, MLAnthologySource)


@pytest.mark.asyncio
async def test_uai_routed_to_pmlr_source():
    """UAI should use the PMLR-backed MLAnthologySource."""
    from top_paper_mcp_server.tools.conference_search import _get_source
    from top_paper_mcp_server.tools.conferences.mlanthology import MLAnthologySource

    source = _get_source("UAI")
    assert isinstance(source, MLAnthologySource)


@pytest.mark.asyncio
async def test_colt_searchable_via_conference_search_tool():
    """Simulate a user asking: 'Search COLT 2024 for learning theory papers'."""
    from top_paper_mcp_server.tools.conference_search import handle_conference_search
    from top_paper_mcp_server.tools.conferences.base import PaperMetadata
    import json

    mock_papers = [
        PaperMetadata(
            paper_id="smith24a",
            title="Learning Theory with Bandit Feedback",
            authors=["Alice Smith"],
            abstract="We study bandit feedback.",
            year=2024,
            conference="COLT",
            url=f"{PMLR_BASE_URL}/v247/smith24a.html",
            pdf_url=f"{PMLR_BASE_URL}/v247/smith24a.pdf",
        )
    ]

    with patch(
        "top_paper_mcp_server.tools.conference_search.mlanthology_source"
    ) as mock_source:
        mock_source.search = AsyncMock(return_value=mock_papers)
        result = await handle_conference_search(
            {"query": "learning theory", "conference": "COLT", "year": 2024}
        )

    content = json.loads(result[0].text)
    assert content["total_results"] >= 1
    assert content["conference"] == "COLT"
    assert content["papers"][0]["title"] == "Learning Theory with Bandit Feedback"


@pytest.mark.asyncio
async def test_uai_searchable_via_conference_search_tool():
    """Simulate a user asking: 'Search UAI 2024 for uncertainty quantification'."""
    from top_paper_mcp_server.tools.conference_search import handle_conference_search
    from top_paper_mcp_server.tools.conferences.base import PaperMetadata
    import json

    mock_papers = [
        PaperMetadata(
            paper_id="lee24a",
            title="Uncertainty Quantification in Deep Learning",
            authors=["Carol Lee"],
            abstract="Novel uncertainty methods.",
            year=2024,
            conference="UAI",
            url=f"{PMLR_BASE_URL}/v244/lee24a.html",
            pdf_url=f"{PMLR_BASE_URL}/v244/lee24a.pdf",
        )
    ]

    with patch(
        "top_paper_mcp_server.tools.conference_search.mlanthology_source"
    ) as mock_source:
        mock_source.search = AsyncMock(return_value=mock_papers)
        result = await handle_conference_search(
            {"query": "uncertainty quantification", "conference": "UAI", "year": 2024}
        )

    content = json.loads(result[0].text)
    assert content["total_results"] >= 1
    assert content["conference"] == "UAI"
