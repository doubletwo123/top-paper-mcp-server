"""AAAI and IJCAI paper source via official conference websites."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

AAAI_BASE_URL = "https://ojs.aaai.org/index.php"
IJCAI_BASE_URL = "https://ijcai.org"


class AAAISource(ConferenceSource):
    """AAAI paper source via official website."""

    @property
    def name(self) -> str:
        return "AAAI"

    @property
    def conferences(self) -> List[str]:
        return ["AAAI"]

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in AAAI conference."""
        url = f"{AAAI_BASE_URL}/aiml/{year}/issue/view/0"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(response.text, year, query, max_results)

        except httpx.HTTPError as e:
            logger.error(f"AAAI search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"AAAI search failed: {e}")
            return []

    def _parse_paper_list(
        self, html: str, year: int, query: str, max_results: int
    ) -> List[PaperMetadata]:
        """Parse paper list from AAAI page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for article in soup.find_all("article", class_="article"):
            title_elem = article.find("a", class_="title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            href = title_elem.get("href", "")
            paper_id_match = re.search(r"(\d+)", href)
            paper_id = paper_id_match.group(1) if paper_id_match else f"AAAI{year}"

            authors = []
            authors_elem = article.find("div", class_="authors")
            if authors_elem:
                authors = [a.get_text(strip=True) for a in authors_elem.find_all("a")]

            abstract_elem = article.find("div", class_="abstract")
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

            pdf_url = f"{AAAI_BASE_URL}/aiml/{year}/article/view/{paper_id}"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference="AAAI",
                    url=href,
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
        return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        return {"status": "error", "message": "AAAI paper download not yet implemented"}


class IJCaiSource(ConferenceSource):
    """IJCAI paper source via official website."""

    @property
    def name(self) -> str:
        return "IJCAI"

    @property
    def conferences(self) -> List[str]:
        return ["IJCAI"]

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in IJCAI conference."""
        url = f"{IJCAI_BASE_URL}/proceedings/{year}"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    url = f"{IJCAI_BASE_URL}/{year}/proceedings"
                    response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(response.text, year, query, max_results)

        except httpx.HTTPError as e:
            logger.error(f"IJCAI search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"IJCAI search failed: {e}")
            return []

    def _parse_paper_list(
        self, html: str, year: int, query: str, max_results: int
    ) -> List[PaperMetadata]:
        """Parse paper list from IJCAI page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for paper in soup.find_all("div", class_="paper-item"):
            title_elem = paper.find("h4")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            paper_id = f"IJCAI{year}_{len(papers)}"

            authors = []
            authors_elem = paper.find("div", class_="authors")
            if authors_elem:
                authors_text = authors_elem.get_text(strip=True)
                authors = [a.strip() for a in authors_text.split(",")]

            abstract = ""
            pdf_link = paper.find("a", class_="pdf-link")
            pdf_url = pdf_link.get("href", "") if pdf_link else ""

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference="IJCAI",
                    url=pdf_url,
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
        return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        return {
            "status": "error",
            "message": "IJCAI paper download not yet implemented",
        }
