"""Integration tests for conference source parsers using realistic mock responses.

These tests verify that each conference source correctly parses realistic HTML/JSON
responses without making real network requests.
"""

import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from top_paper_mcp_server.tools.conferences.cvf import CVFSource
from top_paper_mcp_server.tools.conferences.openreview import OpenReviewSource
from top_paper_mcp_server.tools.conferences.mlanthology import (
    MLAnthologySource,
    PMLR_BASE_URL,
    PMLR_VOLUME_MAP,
)
from top_paper_mcp_server.tools.conferences.aaai_ijcai import AAAISource, IJCaiSource
from top_paper_mcp_server.tools.conferences.eccv import ECCVSource
from top_paper_mcp_server.tools.conference_search import (
    CONFERENCE_SOURCE_MAP,
    _get_source,
    handle_conference_search,
)
from top_paper_mcp_server.tools.conferences.base import PaperMetadata


# ---------------------------------------------------------------------------
# Realistic mock HTML / JSON fixtures
# ---------------------------------------------------------------------------

CVF_MOCK_HTML = """<!DOCTYPE html>
<html>
<body>
<dl>
<dt class="ptitle">
  <a href="/content/CVPR2024/html/Wang_Object_Detection_CVPR_2024_paper.html">
    Object Detection with Transformers
  </a>
</dt>
<dd>
  <a href="/content/CVPR2024/html/Wang_Object_Detection_CVPR_2024_paper.html">
    Object Detection with Transformers
  </a>
  <br>
</dd>
<dt class="ptitle">
  <a href="/content/CVPR2024/html/Li_Deep_Learning_Survey_CVPR_2024_paper.html">
    Deep Learning Survey
  </a>
</dt>
<dd>
  <a href="/content/CVPR2024/html/Li_Deep_Learning_Survey_CVPR_2024_paper.html">
    Deep Learning Survey
  </a>
  <br>
</dd>
<dt class="ptitle">
  <a href="/content/CVPR2024/html/Smith_Image_Segmentation_CVPR_2024_paper.html">
    Image Segmentation with Neural Networks
  </a>
</dt>
<dd>
  <a href="/content/CVPR2024/html/Smith_Image_Segmentation_CVPR_2024_paper.html">
    Image Segmentation with Neural Networks
  </a>
  <br>
</dd>
</dl>
</body>
</html>"""

# Realistic OpenReview API v2 response
OPENREVIEW_MOCK_RESPONSE = {
    "notes": [
        {
            "id": "abc123xyz",
            "content": {
                "title": {"value": "Attention Is All You Need: Transformer Revisited"},
                "abstract": {
                    "value": "We revisit the transformer architecture with new insights."
                },
                "authors": {"value": ["John Doe", "Jane Smith", "Bob Jones"]},
                "pdf": {"value": "/pdf/abc123xyz.pdf"},
            },
        },
        {
            "id": "def456uvw",
            "content": {
                "title": {"value": "BERT: Bidirectional Encoder Representations"},
                "abstract": {
                    "value": "We present BERT, a new transformer pretraining method."
                },
                "authors": {"value": ["Alice Brown", "Charlie Davis"]},
                "pdf": {"value": "/pdf/def456uvw.pdf"},
            },
        },
        {
            "id": "ghi789rst",
            "content": {
                "title": {"value": "Diffusion Models for Image Synthesis"},
                "abstract": {
                    "value": "We propose using diffusion models instead of GANs."
                },
                "authors": {"value": ["Eve Wilson"]},
                "pdf": {"value": "/pdf/ghi789rst.pdf"},
            },
        },
    ]
}

AAAI_MOCK_HTML = """<html>
<body>
<div class="section">
<ul class="cmp_article_list">
  <li>
    <article class="article">
      <h3 class="title">
        <a class="title" href="https://ojs.aaai.org/index.php/AAAI/article/view/26753">
          Deep Learning for Object Detection in Autonomous Driving
        </a>
      </h3>
      <div class="authors">
        <a href="#">John Smith</a>, <a href="#">Jane Doe</a>
      </div>
      <div class="abstract">
        We propose a new method for object detection...
      </div>
    </article>
  </li>
  <li>
    <article class="article">
      <h3 class="title">
        <a class="title" href="https://ojs.aaai.org/index.php/AAAI/article/view/26754">
          Transformer Models for Natural Language Processing
        </a>
      </h3>
      <div class="authors">
        <a href="#">Bob Wilson</a>
      </div>
      <div class="abstract">
        This paper presents a new transformer model for NLP tasks...
      </div>
    </article>
  </li>
</ul>
</div>
</body>
</html>"""

IJCAI_MOCK_HTML = """<html>
<body>
<div id="schedule">
  <div class="paper-item">
    <h4>Deep Reinforcement Learning for Game Playing</h4>
    <div class="authors">Alice Brown, Charlie Davis, Eve Wilson</div>
    <a class="pdf-link" href="https://www.ijcai.org/proceedings/2024/0001.pdf">PDF</a>
  </div>
  <div class="paper-item">
    <h4>Knowledge Graph Embedding Methods</h4>
    <div class="authors">Frank Miller, Grace Lee</div>
    <a class="pdf-link" href="https://www.ijcai.org/proceedings/2024/0002.pdf">PDF</a>
  </div>
</div>
</body>
</html>"""

# Realistic PMLR volume page HTML
PMLR_MOCK_HTML = """<!DOCTYPE html>
<html>
<head><title>COLT 2024</title></head>
<body>
<div class="container">
  <h2>Proceedings of The 37th Annual Conference on Computational Learning Theory</h2>
  <div id="series">
    <div class="paper" id="paper1">
      <p class="title">PAC Learning with Oracle Queries</p>
      <p class="details">
        <span class="authors">Alice Researcher, Bob Scientist</span>
        |
        <a href="/v247/researcher24a.html">abs</a>
        |
        <a href="https://proceedings.mlr.press/v247/researcher24a/researcher24a.pdf">pdf</a>
      </p>
    </div>
    <div class="paper" id="paper2">
      <p class="title">Online Learning with Bandit Feedback and Regret Bounds</p>
      <p class="details">
        <span class="authors">Charlie Theorist, Dave Learner</span>
        |
        <a href="/v247/theorist24b.html">abs</a>
        |
        <a href="https://proceedings.mlr.press/v247/theorist24b/theorist24b.pdf">pdf</a>
      </p>
    </div>
    <div class="paper" id="paper3">
      <p class="title">Sample Complexity of Hypothesis Testing</p>
      <p class="details">
        <span class="authors">Eve Scholar</span>
        |
        <a href="/v247/scholar24c.html">abs</a>
        |
        <a href="https://proceedings.mlr.press/v247/scholar24c/scholar24c.pdf">pdf</a>
      </p>
    </div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CVF Source Tests
# ---------------------------------------------------------------------------


class TestCVFSource:
    """Tests for CVF HTML parsing."""

    def setup_method(self):
        self.source = CVFSource()

    def test_parse_finds_matching_papers(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "object detection", 10
        )
        assert len(papers) == 1
        assert "Object Detection" in papers[0].title

    def test_parse_returns_all_papers_with_empty_query(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "", 10
        )
        assert len(papers) == 3

    def test_parse_respects_max_results(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "", 2
        )
        assert len(papers) == 2

    def test_parse_extracts_correct_paper_id(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "object detection", 10
        )
        assert papers[0].paper_id == "Wang_Object_Detection_CVPR_2024_paper"

    def test_parse_builds_correct_url(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "object detection", 10
        )
        expected_url = "https://openaccess.thecvf.com/content/CVPR2024/html/Wang_Object_Detection_CVPR_2024_paper.html"
        assert papers[0].url == expected_url

    def test_parse_builds_correct_pdf_url(self):
        papers = self.source._parse_paper_list(
            CVF_MOCK_HTML, "CVPR", 2024, "object detection", 10
        )
        assert papers[0].pdf_url.endswith(".pdf")
        assert "Wang_Object_Detection_CVPR_2024_paper" in papers[0].pdf_url

    def test_eccv_handled_by_cvf(self):
        """ECCV should now route through CVF, not the separate ECCVSource."""
        assert CONFERENCE_SOURCE_MAP.get("ECCV") == "cvf"
        source = _get_source("ECCV")
        assert isinstance(source, CVFSource)

    def test_eccv_in_cvf_conferences(self):
        assert "ECCV" in self.source.conferences

    def test_eccv_conf_year_generation(self):
        conf_year = self.source._get_conf_year("ECCV", 2024)
        assert conf_year == "ECCV2024"

    @pytest.mark.asyncio
    async def test_search_calls_correct_cvf_url(self):
        """CVF search must fetch the correct openaccess.thecvf.com URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CVF_MOCK_HTML
        mock_response.raise_for_status = MagicMock()

        captured_urls = []

        async def mock_get(url, **kwargs):
            captured_urls.append(url)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            papers = await self.source.search("object detection", "CVPR", 2024, 5)

        assert len(captured_urls) == 1
        assert captured_urls[0] == "https://openaccess.thecvf.com/CVPR2024"

    @pytest.mark.asyncio
    async def test_eccv_search_uses_cvf_url(self):
        """ECCV search through CVF must fetch thecvf.com, not ecva.net."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = CVF_MOCK_HTML
        mock_response.raise_for_status = MagicMock()

        captured_urls = []

        async def mock_get(url, **kwargs):
            captured_urls.append(url)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            papers = await self.source.search("detection", "ECCV", 2024, 5)

        assert len(captured_urls) == 1
        assert captured_urls[0] == "https://openaccess.thecvf.com/ECCV2024"


# ---------------------------------------------------------------------------
# OpenReview Source Tests
# ---------------------------------------------------------------------------


class TestOpenReviewSource:
    """Tests for OpenReview API parsing."""

    def setup_method(self):
        self.source = OpenReviewSource()

    def test_parse_extracts_title(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, ""
        )
        titles = [p.title for p in papers]
        assert "Attention Is All You Need: Transformer Revisited" in titles

    def test_parse_extracts_authors(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, ""
        )
        assert papers[0].authors == ["John Doe", "Jane Smith", "Bob Jones"]

    def test_parse_extracts_abstract(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, ""
        )
        assert "transformer" in papers[0].abstract.lower()

    def test_parse_filters_by_query_title(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, "transformer"
        )
        # "transformer" appears in title or abstract of first two papers
        for p in papers:
            assert "transformer" in p.title.lower() or "transformer" in p.abstract.lower()

    def test_parse_filters_by_query_abstract(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, "diffusion"
        )
        assert len(papers) == 1
        assert "Diffusion" in papers[0].title

    def test_parse_builds_openreview_pdf_url(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, ""
        )
        assert papers[0].pdf_url.startswith("https://openreview.net/pdf")

    def test_parse_builds_openreview_forum_url(self):
        papers = self.source._parse_papers(
            OPENREVIEW_MOCK_RESPONSE["notes"], "ICLR", 2024, ""
        )
        assert papers[0].url.startswith("https://openreview.net/forum")

    def test_get_content_value_unwraps_value_dict(self):
        content = {"title": {"value": "Test Title"}}
        assert self.source._get_content_value(content, "title", "") == "Test Title"

    def test_get_content_value_handles_plain_string(self):
        content = {"title": "Plain Title"}
        assert self.source._get_content_value(content, "title", "") == "Plain Title"

    def test_get_content_value_returns_default(self):
        content = {}
        assert self.source._get_content_value(content, "missing", "default") == "default"

    def test_venue_id_iclr_2024(self):
        assert self.source._get_venue_id("ICLR", 2024) == "ICLR.cc/2024/Conference"

    def test_venue_id_neurips_2024(self):
        assert self.source._get_venue_id("NeurIPS", 2024) == "NeurIPS.cc/2024/Conference"

    def test_venue_id_icml_2024(self):
        assert self.source._get_venue_id("ICML", 2024) == "ICML.cc/2024/Conference"

    def test_venue_id_aaai_2024(self):
        assert self.source._get_venue_id("AAAI", 2024) == "AAAI.org/2024/Conference"

    def test_venue_id_acl_2024(self):
        assert self.source._get_venue_id("ACL", 2024) == "aclweb.org/ACL/2024/Conference"

    def test_venue_id_colm_2024(self):
        assert self.source._get_venue_id("COLM", 2024) == "COLM.org/2024/Conference"

    def test_aaai_routes_to_openreview(self):
        """After fixing Bug #2, AAAI should use the OpenReview source."""
        assert CONFERENCE_SOURCE_MAP.get("AAAI") == "openreview"
        source = _get_source("AAAI")
        assert isinstance(source, OpenReviewSource)

    @pytest.mark.asyncio
    async def test_search_uses_venue_id(self):
        """OpenReview search must include the correct venueid parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=OPENREVIEW_MOCK_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        captured_params = {}

        async def mock_get(url, params=None, **kwargs):
            captured_params.update(params or {})
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            papers = await self.source.search("transformer", "ICLR", 2024, 5)

        assert "venueid" in captured_params
        assert captured_params["venueid"] == "ICLR.cc/2024/Conference"


# ---------------------------------------------------------------------------
# AAAI Source Tests (legacy - now routes to OpenReview)
# ---------------------------------------------------------------------------


class TestAAAISource:
    """Tests for the legacy AAAISource HTML parser."""

    def setup_method(self):
        self.source = AAAISource()

    def test_parse_finds_matching_papers(self):
        papers = self.source._parse_paper_list(AAAI_MOCK_HTML, 2024, "object", 10)
        assert len(papers) == 1
        assert "Object Detection" in papers[0].title

    def test_parse_returns_all_papers_empty_query(self):
        papers = self.source._parse_paper_list(AAAI_MOCK_HTML, 2024, "", 10)
        assert len(papers) == 2

    def test_parse_extracts_authors(self):
        papers = self.source._parse_paper_list(AAAI_MOCK_HTML, 2024, "object", 10)
        assert len(papers[0].authors) == 2

    def test_parse_extracts_abstract(self):
        papers = self.source._parse_paper_list(AAAI_MOCK_HTML, 2024, "object", 10)
        assert papers[0].abstract != ""


# ---------------------------------------------------------------------------
# IJCAI Source Tests
# ---------------------------------------------------------------------------


class TestIJCAISource:
    """Tests for the IJCaiSource HTML parser."""

    def setup_method(self):
        self.source = IJCaiSource()

    def test_parse_finds_matching_papers(self):
        papers = self.source._parse_paper_list(
            IJCAI_MOCK_HTML, 2024, "reinforcement learning", 10
        )
        assert len(papers) == 1
        assert "Reinforcement Learning" in papers[0].title

    def test_parse_returns_all_papers_empty_query(self):
        papers = self.source._parse_paper_list(IJCAI_MOCK_HTML, 2024, "", 10)
        assert len(papers) == 2

    def test_parse_extracts_authors(self):
        papers = self.source._parse_paper_list(IJCAI_MOCK_HTML, 2024, "", 10)
        assert len(papers[0].authors) == 3

    def test_parse_extracts_pdf_url(self):
        papers = self.source._parse_paper_list(IJCAI_MOCK_HTML, 2024, "", 10)
        assert papers[0].pdf_url.startswith("https://www.ijcai.org/proceedings/")
        assert papers[0].pdf_url.endswith(".pdf")


# ---------------------------------------------------------------------------
# MLAnthology (PMLR) Source Tests
# ---------------------------------------------------------------------------


class TestMLAnthologySource:
    """Tests for the rewritten PMLR-based MLAnthologySource."""

    def setup_method(self):
        self.source = MLAnthologySource()

    def test_source_name_is_pmlr(self):
        assert self.source.name == "PMLR"

    def test_conferences_list(self):
        assert "COLT" in self.source.conferences
        assert "UAI" in self.source.conferences

    def test_volume_map_has_recent_colt(self):
        assert ("COLT", 2024) in PMLR_VOLUME_MAP
        assert ("COLT", 2023) in PMLR_VOLUME_MAP

    def test_volume_map_has_recent_uai(self):
        assert ("UAI", 2024) in PMLR_VOLUME_MAP
        assert ("UAI", 2023) in PMLR_VOLUME_MAP

    def test_parse_finds_matching_papers(self):
        papers = self.source._parse_paper_list(
            PMLR_MOCK_HTML, "COLT", 2024, "learning", 10
        )
        # "PAC Learning" and "Online Learning" both match "learning"
        assert len(papers) == 2

    def test_parse_returns_all_papers_empty_query(self):
        papers = self.source._parse_paper_list(PMLR_MOCK_HTML, "COLT", 2024, "", 10)
        assert len(papers) == 3

    def test_parse_respects_max_results(self):
        papers = self.source._parse_paper_list(PMLR_MOCK_HTML, "COLT", 2024, "", 1)
        assert len(papers) == 1

    def test_parse_extracts_authors(self):
        papers = self.source._parse_paper_list(PMLR_MOCK_HTML, "COLT", 2024, "", 10)
        assert papers[0].authors == ["Alice Researcher", "Bob Scientist"]

    def test_parse_extracts_paper_id_from_abs_link(self):
        papers = self.source._parse_paper_list(PMLR_MOCK_HTML, "COLT", 2024, "", 10)
        assert papers[0].paper_id == "researcher24a"

    def test_parse_builds_pmlr_pdf_url(self):
        papers = self.source._parse_paper_list(PMLR_MOCK_HTML, "COLT", 2024, "", 10)
        assert papers[0].pdf_url.startswith("https://proceedings.mlr.press/")
        assert papers[0].pdf_url.endswith(".pdf")

    def test_pmlr_base_url_is_correct(self):
        """PMLR base URL must NOT be the NeurIPS proceedings site."""
        assert PMLR_BASE_URL == "https://proceedings.mlr.press"
        assert "neurips" not in PMLR_BASE_URL

    def test_colt_routes_to_mlanthology(self):
        assert CONFERENCE_SOURCE_MAP.get("COLT") == "mlanthology"
        source = _get_source("COLT")
        assert isinstance(source, MLAnthologySource)

    def test_uai_routes_to_mlanthology(self):
        assert CONFERENCE_SOURCE_MAP.get("UAI") == "mlanthology"
        source = _get_source("UAI")
        assert isinstance(source, MLAnthologySource)

    @pytest.mark.asyncio
    async def test_search_uses_pmlr_volume_url(self):
        """Search must fetch the PMLR volume page, not neurips.cc."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = PMLR_MOCK_HTML
        mock_response.raise_for_status = MagicMock()

        captured_urls = []

        async def mock_get(url, **kwargs):
            captured_urls.append(url)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            papers = await self.source.search("learning", "COLT", 2024, 5)

        # Should fetch exactly the PMLR volume page for COLT 2024 (v247)
        volume = PMLR_VOLUME_MAP[("COLT", 2024)]
        expected_url = f"https://proceedings.mlr.press/v{volume}/"
        assert expected_url in captured_urls
        assert not any(url.startswith("https://proceedings.neurips.cc") for url in captured_urls)

    @pytest.mark.asyncio
    async def test_search_returns_empty_for_unknown_year(self):
        """Search for a year with no static mapping and no index match returns []."""
        papers = await self.source.search("learning", "COLT", 1990, 5)
        assert papers == []


# ---------------------------------------------------------------------------
# Source Routing Tests
# ---------------------------------------------------------------------------


class TestConferenceSourceRouting:
    """Verify all conferences route to the correct source classes."""

    def test_cvpr_routes_to_cvf(self):
        assert isinstance(_get_source("CVPR"), CVFSource)

    def test_iccv_routes_to_cvf(self):
        assert isinstance(_get_source("ICCV"), CVFSource)

    def test_wacv_routes_to_cvf(self):
        assert isinstance(_get_source("WACV"), CVFSource)

    def test_eccv_routes_to_cvf_not_ecva(self):
        source = _get_source("ECCV")
        assert isinstance(source, CVFSource)
        assert not isinstance(source, ECCVSource)

    def test_iclr_routes_to_openreview(self):
        assert isinstance(_get_source("ICLR"), OpenReviewSource)

    def test_neurips_routes_to_openreview(self):
        assert isinstance(_get_source("NEURIPS"), OpenReviewSource)

    def test_icml_routes_to_openreview(self):
        assert isinstance(_get_source("ICML"), OpenReviewSource)

    def test_aaai_routes_to_openreview(self):
        assert isinstance(_get_source("AAAI"), OpenReviewSource)

    def test_acl_routes_to_openreview(self):
        assert isinstance(_get_source("ACL"), OpenReviewSource)

    def test_emnlp_routes_to_openreview(self):
        assert isinstance(_get_source("EMNLP"), OpenReviewSource)

    def test_naacl_routes_to_openreview(self):
        assert isinstance(_get_source("NAACL"), OpenReviewSource)

    def test_colt_routes_to_pmlr(self):
        source = _get_source("COLT")
        assert isinstance(source, MLAnthologySource)
        assert source.name == "PMLR"

    def test_uai_routes_to_pmlr(self):
        source = _get_source("UAI")
        assert isinstance(source, MLAnthologySource)
        assert source.name == "PMLR"


# ---------------------------------------------------------------------------
# End-to-end handler tests with mocked sources
# ---------------------------------------------------------------------------


class TestHandlerWithMockedSources:
    """Test the conference search handler with realistic mocked responses."""

    @pytest.mark.asyncio
    async def test_cvpr_search_returns_papers(self):
        """Simulates: user asks 'search CVPR 2024 for object detection'."""
        mock_papers = [
            PaperMetadata(
                paper_id="Wang_Object_Detection_CVPR_2024_paper",
                title="Object Detection with Transformers",
                authors=["John Wang"],
                abstract="",
                year=2024,
                conference="CVPR",
                url="https://openaccess.thecvf.com/content/CVPR2024/html/Wang_Object_Detection_CVPR_2024_paper.html",
                pdf_url="https://openaccess.thecvf.com/content/CVPR2024/papers/Wang_Object_Detection_CVPR_2024_paper.pdf",
            )
        ]

        with patch(
            "top_paper_mcp_server.tools.conference_search.cvf_source"
        ) as mock_cvf:
            mock_cvf.search = AsyncMock(return_value=mock_papers)
            result = await handle_conference_search(
                {
                    "query": "object detection",
                    "conference": "CVPR",
                    "year": 2024,
                    "max_results": 5,
                }
            )

        data = json.loads(result[0].text)
        assert data["total_results"] == 1
        assert data["conference"] == "CVPR"
        assert "Object Detection" in data["papers"][0]["title"]
        assert data["papers"][0]["url"] == "https://openaccess.thecvf.com/content/CVPR2024/html/Wang_Object_Detection_CVPR_2024_paper.html"

    @pytest.mark.asyncio
    async def test_eccv_search_uses_cvf_source(self):
        """ECCV must use cvf_source after the routing fix."""
        with patch(
            "top_paper_mcp_server.tools.conference_search.cvf_source"
        ) as mock_cvf:
            mock_cvf.search = AsyncMock(return_value=[])
            await handle_conference_search(
                {"query": "detection", "conference": "ECCV", "year": 2024}
            )
            mock_cvf.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_aaai_search_uses_openreview_source(self):
        """AAAI must use openreview_source after the routing fix."""
        with patch(
            "top_paper_mcp_server.tools.conference_search.openreview_source"
        ) as mock_or:
            mock_or.search = AsyncMock(return_value=[])
            await handle_conference_search(
                {"query": "planning", "conference": "AAAI", "year": 2024}
            )
            mock_or.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_colt_search_uses_mlanthology_source(self):
        """COLT must use mlanthology_source (PMLR)."""
        with patch(
            "top_paper_mcp_server.tools.conference_search.mlanthology_source"
        ) as mock_ml:
            mock_ml.search = AsyncMock(return_value=[])
            await handle_conference_search(
                {"query": "learning", "conference": "COLT", "year": 2024}
            )
            mock_ml.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_iclr_search_returns_papers(self):
        """Simulates: user asks 'find ICLR 2024 papers about transformer'."""
        mock_papers = [
            PaperMetadata(
                paper_id="abc123",
                title="Attention Is All You Need: Transformer Revisited",
                authors=["John Doe", "Jane Smith"],
                abstract="We revisit the transformer architecture.",
                year=2024,
                conference="ICLR",
                url="https://openreview.net/forum?id=abc123",
                pdf_url="https://openreview.net/pdf?id=abc123",
            )
        ]

        with patch(
            "top_paper_mcp_server.tools.conference_search.openreview_source"
        ) as mock_or:
            mock_or.search = AsyncMock(return_value=mock_papers)
            result = await handle_conference_search(
                {"query": "transformer", "conference": "ICLR", "year": 2024}
            )

        data = json.loads(result[0].text)
        assert data["total_results"] == 1
        assert data["papers"][0]["url"] == "https://openreview.net/forum?id=abc123"

    @pytest.mark.asyncio
    async def test_no_results_returns_friendly_message(self):
        """Empty results should return a helpful message, not an error."""
        with patch(
            "top_paper_mcp_server.tools.conference_search.openreview_source"
        ) as mock_or:
            mock_or.search = AsyncMock(return_value=[])
            result = await handle_conference_search(
                {"query": "xyznonexistent123", "conference": "ICLR", "year": 2024}
            )

        data = json.loads(result[0].text)
        assert data["total_results"] == 0
        assert "message" in data
        assert "papers" in data
        assert data["papers"] == []
