"""ACM Digital Library paper source."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

ACM_BASE_URL = "https://dl.acm.org"

ACM_CONFERENCES = {
    "SIGGRAPH": "SIGGRAPH",
    "SIGGRAPH_ASIA": "SIGGRAPH Asia",
    "CHI": "CHI",
    "UIST": "UIST",
    "UbiComp": "UbiComp",
    "MobiCom": "MobiCom",
    "WWW": "WWW",
    "SIGIR": "SIGIR",
    "KDD": "KDD",
    "AAIM": "AAIM",
    "IJCAI": "IJCAI",
}


class ACMSource(ConferenceSource):
    """ACM Digital Library paper source."""

    @property
    def name(self) -> str:
        return "ACM"

    @property
    def conferences(self) -> List[str]:
        return list(ACM_CONFERENCES.keys())

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in ACM Digital Library."""
        search_url = f"{ACM_BASE_URL}/action/doSearch"

        params = {
            "AllField": query,
            "expand": "dl",
            "pageSize": max_results,
        }

        if conference:
            params["ContentItemType"] = "research-article"

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
            ) as client:
                response = await client.get(search_url, params=params)

                if response.status_code == 200:
                    return self._parse_search_results(
                        response.text, conference, year, query, max_results
                    )
                else:
                    logger.warning(f"ACM search returned {response.status_code}")
                    return []

        except httpx.HTTPError as e:
            logger.error(f"ACM search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"ACM search failed: {e}")
            return []

    def _parse_search_results(
        self,
        html: str,
        conference: str,
        year: int,
        query: str,
        max_results: int,
    ) -> List[PaperMetadata]:
        """Parse ACM search results."""
        soup = BeautifulSoup(html, "html.parser")
        papers = []
        query_lower = query.lower()

        for result in soup.find_all("div", class_="result__item"):
            title_elem = result.find("a", class_="result__title")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if query and query_lower not in title.lower():
                continue

            href = title_elem.get("href", "")
            paper_id_match = re.search(r"doi/([^?]+)", href)
            paper_id = paper_id_match.group(1) if paper_id_match else ""

            authors = []
            authors_elem = result.find("div", class_="result__contributors")
            if authors_elem:
                for a in authors_elem.find_all("a"):
                    authors.append(a.get_text(strip=True))

            abstract = ""
            abstract_elem = result.find("div", class_="result__abstract")
            if abstract_elem:
                abstract = abstract_elem.get_text(strip=True)

            pdf_url = f"{ACM_BASE_URL}/doi/pdf/10.1145/{paper_id}" if paper_id else ""

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference="ACM",
                    url=f"{ACM_BASE_URL}/doi/10.1145/{paper_id}",
                    pdf_url=pdf_url,
                )
            )

            if len(papers) >= max_results:
                break

        return papers

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by DOI."""
        url = f"{ACM_BASE_URL}/doi/10.1145/{paper_id}"

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "top-paper-mcp-server/0.5.0 (research tool)"},
            ) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return self._parse_paper_detail(response.text, paper_id)
        except httpx.HTTPError:
            pass

        return None

    def _parse_paper_detail(self, html: str, paper_id: str) -> Optional[PaperMetadata]:
        """Parse single paper detail page."""
        soup = BeautifulSoup(html, "html.parser")

        title_elem = soup.find("meta", property="og:title")
        title = title_elem.get("content", "") if title_elem else ""

        authors = []
        authors_div = soup.find("div", class_="citation__authors")
        if authors_div:
            for a in authors_div.find_all("a"):
                authors.append(a.get_text(strip=True))

        abstract_elem = soup.find("meta", property="og:description")
        abstract = abstract_elem.get("content", "") if abstract_elem else ""

        pdf_url = f"{ACM_BASE_URL}/doi/pdf/10.1145/{paper_id}"

        year_match = re.search(r"(\d{4})", html)
        year = int(year_match.group(1)) if year_match else 2024

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference="ACM",
            url=f"{ACM_BASE_URL}/doi/10.1145/{paper_id}",
            pdf_url=pdf_url,
        )

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content - requires authentication."""
        return {
            "status": "error",
            "message": "ACM PDF download requires institutional access or subscription. "
            "Please access papers via the URL provided in search results.",
        }
