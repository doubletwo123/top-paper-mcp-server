"""Tests for related papers discovery via Semantic Scholar."""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from top_paper_mcp_server.tools.related_papers import (
    handle_related_papers,
    fetch_recommendations,
    fetch_citations_and_references,
    _normalize_arxiv_id,
    _format_paper,
)

MOCK_S2_PAPER = {
    "paperId": "abc123",
    "title": "Test Paper from Semantic Scholar",
    "abstract": "This is a test abstract.",
    "authors": [{"name": "Alice"}, {"name": "Bob"}],
    "year": 2024,
    "venue": "CVPR",
    "citationCount": 42,
    "url": "https://www.semanticscholar.org/paper/abc123",
    "openAccessPdf": {"url": "https://arxiv.org/pdf/2401.12345"},
}


# ---------------------------------------------------------------------------
# _normalize_arxiv_id Tests
# ---------------------------------------------------------------------------


def test_normalize_arxiv_id_plain():
    assert _normalize_arxiv_id("2401.12345") == "ARXIV:2401.12345"


def test_normalize_arxiv_id_already_prefixed():
    assert _normalize_arxiv_id("ARXIV:2401.12345") == "ARXIV:2401.12345"


def test_normalize_arxiv_id_doi():
    assert _normalize_arxiv_id("DOI:10.1234/test") == "DOI:10.1234/test"


def test_normalize_arxiv_id_s2_id():
    assert _normalize_arxiv_id("abc123def") == "abc123def"


# ---------------------------------------------------------------------------
# _format_paper Tests
# ---------------------------------------------------------------------------


def test_format_paper():
    result = _format_paper(MOCK_S2_PAPER)
    assert result["title"] == "Test Paper from Semantic Scholar"
    assert result["authors"] == ["Alice", "Bob"]
    assert result["citation_count"] == 42
    assert result["pdf_url"] == "https://arxiv.org/pdf/2401.12345"
    assert result["source"] == "semantic_scholar"


def test_format_paper_missing_fields():
    result = _format_paper({"paperId": "x"})
    assert result["id"] == "x"
    assert result["title"] == ""
    assert result["authors"] == []
    assert result["citation_count"] == 0


# ---------------------------------------------------------------------------
# fetch_recommendations Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_recommendations_success(mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"recommendedPapers": [MOCK_S2_PAPER, MOCK_S2_PAPER]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.related_papers.httpx.AsyncClient", return_value=mock_client)
    results = await fetch_recommendations(["2401.12345"], limit=5)
    assert len(results) == 2
    assert results[0]["title"] == "Test Paper from Semantic Scholar"


@pytest.mark.asyncio
async def test_fetch_recommendations_empty(mocker):
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.related_papers.httpx.AsyncClient", return_value=mock_client)
    results = await fetch_recommendations(["nonexistent"])
    assert results == []


@pytest.mark.asyncio
async def test_fetch_recommendations_with_negative(mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"recommendedPapers": [MOCK_S2_PAPER]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.related_papers.httpx.AsyncClient", return_value=mock_client)
    await fetch_recommendations(["2401.12345"], negative_ids=["2401.99999"])
    call_args = mock_client.post.call_args
    body = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
    assert "negativePaperIds" in body


# ---------------------------------------------------------------------------
# fetch_citations_and_references Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_citations_references_success(mocker):
    mock_data = {
        "references": [MOCK_S2_PAPER],
        "citations": [MOCK_S2_PAPER, MOCK_S2_PAPER],
    }
    mocker.patch(
        "top_paper_mcp_server.tools.related_papers._s2_get",
        AsyncMock(return_value=mock_data),
    )
    result = await fetch_citations_and_references("2401.12345")
    assert len(result["references"]) == 1
    assert len(result["citations"]) == 2


@pytest.mark.asyncio
async def test_fetch_citations_references_not_found(mocker):
    mocker.patch(
        "top_paper_mcp_server.tools.related_papers._s2_get",
        AsyncMock(return_value=None),
    )
    result = await fetch_citations_and_references("nonexistent")
    assert result["references"] == []
    assert result["citations"] == []


# ---------------------------------------------------------------------------
# handle_related_papers Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_no_paper_id():
    result = await handle_related_papers({})
    content = json.loads(result[0].text)
    assert content["status"] == "error"


@pytest.mark.asyncio
async def test_handle_recommendations(mocker):
    mocker.patch(
        "top_paper_mcp_server.tools.related_papers.fetch_recommendations",
        AsyncMock(return_value=[_format_paper(MOCK_S2_PAPER)]),
    )
    result = await handle_related_papers({
        "paper_id": "2401.12345",
        "mode": "recommendations",
        "limit": 5,
    })
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["mode"] == "recommendations"
    assert content["total_results"] == 1


@pytest.mark.asyncio
async def test_handle_citations(mocker):
    mocker.patch(
        "top_paper_mcp_server.tools.related_papers.fetch_citations_and_references",
        AsyncMock(return_value={"citations": [_format_paper(MOCK_S2_PAPER)], "references": []}),
    )
    result = await handle_related_papers({
        "paper_id": "2401.12345",
        "mode": "citations",
    })
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["mode"] == "citations"
    assert content["total_results"] == 1


@pytest.mark.asyncio
async def test_handle_references(mocker):
    mocker.patch(
        "top_paper_mcp_server.tools.related_papers.fetch_citations_and_references",
        AsyncMock(return_value={"citations": [], "references": [_format_paper(MOCK_S2_PAPER)]}),
    )
    result = await handle_related_papers({
        "paper_id": "2401.12345",
        "mode": "references",
    })
    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["mode"] == "references"


@pytest.mark.asyncio
async def test_handle_unknown_mode():
    result = await handle_related_papers({
        "paper_id": "2401.12345",
        "mode": "invalid",
    })
    content = json.loads(result[0].text)
    assert content["status"] == "error"
    assert "Unknown mode" in content["message"]


@pytest.mark.asyncio
async def test_handle_citations_requires_paper_id():
    result = await handle_related_papers({
        "paper_ids": ["2401.12345"],
        "mode": "citations",
    })
    content = json.loads(result[0].text)
    assert content["status"] == "error"
