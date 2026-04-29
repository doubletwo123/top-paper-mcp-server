"""NeurIPS paper source via official conference website."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

NEURIPS_BASE_URL = "https://neurips.cc"


class NeurIPSSource(ConferenceSource):
    """NeurIPS paper source via official website."""

    @property
    def name(self) -> str:
        return "NeurIPS"

    @property
    def conferences(self) -> List[str]:
        return ["NeurIPS"]

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in NeurIPS conference."""
        url = f"{NEURIPS_BASE_URL}/virtual/{year}/papers.html"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(response.text, year, query, max_results)

        except httpx.HTTPError as e:
            logger.error(f"NeurIPS search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"NeurIPS search failed: {e}")
            return []

    def _parse_paper_list(
        self, html: str, year: int, query: str, max_results: int
    ) -> List[PaperMetadata]:
        """Parse paper list from NeurIPS virtual page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for paper_div in soup.find_all("div", class_="paper"):
            title_elem = paper_div.find("a", class_="paper-title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            href = title_elem.get("href", "")
            paper_id_match = re.search(r"(\d+)", href)
            paper_id = paper_id_match.group(1) if paper_id_match else ""

            authors_div = paper_div.find("div", class_="authors")
            authors_text = authors_div.get_text(strip=True) if authors_div else ""
            authors = (
                [a.strip() for a in authors_text.split(",")] if authors_text else []
            )

            abstract_div = paper_div.find("div", class_="abstract")
            abstract = abstract_div.get_text(strip=True) if abstract_div else ""

            pdf_url = f"{NEURIPS_BASE_URL}/Virtual/{year}/{paper_id}.pdf"
            detail_url = f"{NEURIPS_BASE_URL}/virtual/{year}/{paper_id}"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference="NeurIPS",
                    url=detail_url,
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
        for year in range(2020, 2030):
            url = f"{NEURIPS_BASE_URL}/virtual/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return self._parse_paper_detail(response.text, paper_id, year)
            except httpx.HTTPError:
                continue
        return None

    def _parse_paper_detail(
        self, html: str, paper_id: str, year: int
    ) -> Optional[PaperMetadata]:
        """Parse single paper detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.find("meta", property="og:title")
        title = title_elem.get("content", "") if title_elem else ""

        authors = []
        authors_div = soup.find("div", class_="authors")
        if authors_div:
            for a in authors_div.find_all("a"):
                authors.append(a.get_text(strip=True))

        abstract_elem = soup.find("meta", property="og:description")
        abstract = abstract_elem.get("content", "") if abstract_elem else ""

        pdf_url = f"{NEURIPS_BASE_URL}/Virtual/{year}/{paper_id}.pdf"

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference="NeurIPS",
            url=f"{NEURIPS_BASE_URL}/virtual/{year}/{paper_id}",
            pdf_url=pdf_url,
        )

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        for year in range(2020, 2030):
            url = f"{NEURIPS_BASE_URL}/virtual/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return {
                            "status": "success",
                            "paper_id": paper_id,
                            "source": "neurips_html",
                            "content": self._extract_text_from_html(response.text),
                            "year": year,
                            "conference": "NeurIPS",
                        }
            except httpx.HTTPError:
                continue

        return {"status": "error", "message": f"Paper {paper_id} not found in NeurIPS"}

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from paper HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []
        for elem in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            text = elem.get_text(strip=True)
            if text and len(text) > 10:
                text_parts.append(text)

        return "\n\n".join(text_parts)
