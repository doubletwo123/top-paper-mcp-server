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
        ids[("NeurIPS", year)] = f"NeurIPS.cc/{year}/Conference"
        ids[("ICML", year)] = f"ICML.cc/{year}/Conference"
        ids[("AAAI", year)] = f"AAAI.org/{year}/Conference"
        ids[("IJCAI", year)] = f"IJCAI.org/{year}/Conference"
        ids[("CVPR", year)] = f"CVPR.cc/{year}/Conference"
        ids[("ICCV", year)] = f"ICCV.cc/{year}/Conference"
        ids[("WACV", year)] = f"WACV.cc/{year}/Conference"
        ids[("ECCV", year)] = f"ECCV.cc/{year}/Conference"
        ids[("ACL", year)] = f"ACL/Association_for_Computational_Linguistics/{year}"
        ids[("EMNLP", year)] = f"EMNLP/Association_for_Computational_Linguistics/{year}"
        ids[("NAACL", year)] = f"NAACL/Association_for_Computational_Linguistics/{year}"
        ids[("COLM", year)] = f"COLM/{year}"
        ids[("CoRL", year)] = f"CoRL/{year}/Conference"
        ids[("MLSYS", year)] = f"mlsys.org/{year}/Conference"
        ids[("MICCAI", year)] = f"miccai.org/{year}/Conference"
        ids[("IWSLT", year)] = f"IWSLT/{year}"
        ids[("INTERSPEECH", year)] = f"INTERSPEECH/{year}"
    return ids


VENUE_IDS = _generate_venue_ids()


def _extract_content_value(field: Any) -> str:
    """Extract value from OpenReview API v2 content field.

    API v2 returns content fields as {'value': ...} dicts.
    API v1 returns content fields as plain strings.
    This helper handles both formats.
    """
    if isinstance(field, dict):
        return field.get("value", "")
    if isinstance(field, list):
        return field
    return field or ""


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
        conf_upper = conference.upper()
        result = VENUE_IDS.get((conf_upper, year))
        if result:
            return result
        for (conf_key, y), venue_id in VENUE_IDS.items():
            if conf_key.upper() == conf_upper and y == year:
                return venue_id
        return None

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

        try:
            if query:
                url = f"{OPENREVIEW_BASE_URL}/notes/search"
                params = {
                    "query": query,
                    "source": "forum",
                    "limit": max_results,
                    "group": venue_id,
                }
            else:
                url = f"{OPENREVIEW_BASE_URL}/notes"
                invitation = f"{venue_id}/-/Submission"
                params = {
                    "invitation": invitation,
                    "limit": max_results,
                    "details": "content",
                }

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

            title = _extract_content_value(content.get("title", ""))
            abstract = _extract_content_value(content.get("abstract", ""))

            authors_raw = _extract_content_value(content.get("authors", []))
            authors = []
            if isinstance(authors_raw, list):
                for author in authors_raw:
                    if isinstance(author, dict):
                        authors.append(author.get("name", str(author)))
                    else:
                        authors.append(str(author))
            elif isinstance(authors_raw, str) and authors_raw:
                authors = [authors_raw]

            paper_id = note.get("id", "")

            pdf_url = f"https://openreview.net/pdf?id={paper_id}"
            forum_url = f"https://openreview.net/forum?id={paper_id}"

            papers.append(
                PaperMetadata(
                    paper_id=paper_id,
                    title=str(title),
                    authors=authors,
                    abstract=str(abstract),
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

            paper_year = 2025
            for (conf, y), vid in VENUE_IDS.items():
                if conf.upper() == conference.upper():
                    paper_year = y
                    break

            return self._parse_papers(notes, conference, paper_year)[0]

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

            title = _extract_content_value(content.get("title", ""))
            abstract = _extract_content_value(content.get("abstract", ""))
            authors_raw = _extract_content_value(content.get("authors", []))
            if isinstance(authors_raw, list):
                authors_str = ", ".join(str(a) for a in authors_raw)
            else:
                authors_str = str(authors_raw)

            text_content = f"# {title}\n\n"
            text_content += f"**Authors:** {authors_str}\n\n"
            text_content += f"**Abstract:** {abstract}\n\n"

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
