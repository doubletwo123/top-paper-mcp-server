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
        ids[("NEURIPS", year)] = f"NeurIPS.cc/{year}/Conference"
        ids[("ICML", year)] = f"ICML.cc/{year}/Conference"
        ids[("AAAI", year)] = f"AAAI.org/{year}/Conference"
        ids[("IJCAI", year)] = f"IJCAI.org/{year}/Conference"
        ids[("CVPR", year)] = f"CVPR{year}"
        ids[("ICCV", year)] = f"ICCV{year}"
        ids[("WACV", year)] = f"WACV{year}"
        ids[("ECCV", year)] = f"ECCV{year}"
        ids[("ACL", year)] = f"aclweb.org/ACL/{year}/Conference"
        ids[("EMNLP", year)] = f"EMNLP/{year}/Conference"
        ids[("NAACL", year)] = f"NAACL/{year}/Conference"
        ids[("COLM", year)] = f"COLM.org/{year}/Conference"
        ids[("CORL", year)] = f"robot-learning.org/CoRL/{year}/Conference"
        ids[("MLSYS", year)] = f"MLSys.org/{year}/Conference"
        ids[("MICCAI", year)] = f"miccai.org/{year}/Conference"
        ids[("IWSLT", year)] = f"iwslt.org/{year}/Conference"
        ids[("INTERSPEECH", year)] = f"interspeech.org/{year}/Conference"
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

    @staticmethod
    def _get_content_value(content: Dict, key: str, default: Any) -> Any:
        """Extract a field value from OpenReview API v2 content.

        OpenReview API v2 wraps every content field in a ``{"value": ...}``
        object.  This helper unwraps the value transparently so the rest of
        the code never has to deal with the wrapper dict.
        """
        val = content.get(key, default)
        if isinstance(val, dict):
            return val.get("value", default)
        return val if val is not None else default

    @staticmethod
    def _extract_authors(authors_raw: Any) -> List[str]:
        """Normalise an author list returned by OpenReview into plain strings."""
        if not isinstance(authors_raw, list):
            return []
        result = []
        for author in authors_raw:
            if isinstance(author, dict):
                result.append(author.get("name", ""))
            else:
                result.append(str(author))
        return result

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
        # Fetch a larger batch so client-side query filtering has enough
        # candidates. The OpenReview /notes endpoint does not support
        # full-text search, so we filter locally.  The multiplier of 5 (min 100)
        # is a heuristic: assuming ~20 % keyword hit-rate we still fill the
        # requested max_results most of the time without an unreasonably large
        # server-side fetch.
        params = {
            "venueid": venue_id,
            "limit": max(max_results * 5, 100),
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            papers = self._parse_papers(data.get("notes", []), conference, year, query)
            return papers[:max_results]

        except httpx.HTTPError as e:
            logger.error(f"OpenReview search error: {e}")
            return []
        except Exception as e:
            logger.exception(f"OpenReview search failed: {e}")
            return []

    def _parse_papers(
        self, notes: List[Dict], conference: str, year: int, query: str = ""
    ) -> List[PaperMetadata]:
        """Parse OpenReview notes into PaperMetadata.

        OpenReview API v2 wraps every content field in ``{"value": ...}``.
        This method extracts the actual values and optionally filters results
        by the search query (title or abstract match).
        """
        papers = []
        query_lower = query.lower() if query else ""

        for note in notes:
            content = note.get("content", {})

            title = self._get_content_value(content, "title", "")
            abstract = self._get_content_value(content, "abstract", "")

            # Client-side query filtering
            if query_lower and (
                query_lower not in title.lower() and query_lower not in abstract.lower()
            ):
                continue

            authors_raw = self._get_content_value(content, "authors", [])
            authors = self._extract_authors(authors_raw)

            paper_id = note.get("id", "")

            # PDF path from content (API v2 stores it as a relative path)
            pdf_rel = self._get_content_value(content, "pdf", "")
            if pdf_rel:
                pdf_url = f"https://openreview.net{pdf_rel}"
            else:
                pdf_url = f"https://openreview.net/pdf?id={paper_id}"

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

            title = self._get_content_value(content, "title", "")
            authors_raw = self._get_content_value(content, "authors", [])
            authors = self._extract_authors(authors_raw)
            abstract = self._get_content_value(content, "abstract", "")

            text_content = f"# {title}\n\n"
            text_content += f"**Authors:** {', '.join(authors)}\n\n"
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
