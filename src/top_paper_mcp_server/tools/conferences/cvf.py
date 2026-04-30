"""CVF (Computer Vision Foundation) paper source for CVPR, ICCV, WACV."""

import re
import asyncio
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

CVF_BASE_URL = "https://openaccess.thecvf.com"

CVF_CONFERENCES = {
    "CVPR": "CVPR",
    "ICCV": "ICCV",
    "WACV": "WACV",
    "ECCV": "ECCV",
}

CVF_YEAR_RANGE = (2000, 2030)


class CVFSource(ConferenceSource):
    """CVF paper source for CVPR, ICCV, and WACV conferences."""

    @property
    def name(self) -> str:
        return "CVF"

    @property
    def conferences(self) -> List[str]:
        return ["CVPR", "ICCV", "WACV"]

    def _get_conf_year(self, conference: str, year: int) -> str:
        """Get conference-year folder name."""
        conf = CVF_CONFERENCES.get(conference.upper())
        if not conf:
            raise ValueError(f"Unsupported conference: {conference}")
        return f"{conf}{year}"

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in CVF conference."""
        conf_year = self._get_conf_year(conference, year)
        url = f"{CVF_BASE_URL}/{conf_year}"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text

            papers = self._parse_paper_list(html, conference, year, query, max_results)
            return papers

        except httpx.HTTPError as e:
            logger.error(f"CVF search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"CVF search failed: {e}")
            return []

    def _parse_paper_list(
        self, html: str, conference: str, year: int, query: str, max_results: int
    ) -> List[PaperMetadata]:
        """Parse paper list from conference page."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        def _matches_query(title_text: str, abstract_text: str) -> bool:
            if not query_lower:
                return True
            combined = f"{title_text} {abstract_text}".lower()
            return query_lower in combined

        for title_dt in soup.find_all("dt", class_="ptitle"):
            title_link = title_dt.find("a", href=True)
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = title_link["href"]

            paper_dd = title_dt.find_next_sibling("dd")
            authors = []
            abstract = ""
            if paper_dd:
                authors_div = paper_dd.find("div", class_="authors")
                authors_text = (
                    authors_div.get_text(strip=True) if authors_div else ""
                )
                authors = (
                    [a.strip() for a in authors_text.split(",")]
                    if authors_text
                    else []
                )

                abstract_div = paper_dd.find("div", class_="abstract")
                abstract = abstract_div.get_text(strip=True) if abstract_div else ""

            if not _matches_query(title, abstract):
                continue

            paper_id = ""
            match = re.search(r"/content/[^/]+/html/([^/]+)\.html", href)
            if match:
                paper_id = match.group(1)
            else:
                paper_id = href.rsplit("/", 1)[-1].split(".")[0]

            if not paper_id:
                continue

            pdf_href = href
            if "/html/" in pdf_href:
                pdf_href = pdf_href.replace("/html/", "/papers/")
            pdf_href = pdf_href.replace(".html", ".pdf")

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference=conference.upper(),
                    url=f"{CVF_BASE_URL}{href}",
                    pdf_url=f"{CVF_BASE_URL}{pdf_href}",
                )
            )

            if len(papers) >= max_results:
                break

        if papers:
            return papers

        for paper_div in soup.find_all("dd"):
            title_link = paper_div.find("a", href=True)
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = title_link["href"]

            authors_div = paper_div.find("div", class_="authors")
            authors_text = authors_div.get_text(strip=True) if authors_div else ""
            authors = (
                [a.strip() for a in authors_text.split(",")] if authors_text else []
            )

            abstract_div = paper_div.find("div", class_="abstract")
            abstract = abstract_div.get_text(strip=True) if abstract_div else ""

            if not _matches_query(title, abstract):
                continue

            match = re.search(r"/content/(\w+\d+)/(\w+)\.html", href)
            if not match:
                continue

            paper_id = match.group(2)

            pdf_url = href.replace(".html", ".pdf")

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference=conference.upper(),
                    url=f"{CVF_BASE_URL}{href}",
                    pdf_url=f"{CVF_BASE_URL}{pdf_url}",
                )
            )

            if len(papers) >= max_results:
                break

        return papers

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by ID."""
        conf_year = self._get_conf_year(conference, 0)

        for year in range(2020, 2030):
            conf_year = self._get_conf_year(conference, year)
            html_url = f"{CVF_BASE_URL}/{conf_year}/{paper_id}.html"

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(html_url)
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

        title_elem = soup.find("div", class_="preprint-title")
        title = title_elem.get_text(strip=True) if title_elem else ""

        authors_div = soup.find("div", class_="authors")
        authors_text = authors_div.get_text(strip=True) if authors_div else ""
        authors = [a.strip() for a in authors_text.split(",")]

        abstract_div = soup.find("div", class_="abstract")
        abstract = abstract_div.get_text(strip=True) if abstract_div else ""

        pdf_url = f"{CVF_BASE_URL}/{conference.upper()}{year}/{paper_id}.pdf"

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference=conference.upper(),
            url=f"{CVF_BASE_URL}/{conference.upper()}{year}/{paper_id}.html",
            pdf_url=pdf_url,
        )

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        for year in range(2020, 2030):
            conf_year = self._get_conf_year(conference, year)
            html_url = f"{CVF_BASE_URL}/{conf_year}/{paper_id}.html"

            try:
                async with httpx.AsyncClient(
                    timeout=30.0, follow_redirects=True
                ) as client:
                    response = await client.get(html_url)
                    if response.status_code == 200:
                        return {
                            "status": "success",
                            "paper_id": paper_id,
                            "source": "cvf_html",
                            "content": self._extract_text_from_html(response.text),
                            "year": year,
                            "conference": conference.upper(),
                        }
            except httpx.HTTPError:
                continue

        return {
            "status": "error",
            "message": f"Paper {paper_id} not found in {conference}",
        }

    def _extract_text_from_html(self, html: str) -> str:
        """Extract readable text from paper HTML."""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text_parts = []
        for p in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
            text = p.get_text(strip=True)
            if text:
                text_parts.append(text)

        return "\n\n".join(text_parts)
