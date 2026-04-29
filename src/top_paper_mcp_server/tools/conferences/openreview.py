"""OpenReview paper source for ICLR, NeurIPS, and other conferences."""

import re
import asyncio
import httpx
import logging
from typing import Dict, Any, List, Optional
from .base import ConferenceSource, PaperMetadata

logger = logging.getLogger("top-paper-mcp-server")

OPENREVIEW_BASE_URL = "https://api2.openreview.net"


def _generate_venue_ids():
    """Generate venue IDs for all supported years."""
    ids = {}
    for year in range(2000, 2030):
        ids[("ICLR", year)] = f"ICLR.cc/{year}/Conference"
        ids[("NeurIPS", year)] = f"NeurIPS.cc/{year}"
        ids[("ICML", year)] = f"ICML.cc/{year}/Conference"
        ids[("AAAI", year)] = f"AAAI.org/{year}/Conference"
        ids[("IJCAI", year)] = f"IJCAI.org/{year}/Conference"
        ids[("CVPR", year)] = f"CVPR{year}"
        ids[("ICCV", year)] = f"ICCV{year}"
        ids[("WACV", year)] = f"WACV{year}"
        ids[("ECCV", year)] = f"ECCV{year}"
        ids[("ACL", year)] = f"aclweb.org/{year}"
        ids[("EMNLP", year)] = f"emnlp.org/{year}"
        ids[("NAACL", year)] = f"naacl.org/{year}"
        ids[("COLM", year)] = f"COLM/{year}"
        ids[("CoRL", year)] = f"CoRL.{year}"
        ids[("MLSYS", year)] = f"mlsys.org/{year}"
        ids[("MICCAI", year)] = f"miccai.org/{year}"
        ids[("IWSLT", year)] = f"iwslt.org/{year}"
        ids[("INTERSPEECH", year)] = f"interspeech.org/{year}"
    return ids


VENUE_IDS = _generate_venue_ids()


class OpenReviewSource(ConferenceSource):
    """OpenReview paper source for ICLR, NeurIPS, ICML."""

    @property
    def name(self) -> str:
        return "OpenReview"

    @property
    def conferences(self) -> List[str]:
        return [
            "ICLR",
            "NeurIPS",
            "ICML",
            "AAAI",
            "IJCAI",
            "ACL",
            "EMNLP",
            "NAACL",
            "COLM",
            "CoRL",
            "MLSYS",
            "MICCAI",
            "IWSLT",
            "INTERSPEECH",
        ]

    def _get_venue_id(self, conference: str, year: int) -> Optional[str]:
        """Get OpenReview venue ID for conference."""
        return VENUE_IDS.get((conference.upper(), year))

    async def search(
        self,
        query: str,
        conference: str,
        year: int,
        max_results: int = 10,
    ) -> List[PaperMetadata]:
        """Search papers in OpenReview conference."""
        venue_id = self._get_venue_id(conference, year)
        if not venue_id:
            logger.warning(f"No OpenReview venue ID for {conference} {year}")
            return []

        url = f"{OPENREVIEW_BASE_URL}/notes"
        params = {
            "venueid": venue_id,
            "limit": max_results * 2,
            "details": "content",
        }

        if query:
            params["q"] = f"(title:*{query}*) OR (abstract:*{query}*)"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            papers = self._parse_papers(data.get("notes", []), conference, year)
            return papers[:max_results]

        except httpx.HTTPError as e:
            logger.error(f"OpenReview search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"OpenReview search failed: {e}")
            return []

    def _parse_papers(
        self, notes: List[Dict], conference: str, year: int
    ) -> List[PaperMetadata]:
        """Parse OpenReview notes into PaperMetadata."""
        papers = []
        for note in notes:
            content = note.get("content", {})

            title = content.get("title", "")
            abstract = content.get("abstract", "")

            authors = []
            for author in content.get("authors", []):
                if isinstance(author, dict):
                    authors.append(author.get("name", ""))
                else:
                    authors.append(str(author))

            paper_id = note.get("id", "")

            pdf_url = ""
            for link in note.get("details", {}).get("pdf", {}).get("link", []):
                if link.get("type") == "pdf":
                    pdf_url = link.get("url", "")
                    break

            pdf_url = pdf_url or f"https://openreview.net/pdf?id={paper_id}"

            forum_url = f"https://openreview.net/forum?id={paper_id}"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    conference=conference.upper(),
                    url=forum_url,
                    pdf_url=pdf_url,
                )
            )

        return papers

    async def get_paper(
        self, paper_id: str, conference: str
    ) -> Optional[PaperMetadata]:
        """Get paper metadata by OpenReview ID."""
        url = f"{OPENREVIEW_BASE_URL}/notes"
        params = {
            "id": paper_id,
            "details": "content",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            notes = data.get("notes", [])
            if not notes:
                return None

            year = 2025
            for (conf, y), vid in VENUE_IDS.items():
                if conf.upper() == conference.upper():
                    year = y
                    break

            return self._parse_papers(notes, conference, year)[0]

        except httpx.HTTPError:
            return None
        except Exception as e:
            logger.exception(f"OpenReview get_paper failed: {e}")
            return None

    async def download_paper(self, paper_id: str, conference: str) -> Dict[str, Any]:
        """Download paper content from OpenReview."""
        url = f"{OPENREVIEW_BASE_URL}/notes"
        params = {
            "id": paper_id,
            "details": "content",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            notes = data.get("notes", [])
            if not notes:
                return {"status": "error", "message": f"Paper {paper_id} not found"}

            note = notes[0]
            content = note.get("content", {})

            text_content = f"# {content.get('title', '')}\n\n"
            text_content += f"**Authors:** {', '.join(content.get('authors', []))}\n\n"
            text_content += f"**Abstract:** {content.get('abstract', '')}\n\n"

            return {
                "status": "success",
                "paper_id": paper_id,
                "source": "openreview",
                "content": text_content,
                "conference": conference.upper(),
            }

        except httpx.HTTPError as e:
            return {"status": "error", "message": f"HTTP error: {e}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
