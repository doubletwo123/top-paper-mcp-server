"""Related papers discovery via Semantic Scholar API.

Uses Semantic Scholar's Recommendations API and citation graph to find
papers related to a given paper.

API docs: https://api.semanticscholar.org/api-docs/
- Recommendations: GET /recommendations/v1/papers/?positivePaperIds=...
- Citations/References: GET /graph/v1/paper/{id}?fields=references,citations
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
import mcp.types as types
from mcp.types import ToolAnnotations

logger = logging.getLogger("top-paper-mcp-server")

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org"
S2_TIMEOUT = 20.0
S2_FIELDS = "paperId,title,abstract,year,venue,citationCount,url,openAccessPdf,authors"


async def _s2_get(
    endpoint: str, params: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Make a GET request to Semantic Scholar API."""
    url = f"{SEMANTIC_SCHOLAR_BASE}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=S2_TIMEOUT) as client:
            response = await client.get(url, params=params)
            if response.status_code == 404:
                return None
            if response.status_code == 429:
                logger.warning("Semantic Scholar rate limited")
                return None
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"Semantic Scholar API error: {e}")
        return None
    except Exception as e:
        logger.exception(f"Semantic Scholar API failed: {e}")
        return None


def _normalize_arxiv_id(paper_id: str) -> str:
    """Normalize arXiv ID for Semantic Scholar (e.g., '2401.12345' -> 'ARXIV:2401.12345')."""
    if (
        paper_id.startswith("ARXIV:")
        or paper_id.startswith("Corr:")
        or paper_id.startswith("DOI:")
    ):
        return paper_id
    # Looks like an arXiv ID
    if "." in paper_id and paper_id[0].isdigit():
        return f"ARXIV:{paper_id}"
    return paper_id


def _format_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Semantic Scholar paper dict into our standard format."""
    authors = paper.get("authors", [])
    author_names = [a.get("name", "") for a in authors] if authors else []

    return {
        "id": paper.get("paperId", ""),
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract", ""),
        "authors": author_names,
        "year": paper.get("year"),
        "venue": paper.get("venue", ""),
        "citation_count": paper.get("citationCount", 0),
        "url": paper.get("url", ""),
        "pdf_url": (paper.get("openAccessPdf") or {}).get("url", ""),
        "source": "semantic_scholar",
    }


async def fetch_recommendations(
    paper_ids: List[str],
    limit: int = 10,
    negative_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch recommended papers based on positive (and optionally negative) paper IDs.

    Uses POST /recommendations/v1/papers/ endpoint.

    Args:
        paper_ids: list of paper IDs the user likes (arXiv IDs or S2 paper IDs)
        limit: max results (default 10, max 50)
        negative_ids: optional list of paper IDs the user dislikes

    Returns:
        List of recommended paper dicts.
    """
    normalized = [_normalize_arxiv_id(pid) for pid in paper_ids]
    body: Dict[str, Any] = {
        "positivePaperIds": normalized,
    }
    if negative_ids:
        body["negativePaperIds"] = [_normalize_arxiv_id(nid) for nid in negative_ids]

    params = {
        "limit": min(limit, 50),
        "fields": S2_FIELDS,
    }

    url = f"{SEMANTIC_SCHOLAR_BASE}/recommendations/v1/papers/"
    try:
        async with httpx.AsyncClient(timeout=S2_TIMEOUT) as client:
            response = await client.post(url, json=body, params=params)
            if response.status_code in (404, 429):
                logger.warning(
                    f"Semantic Scholar recommendations: HTTP {response.status_code}"
                )
                return []
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Semantic Scholar recommendations error: {e}")
        return []
    except Exception as e:
        logger.exception(f"Semantic Scholar recommendations failed: {e}")
        return []

    papers = data.get("recommendedPapers", [])
    return [_format_paper(p) for p in papers]


async def fetch_citations_and_references(
    paper_id: str,
    limit: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch citations and references for a paper.

    Args:
        paper_id: arXiv ID or Semantic Scholar paper ID
        limit: max results per direction (default 10)

    Returns:
        Dict with "citations" and "references" lists.
    """
    normalized = _normalize_arxiv_id(paper_id)
    # S2 API requires nested field specification for references/citations
    ref_fields = ",".join(f"references.{f}" for f in S2_FIELDS.split(","))
    cite_fields = ",".join(f"citations.{f}" for f in S2_FIELDS.split(","))
    fields = f"{ref_fields},{cite_fields}"
    data = await _s2_get(f"/graph/v1/paper/{normalized}", {"fields": fields})

    if not data:
        return {"citations": [], "references": []}

    refs = data.get("references", []) or []
    cites = data.get("citations", []) or []

    return {
        "references": [_format_paper(r) for r in refs[:limit] if r.get("paperId")],
        "citations": [_format_paper(c) for c in cites[:limit] if c.get("paperId")],
    }


async def handle_related_papers(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle the related_papers MCP tool call.

    Supports three modes:
    1. recommendations: find papers similar to given paper(s)
    2. citations: find papers that cite this paper
    3. references: find papers this paper references
    """
    paper_id = arguments.get("paper_id", "").strip()
    paper_ids_raw = arguments.get("paper_ids", [])
    mode = arguments.get("mode", "recommendations").strip()
    limit = min(max(1, int(arguments.get("limit", 10))), 50)

    if not paper_id and not paper_ids_raw:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {"status": "error", "message": "paper_id or paper_ids is required"}
                ),
            )
        ]

    if mode == "recommendations":
        ids = paper_ids_raw if paper_ids_raw else [paper_id]
        negative_ids = arguments.get("negative_paper_ids", [])
        papers = await fetch_recommendations(
            ids, limit=limit, negative_ids=negative_ids
        )

        result = {
            "status": "success",
            "mode": "recommendations",
            "seed_papers": ids,
            "total_results": len(papers),
            "papers": papers,
        }
    elif mode in ("citations", "references"):
        if not paper_id:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "message": "paper_id is required for citations/references mode",
                        }
                    ),
                )
            ]
        data = await fetch_citations_and_references(paper_id, limit=limit)
        papers = data.get(mode, [])

        result = {
            "status": "success",
            "mode": mode,
            "paper_id": paper_id,
            "total_results": len(papers),
            "papers": papers,
        }
    else:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "error",
                        "message": f"Unknown mode: '{mode}'. Use 'recommendations', 'citations', or 'references'.",
                    }
                ),
            )
        ]

    return [types.TextContent(type="text", text=json.dumps(result))]


# ---------------------------------------------------------------------------
# MCP tool definition
# ---------------------------------------------------------------------------

related_papers_tool = types.Tool(
    name="related_papers",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description=(
        "Discover related papers via Semantic Scholar. Supports three modes: "
        "'recommendations' (find similar papers to one or more seed papers), "
        "'citations' (find papers that cite this paper), and "
        "'references' (find papers this paper references). "
        "Uses the free Semantic Scholar API — no API key required."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "paper_id": {
                "type": "string",
                "description": "Paper ID (arXiv ID like '2401.12345' or Semantic Scholar ID). Required for citations/references mode.",
            },
            "paper_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Multiple paper IDs for recommendations mode (e.g., papers you found useful). Overrides paper_id for recommendations.",
            },
            "negative_paper_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paper IDs you're NOT interested in (for recommendations mode). Helps refine suggestions.",
            },
            "mode": {
                "type": "string",
                "description": "Search mode: 'recommendations' (similar papers), 'citations' (who cites this), 'references' (what this cites). Default: recommendations.",
                "enum": ["recommendations", "citations", "references"],
                "default": "recommendations",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 10, max: 50)",
                "default": 10,
            },
        },
        "required": [],
    },
)
