"""PMLR (Proceedings of Machine Learning Research) paper source for COLT and UAI."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

PMLR_BASE_URL = "https://proceedings.mlr.press"

# Static mapping of (conference, year) → PMLR volume number for recent years.
# These are updated through 2024. For years not listed the source will fall
# back to scraping the PMLR proceedings index to find the volume dynamically.
PMLR_VOLUME_MAP: Dict[Tuple[str, int], int] = {
    # COLT volumes
    ("COLT", 2024): 247,
    ("COLT", 2023): 195,
    ("COLT", 2022): 178,
    ("COLT", 2021): 134,
    ("COLT", 2020): 125,
    ("COLT", 2019): 99,
    ("COLT", 2018): 75,
    ("COLT", 2017): 65,
    ("COLT", 2016): 49,
    ("COLT", 2015): 40,
    # UAI volumes
    ("UAI", 2024): 244,
    ("UAI", 2023): 216,
    ("UAI", 2022): 180,
    ("UAI", 2021): 161,
    ("UAI", 2020): 124,
    ("UAI", 2019): 115,
    ("UAI", 2018): 73,
}

VENUE_MAP = {
    "COLT": "COLT",
    "UAI": "UAI",
}


class MLAnthologySource(ConferenceSource):
    """PMLR paper source for COLT and UAI conferences."""

    @property
    def name(self) -> str:
        return "PMLR"

    @property
    def conferences(self) -> List[str]:
        return list(VENUE_MAP.keys())

    async def _find_volume(
        self, conference: str, year: int, client: httpx.AsyncClient
    ) -> Optional[int]:
        """Find the PMLR volume number for a conference and year.

        First checks the static map; if not found, scrapes the PMLR proceedings
        index page to discover the volume dynamically.
        """
        static = PMLR_VOLUME_MAP.get((conference.upper(), year))
        if static:
            return static

        # Dynamic fallback: scrape the PMLR index
        try:
            response = await client.get(PMLR_BASE_URL + "/")
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            conf_upper = conference.upper()
            for link in soup.find_all("a", href=re.compile(r"^/v\d+")):
                text = link.get_text(" ", strip=True)
                # Match lines like "Proceedings of ... COLT 2023"
                if conf_upper in text.upper() and str(year) in text:
                    m = re.search(r"/v(\d+)", link["href"])
                    if m:
                        return int(m.group(1))
        except Exception as e:
            logger.warning(f"PMLR index scrape failed: {e}")
        return None

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in a PMLR-hosted conference."""
        conf_upper = conference.upper()
        if conf_upper not in VENUE_MAP:
            logger.warning(f"Unknown conference for PMLR source: {conference}")
            return []

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
            ) as client:
                volume = await self._find_volume(conf_upper, year, client)
                if volume is None:
                    logger.warning(
                        f"No PMLR volume found for {conference} {year}"
                    )
                    return []

                url = f"{PMLR_BASE_URL}/v{volume}/"
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(
                response.text, conference, year, query, max_results
            )

        except httpx.HTTPError as e:
            logger.error(f"PMLR search error for {conference} {year}: {e}")
            return []
        except Exception as e:
            logger.exception(f"PMLR search failed for {conference} {year}: {e}")
            return []

    def _parse_paper_list(
        self,
        html: str,
        conference: str,
        year: int,
        query: str,
        max_results: int,
    ) -> List[PaperMetadata]:
        """Parse paper list from a PMLR volume page.

        PMLR volume pages list papers as ``<div class="paper">`` blocks
        containing a ``<p class="title">`` and a ``<p class="details">`` with
        author names and PDF/abstract links.
        """
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for paper_div in soup.find_all("div", class_="paper"):
            title_elem = paper_div.find("p", class_="title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            # Extract paper id from the abstract link href
            paper_id = ""
            abs_link = paper_div.find("a", string=re.compile(r"abs", re.I))
            if abs_link:
                m = re.search(r"/v\d+/(\S+)\.html", abs_link.get("href", ""))
                if m:
                    paper_id = m.group(1)

            # Maximum number of characters used when generating a fallback slug
            _MAX_SLUG_CHARS = 40

            if not paper_id:
                # Fallback: generate a slug from the title
                paper_id = re.sub(r"\W+", "_", title[:_MAX_SLUG_CHARS]).strip("_").lower()

            authors: List[str] = []
            details = paper_div.find("p", class_="details")
            if details:
                authors_span = details.find("span", class_="authors")
                if authors_span:
                    authors = [
                        a.strip()
                        for a in authors_span.get_text(strip=True).split(",")
                        if a.strip()
                    ]

            # Construct PDF and abstract URLs
            pdf_link = paper_div.find("a", string=re.compile(r"pdf", re.I))
            if pdf_link:
                pdf_href = pdf_link.get("href", "")
                pdf_url = (
                    pdf_href
                    if pdf_href.startswith("http")
                    else PMLR_BASE_URL + pdf_href
                )
            else:
                pdf_url = ""

            abs_href = abs_link.get("href", "") if abs_link else ""
            paper_url = (
                abs_href
                if abs_href.startswith("http")
                else PMLR_BASE_URL + abs_href
            )

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract="",
                    year=year,
                    conference=conference.upper(),
                    url=paper_url,
                    pdf_url=pdf_url,
                )
            )

            if len(papers) >= max_results:
                break

        return papers

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by ID (not implemented for PMLR)."""
        return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content (not implemented for PMLR)."""
        return {
            "status": "error",
            "message": (
                f"Direct paper download not supported for {conference} via PMLR. "
                f"Please access the paper via its URL from search results."
            ),
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from paper HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []

        title = soup.find("h2", class_="title")
        if not title:
            title = soup.find("h2")
        if title:
            text_parts.append(title.get_text(strip=True))

        authors_div = soup.find("span", class_="authors")
        if authors_div:
            text_parts.append(authors_div.get_text(strip=True))

        abstract_div = soup.find("div", id="abstract")
        if abstract_div:
            text_parts.append(abstract_div.get_text(strip=True))

        return "\n\n".join(text_parts)
