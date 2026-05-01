"""HuggingFace integration — paper metadata mirror and daily papers."""

import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
import mcp.types as types
from mcp.types import ToolAnnotations

logger = logging.getLogger("top-paper-mcp-server")

HUGGINGFACE_API_BASE = "https://huggingface.co/api"
HF_REQUEST_TIMEOUT = 15.0

# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------


async def fetch_hf_paper_metadata(arxiv_id: str) -> Optional[Dict[str, Any]]:
    """Fetch paper metadata from HuggingFace by arXiv ID.

    Returns a dict with title, summary, authors, upvotes, ai_summary,
    ai_keywords, githubRepo, githubStars — or None on any failure.
    """
    url = f"{HUGGINGFACE_API_BASE}/papers/{arxiv_id}"
    try:
        async with httpx.AsyncClient(timeout=HF_REQUEST_TIMEOUT) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(f"HuggingFace paper metadata error for {arxiv_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"HuggingFace paper metadata failed for {arxiv_id}: {e}")
        return None


async def fetch_daily_papers(
    target_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch HuggingFace daily papers.

    Args:
        target_date: YYYY-MM-DD string. Defaults to today if None/empty.

    Returns:
        List of paper dicts, each containing id, title, summary, authors,
        publishedAt, upvotes, etc. Empty list on failure.
    """
    params: Dict[str, str] = {}
    if target_date:
        params["date"] = target_date

    url = f"{HUGGINGFACE_API_BASE}/daily_papers"
    try:
        async with httpx.AsyncClient(timeout=HF_REQUEST_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            # API returns a list of { paper: {...}, publishedAt: ... } objects
            if isinstance(data, list):
                return data
            return []
    except httpx.HTTPError as e:
        logger.error(f"HuggingFace daily papers error: {e}")
        return []
    except Exception as e:
        logger.exception(f"HuggingFace daily papers failed: {e}")
        return []


# ---------------------------------------------------------------------------
# MCP tool handler
# ---------------------------------------------------------------------------


async def handle_hf_daily_papers(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle the hf_daily_papers MCP tool call."""
    target_date = arguments.get("date", "").strip()
    max_results = arguments.get("max_results", 20)
    max_results = min(max(1, int(max_results)), 100)

    # Validate date format if provided
    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "message": f"Invalid date format: '{target_date}'. Use YYYY-MM-DD.",
                        }
                    ),
                )
            ]

    raw = await fetch_daily_papers(target_date or None)
    if not raw:
        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "success",
                        "date": target_date or date.today().isoformat(),
                        "total_results": 0,
                        "papers": [],
                    }
                ),
            )
        ]

    papers: List[Dict[str, Any]] = []
    for entry in raw[:max_results]:
        paper = entry.get("paper", entry)
        papers.append(
            {
                "id": paper.get("id", ""),
                "title": paper.get("title", ""),
                "summary": paper.get("summary", ""),
                "authors": [
                    a.get("name", "") if isinstance(a, dict) else str(a)
                    for a in paper.get("authors", [])
                ],
                "published_at": entry.get("publishedAt", paper.get("publishedAt", "")),
                "upvotes": paper.get("upvotes", 0),
                "ai_summary": paper.get("ai_summary", ""),
                "ai_keywords": paper.get("ai_keywords", []),
                "github_repo": paper.get("githubRepo", ""),
                "github_stars": paper.get("githubStars", 0),
                "url": f"https://huggingface.co/papers/{paper.get('id', '')}",
            }
        )

    result = {
        "status": "success",
        "date": target_date or date.today().isoformat(),
        "total_results": len(papers),
        "papers": papers,
    }
    return [types.TextContent(type="text", text=json.dumps(result))]


# ---------------------------------------------------------------------------
# MCP tool definition
# ---------------------------------------------------------------------------

hf_daily_papers_tool = types.Tool(
    name="hf_daily_papers",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description=(
        "Fetch trending daily papers from HuggingFace. Returns papers curated "
        "by the HF community with metadata including upvotes, AI summaries, "
        "keywords, and associated GitHub repos. Useful for discovering trending "
        "research and as a fallback when arXiv is congested."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format (e.g., 2024-01-15). Defaults to today if not provided.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of papers to return (default: 20, max: 100)",
                "default": 20,
            },
        },
        "required": [],
    },
)
