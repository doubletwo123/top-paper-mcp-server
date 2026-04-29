"""Tests for conference download functionality."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from top_paper_mcp_server.tools.conference_download import (
    handle_conference_download,
    _get_source,
    CONTENT_WARNING,
)
from top_paper_mcp_server.tools.conferences.base import PaperMetadata


class MockDownloadSource:
    """Mock conference source for download testing."""

    def __init__(self, name="mock"):
        self._name = name

    @property
    def name(self):
        return self._name

    async def download_paper(self, paper_id, conference):
        if paper_id == "not_found":
            return {
                "status": "error",
                "message": f"Paper {paper_id} not found in {conference}",
            }
        return {
            "status": "success",
            "paper_id": paper_id,
            "conference": conference,
            "content": f"Full content of paper {paper_id} from {conference}",
            "source": "html",
            "year": 2024,
        }


@pytest.fixture
def mock_download_sources():
    """Patch all conference sources with mock for download."""
    with (
        patch(
            "top_paper_mcp_server.tools.conference_download.cvf_source",
            MockDownloadSource("cvf"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_download.openreview_source",
            MockDownloadSource("openreview"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_download.eccv_source",
            MockDownloadSource("eccv"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_download.acm_source",
            MockDownloadSource("acm"),
        ),
        patch(
            "top_paper_mcp_server.tools.conference_download.mlanthology_source",
            MockDownloadSource("mlanthology"),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# handle_conference_download Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_success(mock_download_sources):
    """Test successful paper download."""
    result = await handle_conference_download(
        {"paper_id": "12345", "conference": "CVPR", "year": 2024}
    )

    content = json.loads(result[0].text)
    assert content["status"] == "success"
    assert content["paper_id"] == "12345"
    assert content["conference"] == "CVPR"
    assert content["year"] == 2024
    assert "Full content of paper" in content["content"]


@pytest.mark.asyncio
async def test_download_with_content_warning(mock_download_sources):
    """Test that downloaded content includes security warning."""
    result = await handle_conference_download(
        {"paper_id": "12345", "conference": "NeurIPS"}
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
async def test_download_paper_not_found(mock_download_sources):
    """Test download when paper doesn't exist."""
    result = await handle_conference_download(
        {"paper_id": "not_found", "conference": "CVPR"}
    )

    content = json.loads(result[0].text)
    assert content["status"] == "error"
    assert "not found" in content["message"]


@pytest.mark.asyncio
async def test_download_various_conferences(mock_download_sources):
    """Test downloading from different conferences."""
    conferences = ["CVPR", "ICCV", "WACV", "ICLR", "NEURIPS", "ICML", "ACL", "AAAI", "COLT", "UAI"]

    for conf in conferences:
        result = await handle_conference_download(
            {"paper_id": "test_001", "conference": conf}
        )
        content = json.loads(result[0].text)
        assert content["status"] == "success"


@pytest.mark.asyncio
async def test_download_error_handling(mock_download_sources):
    """Test that unexpected exceptions return clean error."""
    with patch(
        "top_paper_mcp_server.tools.conference_download.cvf_source",
    ) as mock_source:
        mock_instance = MockDownloadSource("cvf")
        mock_instance.download_paper = MagicMock(
            side_effect=RuntimeError("Network error")
        )
        mock_source.download_paper = mock_instance.download_paper

        result = await handle_conference_download(
            {"paper_id": "12345", "conference": "CVPR"}
        )

        content = json.loads(result[0].text)
        assert content["status"] == "error"
        assert "Network error" in content["message"]


# ---------------------------------------------------------------------------
# _get_source Tests
# ---------------------------------------------------------------------------


def test_get_source_cvf_conferences():
    """Test getting source for CVF conferences."""
    source = _get_source("CVPR")
    assert source is not None

    source = _get_source("ICCV")
    assert source is not None


def test_get_source_openreview_conferences():
    """Test getting source for OpenReview conferences."""
    source = _get_source("ICLR")
    assert source is not None

    source = _get_source("NeurIPS")
    assert source is not None


def test_get_source_invalid():
    """Test getting source for invalid conference raises ValueError."""
    with pytest.raises(ValueError, match="Unknown conference"):
        _get_source("INVALID_CONF")
