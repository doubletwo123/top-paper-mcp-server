"""Tests for HuggingFace integration — paper metadata mirror and daily papers."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from top_paper_mcp_server.tools.huggingface import (
    fetch_hf_paper_metadata,
    fetch_daily_papers,
    handle_hf_daily_papers,
)

MOCK_HF_PAPER = {
    "id": "2401.12345",
    "title": "Test Paper from HuggingFace",
    "summary": "This is a test abstract from HuggingFace.",
    "authors": [{"name": "Alice"}, {"name": "Bob"}],
    "publishedAt": "2024-01-15T00:00:00Z",
    "upvotes": 42,
    "ai_summary": "This paper proposes a novel approach.",
    "ai_keywords": ["transformer", "attention"],
    "githubRepo": "https://github.com/example/repo",
    "githubStars": 123,
}

MOCK_DAILY_ENTRY = {
    "paper": MOCK_HF_PAPER,
    "publishedAt": "2024-01-15T00:00:00Z",
}


# ---------------------------------------------------------------------------
# fetch_hf_paper_metadata Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_hf_paper_metadata_success(mocker):
    """Successful metadata fetch returns parsed dict."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = MOCK_HF_PAPER
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_hf_paper_metadata("2401.12345")
    assert result is not None
    assert result["title"] == "Test Paper from HuggingFace"
    assert result["upvotes"] == 42


@pytest.mark.asyncio
async def test_fetch_hf_paper_metadata_not_found(mocker):
    """404 response returns None."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_hf_paper_metadata("nonexistent.00000")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_hf_paper_metadata_http_error(mocker):
    """HTTP error returns None gracefully."""
    import httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_hf_paper_metadata("2401.12345")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_hf_paper_metadata_timeout(mocker):
    """Timeout returns None gracefully."""
    import httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_hf_paper_metadata("2401.12345")
    assert result is None


# ---------------------------------------------------------------------------
# fetch_daily_papers Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_daily_papers_success(mocker):
    """Successful daily papers fetch returns list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [MOCK_DAILY_ENTRY, MOCK_DAILY_ENTRY]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_daily_papers("2024-01-15")
    assert len(result) == 2
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args[1]["params"] == {"date": "2024-01-15"}


@pytest.mark.asyncio
async def test_fetch_daily_papers_no_date(mocker):
    """No date parameter sends empty params."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_daily_papers()
    assert result == []
    call_args = mock_client.get.call_args
    assert call_args[1]["params"] == {}


@pytest.mark.asyncio
async def test_fetch_daily_papers_http_error(mocker):
    """HTTP error returns empty list."""
    import httpx

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Server error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_daily_papers("2024-01-15")
    assert result == []


@pytest.mark.asyncio
async def test_fetch_daily_papers_non_list_response(mocker):
    """Non-list API response returns empty list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unexpected": "format"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mocker.patch("top_paper_mcp_server.tools.huggingface.httpx.AsyncClient", return_value=mock_client)

    result = await fetch_daily_papers()
    assert result == []


# ---------------------------------------------------------------------------
# handle_hf_daily_papers Tool Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hf_daily_papers_tool_success(mocker):
    """Tool handler returns formatted paper list."""
    mocker.patch(
        "top_paper_mcp_server.tools.huggingface.fetch_daily_papers",
        AsyncMock(return_value=[MOCK_DAILY_ENTRY]),
    )

    result = await handle_hf_daily_papers({"date": "2024-01-15", "max_results": 10})
    content = json.loads(result[0].text)

    assert content["status"] == "success"
    assert content["date"] == "2024-01-15"
    assert content["total_results"] == 1
    assert content["papers"][0]["title"] == "Test Paper from HuggingFace"
    assert content["papers"][0]["upvotes"] == 42
    assert content["papers"][0]["github_repo"] == "https://github.com/example/repo"


@pytest.mark.asyncio
async def test_hf_daily_papers_tool_no_date(mocker):
    """Tool handler defaults to today when no date given."""
    mocker.patch(
        "top_paper_mcp_server.tools.huggingface.fetch_daily_papers",
        AsyncMock(return_value=[]),
    )

    result = await handle_hf_daily_papers({})
    content = json.loads(result[0].text)

    assert content["status"] == "success"
    assert content["total_results"] == 0
    assert content["papers"] == []


@pytest.mark.asyncio
async def test_hf_daily_papers_tool_invalid_date():
    """Invalid date format returns error."""
    result = await handle_hf_daily_papers({"date": "not-a-date"})
    content = json.loads(result[0].text)

    assert content["status"] == "error"
    assert "Invalid date format" in content["message"]


@pytest.mark.asyncio
async def test_hf_daily_papers_tool_max_results_capped(mocker):
    """max_results is capped at 100."""
    entries = [MOCK_DAILY_ENTRY] * 200
    mocker.patch(
        "top_paper_mcp_server.tools.huggingface.fetch_daily_papers",
        AsyncMock(return_value=entries),
    )

    result = await handle_hf_daily_papers({"max_results": 500})
    content = json.loads(result[0].text)

    assert content["total_results"] == 100


@pytest.mark.asyncio
async def test_hf_daily_papers_tool_empty_response(mocker):
    """Empty API response returns success with zero results."""
    mocker.patch(
        "top_paper_mcp_server.tools.huggingface.fetch_daily_papers",
        AsyncMock(return_value=[]),
    )

    result = await handle_hf_daily_papers({"date": "2024-01-15"})
    content = json.loads(result[0].text)

    assert content["status"] == "success"
    assert content["total_results"] == 0
    assert content["papers"] == []
