"""AAAI and IJCAI paper source via official conference websites."""

import re
import httpx
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
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
        issue_url = await self._resolve_issue_url(year)
        if not issue_url:
            logger.warning(f"AAAI issue not found for year {year}")
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(issue_url)
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

        article_blocks = soup.select("article.article, div.obj_article_summary")
        for article in article_blocks:
            title_elem = article.find("a", class_="title") or article.find(
                "h3", class_="title"
            )
            if not title_elem:
                title_elem = article.find("a", href=True)

            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            abstract_elem = article.find("div", class_="abstract") or article.find(
                "div", class_="abstracts"
            )
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else ""

            if query and query_lower not in f"{title} {abstract}".lower():
                continue

            href = title_elem.get("href", "")
            href = urljoin(AAAI_BASE_URL, href)
            paper_id_match = re.search(r"(\d+)", href)
            paper_id = paper_id_match.group(1) if paper_id_match else f"AAAI{year}"

            authors = []
            authors_elem = article.find("div", class_="authors")
            if authors_elem:
                authors = [a.get_text(strip=True) for a in authors_elem.find_all("a")]

            pdf_link = article.find("a", href=re.compile(r"/download/"))
            pdf_url = urljoin(AAAI_BASE_URL, pdf_link["href"]) if pdf_link else href

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

    async def _resolve_issue_url(self, year: int) -> Optional[str]:
        archive_url = f"{AAAI_BASE_URL}/AAAI/issue/archive"
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(archive_url)
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"AAAI archive fetch error: {e}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        year_str = str(year)
        for link in soup.find_all("a", href=True):
            if "/issue/view/" not in link["href"]:
                continue
            text_parts = [link.get_text(" ", strip=True)]
            parent = link.find_parent(["div", "li"])
            if parent:
                text_parts.append(parent.get_text(" ", strip=True))
            text = " ".join(part for part in text_parts if part)
            if year_str in text:
                return urljoin(AAAI_BASE_URL, link["href"])

        return None

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by ID."""
        url = f"{AAAI_BASE_URL}/AAAI/article/view/{paper_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
            return self._parse_article_detail(response.text, paper_id)
        except httpx.HTTPError:
            return None
        except Exception as e:
            logger.exception(f"AAAI get_paper failed: {e}")
            return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        url = f"{AAAI_BASE_URL}/AAAI/article/view/{paper_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
            metadata = self._parse_article_detail(response.text, paper_id)
            if not metadata:
                return {
                    "status": "error",
                    "message": f"Paper {paper_id} not found in AAAI",
                }
            text_content = f"# {metadata.title}\n\n"
            if metadata.authors:
                text_content += f"**Authors:** {', '.join(metadata.authors)}\n\n"
            if metadata.abstract:
                text_content += f"**Abstract:** {metadata.abstract}\n\n"
            return {
                "status": "success",
                "paper_id": paper_id,
                "source": "aaai_html",
                "content": text_content,
                "year": metadata.year,
                "conference": metadata.conference,
            }
        except httpx.HTTPError as e:
            return {"status": "error", "message": f"HTTP error: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _parse_article_detail(
        self, html: str, paper_id: str
    ) -> Optional[PaperMetadata]:
        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_meta_value(
            soup, ["citation_title", "dc.Title", "og:title"]
        )
        if not title:
            title_elem = soup.find(["h1", "h2"], class_="page_title") or soup.find(
                ["h1", "h2"]
            )
            title = title_elem.get_text(strip=True) if title_elem else ""

        authors = self._extract_meta_values(soup, "citation_author")
        if not authors:
            authors_div = soup.find("div", class_="authors")
            if authors_div:
                authors = [
                    a.get_text(strip=True) for a in authors_div.find_all("a")
                ]

        abstract = self._extract_meta_value(
            soup, ["citation_abstract", "dc.Description", "og:description"]
        )
        if not abstract:
            abstract_div = soup.find("div", class_="abstract")
            abstract = abstract_div.get_text(strip=True) if abstract_div else ""

        year = self._extract_year(soup) or 2024

        pdf_url = self._extract_meta_value(soup, ["citation_pdf_url"])
        pdf_url = urljoin(AAAI_BASE_URL, pdf_url) if pdf_url else ""

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference="AAAI",
            url=f"{AAAI_BASE_URL}/AAAI/article/view/{paper_id}",
            pdf_url=pdf_url,
        )

    @staticmethod
    def _extract_meta_value(soup: BeautifulSoup, names: List[str]) -> str:
        for name in names:
            meta = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            if meta and meta.get("content"):
                return meta["content"]
        return ""

    @staticmethod
    def _extract_meta_values(soup: BeautifulSoup, name: str) -> List[str]:
        values = []
        for meta in soup.find_all("meta", attrs={"name": name}):
            content = meta.get("content")
            if content:
                values.append(content)
        return values

    @staticmethod
    def _extract_year(soup: BeautifulSoup) -> Optional[int]:
        date_meta = soup.find("meta", attrs={"name": "citation_publication_date"})
        if date_meta and date_meta.get("content"):
            match = re.search(r"(\d{4})", date_meta["content"])
            if match:
                return int(match.group(1))
        return None


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

            authors = []
            authors_elem = paper.find("div", class_="authors")
            if authors_elem:
                authors_text = authors_elem.get_text(strip=True)
                authors = [a.strip() for a in authors_text.split(",")]

            abstract = ""
            pdf_link = paper.find("a", class_="pdf-link")
            pdf_url = pdf_link.get("href", "") if pdf_link else ""
            pdf_url = urljoin(IJCAI_BASE_URL, pdf_url)

            paper_id_match = re.search(r"/(\d+)\.pdf", pdf_url)
            paper_id = (
                paper_id_match.group(1) if paper_id_match else f"IJCAI{year}_{len(papers)}"
            )

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
        for year in range(2018, 2031):
            url = f"{IJCAI_BASE_URL}/proceedings/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        return self._parse_paper_detail(response.text, paper_id, year)
            except httpx.HTTPError:
                continue
        return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content."""
        for year in range(2018, 2031):
            url = f"{IJCAI_BASE_URL}/proceedings/{year}/{paper_id}"
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        metadata = self._parse_paper_detail(
                            response.text, paper_id, year
                        )
                        if not metadata:
                            continue
                        text_content = f"# {metadata.title}\n\n"
                        if metadata.authors:
                            text_content += (
                                f"**Authors:** {', '.join(metadata.authors)}\n\n"
                            )
                        if metadata.abstract:
                            text_content += f"**Abstract:** {metadata.abstract}\n\n"
                        return {
                            "status": "success",
                            "paper_id": paper_id,
                            "source": "ijcai_html",
                            "content": text_content,
                            "year": metadata.year,
                            "conference": metadata.conference,
                        }
            except httpx.HTTPError:
                continue
        return {
            "status": "error",
            "message": "IJCAI paper download not yet implemented",
        }

    def _parse_paper_detail(
        self, html: str, paper_id: str, year: int
    ) -> Optional[PaperMetadata]:
        soup = BeautifulSoup(html, "html.parser")
        title = ""
        title_meta = soup.find("meta", property="og:title")
        if title_meta and title_meta.get("content"):
            title = title_meta["content"]
        if not title:
            title_elem = soup.find(["h1", "h2"])
            title = title_elem.get_text(strip=True) if title_elem else ""

        abstract = ""
        abstract_meta = soup.find("meta", property="og:description")
        if abstract_meta and abstract_meta.get("content"):
            abstract = abstract_meta["content"]

        authors = []
        for meta in soup.find_all("meta", attrs={"name": "citation_author"}):
            if meta.get("content"):
                authors.append(meta["content"])
        if not authors:
            authors_div = soup.find("div", class_="authors")
            if authors_div:
                authors_text = authors_div.get_text(" ", strip=True)
                authors = [a.strip() for a in authors_text.split(",") if a.strip()]

        pdf_url = f"{IJCAI_BASE_URL}/proceedings/{year}/{paper_id}.pdf"

        return PaperMetadata(
            paper_id=paper_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            conference="IJCAI",
            url=f"{IJCAI_BASE_URL}/proceedings/{year}/{paper_id}",
            pdf_url=pdf_url,
        )
