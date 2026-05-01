"""Tests for conference download functionality — OpenReview API with arXiv fallback."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from top_paper_mcp_server.tools.conference_download import (
    handle_conference_download,
    CONTENT_WARNING,
)

MOCK_OPENREVIEW_RESULT = {
    "status": "success",
    "paper_id": "or_12345",
    "source": "openreview",
    "content": "# Test Paper\n\n**Authors:** Test Author\n\n**Abstract:** Test abstract",
    "conference": "CVPR",
}


@pytest.fixture
def mock_openreview():
    """Patch OpenReview source with mock."""
    mock_source = MagicMock()
    mock_source.download_paper = AsyncMock(return_value=MOCK_OPENREVIEW_RESULT)
    with patch(
        "top_paper_mcp_server.tools.conference_download.openreview_source",
        mock_source,
    ):
        yield mock_source


@pytest.fixture
def mock_openreview_not_found():
    """Patch OpenReview source to return not found, and mock arXiv fallback."""
    mock_source = MagicMock()
    mock_source.download_paper = AsyncMock(
        return_value={"status": "error", "message": "Paper not found"}
    )
    mock_arxiv = AsyncMock(
        return_value=[
            MagicMock(text=json.dumps({"status": "error", "message": "not found"}))
        ]
    )
    with (
        patch(
            "top_paper_mcp_server.tools.conference_download.openreview_source",
            mock_source,
        ),
        patch(
            "top_paper_mcp_server.tools.download.handle_download",
            mock_arxiv,
        ),
    ):
        yield mock_source


# ---------------------------------------------------------------------------
# handle_conference_download Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_success(mock_openreview):
    """Test successful paper download via OpenReview."""
    result = await handle_conference_download(
        {"paper_id": "or_12345", "conference": "CVPR"}
    )

    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["paper_id"] == "or_12345"
    assert content["conference"] == "CVPR"
    assert "Test Paper" in content["content"]


@pytest.mark.asyncio
async def test_download_with_content_warning(mock_openreview):
    """Test that downloaded content includes security warning."""
    result = await handle_conference_download(
        {"paper_id": "or_12345", "conference": "CVPR"}
    )

    content = json.loads(result[0].text)
    assert content["content"].startswith("[UNTRUSTED EXTERNAL CONTENT")
    assert "Conference paper" in content["content"]


@pytest.mark.asyncio
async def test_download_missing_params():
    """Test download without required params returns error."""
    result = await handle_conference_download({"paper_id": "", "conference": ""})

    content = json.loads(result[0].text)
    assert content["status"] == "error"
    assert "required" in content["message"]


@pytest.mark.asyncio
async def test_download_openreview_not_found(mock_openreview_not_found):
    """Test download when paper not found on OpenReview."""
    result = await handle_conference_download(
        {"paper_id": "nonexistent", "conference": "CVPR"}
    )

    content = json.loads(result[0].text)
    # Should fall through to arXiv fallback, which also fails
    assert content["status"] == "error"


@pytest.mark.asyncio
async def test_download_various_conferences(mock_openreview):
    """Test downloading from different conferences."""
    conferences = ["CVPR", "ICCV", "WACV", "ICLR", "NEURIPS", "ICML", "ACL", "AAAI"]

    for conf in conferences:
        result = await handle_conference_download(
            {"paper_id": "or_12345", "conference": conf}
        )
        content = json.loads(result[0].text)
        assert content["status"] == "success"
