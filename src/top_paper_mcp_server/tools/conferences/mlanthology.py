"""PMLR (Proceedings of Machine Learning Research) paper source for COLT and UAI."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

PMLR_BASE_URL = "https://proceedings.mlr.press"

# Mapping from (conference, year) to PMLR volume number.
# COLT: Conference on Learning Theory (hosted at PMLR since ~2010)
# UAI: Conference on Uncertainty in Artificial Intelligence (hosted at PMLR since 2018)
PMLR_VOLUME_MAP: Dict[tuple, int] = {
    # COLT
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
    ("COLT", 2014): 35,
    ("COLT", 2013): 30,
    ("COLT", 2012): 23,
    ("COLT", 2011): 19,
    ("COLT", 2010): 9,
    # UAI
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

    def _get_volume(self, conference: str, year: int) -> Optional[int]:
        """Return the PMLR volume number for the given conference and year."""
        return PMLR_VOLUME_MAP.get((conference.upper(), year))

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
            logger.warning(f"Unknown conference: {conference}")
            return []

        volume = self._get_volume(conf_upper, year)
        if volume is None:
            logger.warning(f"No PMLR volume mapping for {conference} {year}")
            return []

        url = f"{PMLR_BASE_URL}/v{volume}/"

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "top-paper-mcp-server/0.6.0 (research tool)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_paper_list(
                response.text, conf_upper, year, volume, query, max_results
            )

        except httpx.HTTPError as e:
            logger.error(f"PMLR search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"PMLR search failed: {e}")
            return []

    def _parse_paper_list(
        self,
        html: str,
        conference: str,
        year: int,
        volume: int,
        query: str,
        max_results: int,
    ) -> List[PaperMetadata]:
        """Parse paper list from a PMLR volume index page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        # PMLR volume pages list papers inside <div class="paper"> blocks.
        for paper_div in soup.find_all("div", class_="paper"):
            title_elem = paper_div.find("p", class_="title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            # Extract paper ID from the PDF or abstract link.
            paper_id = ""
            for link in paper_div.find_all("a", href=True):
                href = link["href"]
                m = re.search(r"/v\d+/(\w+)\.html", href)
                if m:
                    paper_id = m.group(1)
                    break

            if not paper_id:
                # Fallback: derive a unique ID from volume + index.
                paper_id = f"v{volume}_{len(papers)}"

            authors_elem = paper_div.find("p", class_="details")
            authors_text = authors_elem.get_text(strip=True) if authors_elem else ""
            authors = [a.strip() for a in authors_text.split(",") if a.strip()] if authors_text else []

            abstract_elem = paper_div.find("p", class_="abstract")
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

            detail_url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.html"
            pdf_url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.pdf"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference=conference,
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
        """Get paper metadata by PMLR paper ID."""
        # Try all known volumes for the conference.
        conf_upper = conference.upper()
        candidate_volumes = [
            vol
            for (conf, _year), vol in PMLR_VOLUME_MAP.items()
            if conf == conf_upper
        ]
        for volume in candidate_volumes:
            url = f"{PMLR_BASE_URL}/v{volume}/{paper_id}.html"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # Derive year from the volume map.
                        year = next(
                            (
                                yr
                                for (conf, yr), vol in PMLR_VOLUME_MAP.items()
                                if conf == conf_upper and vol == volume
                            ),
                            2024,
                        )
                        return self._parse_paper_detail(
                            response.text, paper_id, conference, year, volume
                        )
            except httpx.HTTPError:
                continue
        return None

    def _parse_paper_detail(
        self, html: str, paper_id: str, conference: str, year: int, volume: int
    ) -> Optional[PaperMetadata]:
        """Parse a single PMLR paper detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else ""

        authors: List[str] = []
        authors_div = soup.find("span", class_="authors")
        if authors_div:
            authors = [a.strip() for a in authors_div.get_text(strip=True).split(",")]

        abstract = ""
        abstract_div = soup.find("div", id="abstract")
        if abstract_div:
            abstract = abstract_div.get_text(strip=True)

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
        """Download paper content from PMLR."""
        conf_upper = conference.upper()
        candidate_volumes = [
            (vol, yr)
            for (conf, yr), vol in PMLR_VOLUME_MAP.items()
            if conf == conf_upper
        ]
        for volume, year in candidate_volumes:
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
                            "conference": conference,
                        }
            except httpx.HTTPError:
                continue

        return {
            "status": "error",
            "message": f"Paper {paper_id} not found in PMLR for {conference}",
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from a PMLR paper page."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []

        title = soup.find("h1")
        if title:
            text_parts.append(title.get_text(strip=True))

        authors_span = soup.find("span", class_="authors")
        if authors_span:
            text_parts.append(authors_span.get_text(strip=True))

        abstract_div = soup.find("div", id="abstract")
        if abstract_div:
            text_parts.append(abstract_div.get_text(strip=True))

        return "\n\n".join(text_parts)
