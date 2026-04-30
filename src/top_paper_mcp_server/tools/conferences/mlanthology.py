"""PMLR (Proceedings of Machine Learning Research) paper source."""

import asyncio
import re
import httpx
import logging
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

PMLR_BASE_URL = "https://proceedings.mlr.press"
VENUE_KEYWORDS = {
    "COLT": ["Conference on Learning Theory", "COLT", "Learning Theory"],
    "UAI": ["Uncertainty in Artificial Intelligence", "UAI"],
}


class MLAnthologySource(ConferenceSource):
    """PMLR paper source for COLT/UAI proceedings."""

    def __init__(self) -> None:
        self._volume_index: Dict[Tuple[str, int], str] = {}
        self._index_loaded = False
        self._index_lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "MLAnthology"

    @property
    def conferences(self) -> List[str]:
        return list(VENUE_KEYWORDS.keys())

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in PMLR."""
        conference_key = conference.upper()
        if conference_key not in VENUE_KEYWORDS:
            logger.warning(f"Unknown conference: {conference}")
            return []

        volume = await self._get_volume(conference_key, year)
        if not volume:
            logger.warning(f"No PMLR volume found for {conference_key} {year}")
            return []

        url = f"{PMLR_BASE_URL}/v{volume}/"

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(
                response.text, conference_key, year, volume, query, max_results
            )

        except httpx.HTTPError as e:
            logger.error(f"PMLR search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"PMLR search failed: {e}")
            return []

    async def _get_volume(self, conference: str, year: int) -> Optional[str]:
        await self._load_volume_index()
        return self._volume_index.get((conference, year))

    async def _load_volume_index(self) -> None:
        if self._index_loaded:
            return
        async with self._index_lock:
            if self._index_loaded:
                return
            self._index_loaded = True

            try:
                async with httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=True,
                    headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
                ) as client:
                    response = await client.get(PMLR_BASE_URL)
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to load PMLR index: {e}")
                return

            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                volume_match = re.search(r"/v(\d+)/", href)
                if not volume_match:
                    continue
                volume = volume_match.group(1)

                text_parts = [link.get_text(" ", strip=True)]
                parent = link.find_parent(["li", "div", "p"])
                if parent:
                    text_parts.append(parent.get_text(" ", strip=True))
                text = " ".join(part for part in text_parts if part)
                if not text:
                    continue

                year_match = re.search(r"\b(20\d{2})\b", text)
                if not year_match:
                    continue
                year = int(year_match.group(1))

                text_lower = text.lower()
                for conf, keywords in VENUE_KEYWORDS.items():
                    if any(keyword.lower() in text_lower for keyword in keywords):
                        self._volume_index.setdefault((conf, year), volume)

    def _parse_paper_list(
        self,
        html: str,
        conference: str,
        year: int,
        volume: str,
        query: str,
        max_results: int,
    ) -> List[PaperMetadata]:
        """Parse paper list from PMLR volume page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for paper in soup.find_all("div", class_="paper"):
            title_link = paper.find("a", href=re.compile(r"\.html?$"))
            title_elem = paper.find(["p", "h3", "h4"], class_="title") or title_link
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            authors_elem = paper.find(["p", "div", "span"], class_="authors")
            authors_text = authors_elem.get_text(" ", strip=True) if authors_elem else ""
            authors = (
                [a.strip() for a in re.split(r",| and ", authors_text) if a.strip()]
                if authors_text
                else []
            )

            pdf_link = paper.find("a", href=re.compile(r"\.pdf$"))
            paper_href = ""
            if title_link and title_link.get("href"):
                paper_href = title_link["href"]
            elif pdf_link and pdf_link.get("href"):
                paper_href = pdf_link["href"]

            paper_id = paper_href.rsplit("/", 1)[-1].split(".")[0] if paper_href else ""
            if not paper_id:
                continue

            url = self._absolute_url(
                paper_href if paper_href.endswith(".html") else f"{paper_id}.html",
                volume,
            )
            pdf_url = self._absolute_url(
                pdf_link["href"] if pdf_link else f"{paper_id}.pdf", volume
            )

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract="",
                    year=year,
                    conference=conference,
                    url=url,
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
        await self._load_volume_index()
        conference_key = conference.upper()
        volumes = [
            (year, volume)
            for (conf, year), volume in self._volume_index.items()
            if conf == conference_key
        ]
        for year, volume in sorted(volumes, reverse=True):
            url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.html"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return self._parse_paper_detail(
                            response.text, paper_id, conference_key, year, volume
                        )
            except httpx.HTTPError:
                continue
        return None

    def _parse_paper_detail(
        self, html: str, paper_id: str, conference: str, year: int, volume: str
    ) -> Optional[PaperMetadata]:
        """Parse single paper detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.find(["h1", "h2", "h3"])
        title = title_elem.get_text(strip=True) if title_elem else ""

        authors = []
        authors_div = soup.find(["div", "p", "span"], class_="authors")
        if authors_div:
            authors_text = authors_div.get_text(" ", strip=True)
            authors = [a.strip() for a in re.split(r",| and ", authors_text) if a.strip()]

        abstract = ""
        abstract_div = soup.find(["div", "p"], class_="abstract")
        if abstract_div:
            abstract = abstract_div.get_text(" ", strip=True)

        pdf_url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.pdf"

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference=conference,
            url=f"{PMLR_BASE_URL}/v{volume}/{paper_id}.html",
            pdf_url=pdf_url,
        )

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        await self._load_volume_index()
        conference_key = conference.upper()
        volumes = [
            (year, volume)
            for (conf, year), volume in self._volume_index.items()
            if conf == conference_key
        ]
        for year, volume in sorted(volumes, reverse=True):
            url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.html"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return {
                            "status": "success",
                            "paper_id": paper_id,
                            "source": "pmlr_html",
                            "content": self._extract_text_from_html(response.text),
                            "year": year,
                            "conference": conference_key,
                        }
            except httpx.HTTPError:
                continue

        return {
            "status": "error",
            "message": f"Paper {paper_id} not found in PMLR",
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from paper HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []

        title = soup.find(["h1", "h2", "h3"])
        if title:
            text_parts.append(title.get_text(strip=True))

        authors_div = soup.find(["div", "p", "span"], class_="authors")
        if authors_div:
            text_parts.append(authors_div.get_text(strip=True))

        abstract_div = soup.find(["div", "p"], class_="abstract")
        if abstract_div:
            text_parts.append(abstract_div.get_text(strip=True))

        return "\n\n".join(text_parts)

    @staticmethod
    def _absolute_url(href: str, volume: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{PMLR_BASE_URL}{href}"
        return f"{PMLR_BASE_URL}/v{volume}/{href}"
