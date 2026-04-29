"""ML Anthology paper source - aggregated ML conference proceedings."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

MLANTHOLOGY_BASE_URL = "https://proceedings.neurips.cc"

VENUE_MAP = {
    "NeurIPS": "NeurIPS",
    "ICML": "ICML",
    "ICLR": "ICLR",
    "COLT": "COLT",
    "UAI": "UAI",
    "AISTATS": "AISTATS",
    "ALT": "ALT",
    "KDD": "KDD",
    "IJCAI": "IJCAI",
}


class MLAnthologySource(ConferenceSource):
    """ML Anthology paper source - covers NeurIPS, ICML, ICLR, and more."""

    @property
    def name(self) -> str:
        return "MLAnthology"

    @property
    def conferences(self) -> List[str]:
        return list(VENUE_MAP.keys())

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in ML Anthology."""
        if conference not in VENUE_MAP:
            logger.warning(f"Unknown conference: {conference}")
            return []

        venue = VENUE_MAP[conference]
        url = f"{MLANTHOLOGY_BASE_URL}/paper/{year}"

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(
                response.text, conference, year, venue, query, max_results
            )

        except httpx.HTTPError as e:
            logger.error(f"ML Anthology search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"ML Anthology search failed: {e}")
            return []

    def _parse_paper_list(
        self,
        html: str,
        conference: str,
        year: int,
        venue: str,
        query: str,
        max_results: int,
    ) -> List[PaperMetadata]:
        """Parse paper list from ML Anthology page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for paper in soup.find_all("li", class_="nav-item"):
            link = paper.find("a", href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            href = link["href"]
            paper_id_match = re.search(r"paper/(\w+)", href)
            paper_id = paper_id_match.group(1) if paper_id_match else ""

            pdf_url = f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}.pdf"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=[],
                    abstract="",
                    year=year,
                    conference=conference,
                    url=f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}",
                    pdf_url=pdf_url,
                )
            )

            if len(papers) >= max_results:
                break

        return papers

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by ID."""
        for year in range(2000, 2030):
            url = f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return self._parse_paper_detail(
                            response.text, paper_id, conference, year
                        )
            except httpx.HTTPError:
                continue
        return None

    def _parse_paper_detail(
        self, html: str, paper_id: str, conference: str, year: int
    ) -> Optional[PaperMetadata]:
        """Parse single paper detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.find("h3")
        title = title_elem.get_text(strip=True) if title_elem else ""

        authors = []
        authors_div = soup.find("div", class_="authors")
        if authors_div:
            authors_text = authors_div.get_text(strip=True)
            authors = [a.strip() for a in authors_text.split(",")]

        abstract = ""
        abstract_div = soup.find("div", class_="abstract")
        if abstract_div:
            abstract = abstract_div.get_text(strip=True)

        pdf_url = f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}.pdf"

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference=conference,
            url=f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}",
            pdf_url=pdf_url,
        )

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        for year in range(2000, 2030):
            url = f"{MLANTHOLOGY_BASE_URL}/paper/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return {
                            "status": "success",
                            "paper_id": paper_id,
                            "source": "mlanthology_html",
                            "content": self._extract_text_from_html(response.text),
                            "year": year,
                            "conference": conference,
                        }
            except httpx.HTTPError:
                continue

        return {
            "status": "error",
            "message": f"Paper {paper_id} not found in ML Anthology",
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from paper HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []

        title = soup.find("h3")
        if title:
            text_parts.append(title.get_text(strip=True))

        authors_div = soup.find("div", class_="authors")
        if authors_div:
            text_parts.append(authors_div.get_text(strip=True))

        abstract_div = soup.find("div", class_="abstract")
        if abstract_div:
            text_parts.append(abstract_div.get_text(strip=True))

        return "\n\n".join(text_parts)
