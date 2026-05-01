"""Conference paper search tools — dual-path: arXiv + OpenReview."""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from enum import IntEnum
import mcp.types as types
from mcp.types import ToolAnnotations

from .conferences import OpenReviewSource, PaperMetadata
from .conferences.openreview import VENUE_IDS
from .search import _raw_arxiv_search

MAX_CONCURRENT_SEARCHES = 10
SEARCH_TIMEOUT = 30.0
MAX_RETRIES = 2

logger = logging.getLogger("top-paper-mcp-server")

openreview_source = OpenReviewSource()

# Conference → arXiv category mapping for better arXiv search results
CONFERENCE_ARXIV_CATEGORIES = {
    "CVPR": ["cs.CV"],
    "ICCV": ["cs.CV"],
    "WACV": ["cs.CV"],
    "ECCV": ["cs.CV"],
    "NEURIPS": ["cs.LG", "cs.AI", "cs.CL", "stat.ML"],
    "ICML": ["cs.LG", "stat.ML"],
    "ICLR": ["cs.LG", "cs.AI", "cs.CL"],
    "COLM": ["cs.CL", "cs.LG"],
    "CORL": ["cs.RO", "cs.LG", "cs.AI"],
    "MLSYS": ["cs.LG", "cs.DC"],
    "MICCAI": ["cs.CV", "eess.IV"],
    "IWSLT": ["cs.CL"],
    "INTERSPEECH": ["eess.AS", "cs.CL"],
    "ACL": ["cs.CL"],
    "EMNLP": ["cs.CL"],
    "NAACL": ["cs.CL"],
    "AAAI": ["cs.AI"],
    "IJCAI": ["cs.AI"],
    "COLT": ["stat.ML", "cs.LG"],
    "UAI": ["stat.ML", "cs.LG"],
}


class ConferencePriority(IntEnum):
    """Conference priority levels for unified search."""

    CVPR = 100
    ICCV = 95
    NeurIPS = 90
    ICLR = 85
    ICML = 80
    ECCV = 75
    WACV = 70
    ACL = 65
    EMNLP = 60
    NAACL = 55
    COLM = 50
    CoRL = 45
    AAAI = 40
    IJCAI = 35
    MLSYS = 30
    MICCAI = 25
    IWSLT = 20
    INTERSPEECH = 15
    COLT = 10
    UAI = 5


CONFERENCE_PRIORITY = {
    conf.upper(): priority.value
    for conf, priority in ConferencePriority.__members__.items()
}

CONFERENCE_CATEGORIES = {
    "computer_vision": ["CVPR", "ICCV", "WACV", "ECCV"],
    "machine_learning": ["NEURIPS", "ICML", "ICLR", "COLM", "CORL", "MLSYS"],
    "nlp": ["ACL", "EMNLP", "NAACL"],
    "speech": ["INTERSPEECH", "IWSLT"],
    "medical": ["MICCAI"],
    "ai": ["AAAI", "IJCAI"],
    "theory": ["COLT", "UAI"],
}

CATEGORY_PRIORITY = {
    "computer_vision": 1,
    "machine_learning": 2,
    "nlp": 3,
    "ai": 4,
    "speech": 5,
    "medical": 6,
    "theory": 7,
}

AVAILABLE_CONFERENCES = {
    "OpenReview": [
        "ICLR",
        "NeurIPS",
        "ICML",
        "CVPR",
        "ICCV",
        "WACV",
        "ECCV",
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
    ],
}

# All conferences supported by OpenReview (derived from venue IDs for completeness)
OPENREVIEW_CONFERENCES = {conf.upper() for conf, _year in VENUE_IDS.keys()}


def _build_tool_description() -> str:
    """Build dynamic tool description with available conferences."""
    conf_list = []
    for source, confs in AVAILABLE_CONFERENCES.items():
        conf_list.append(f"- **{source}**: {', '.join(confs)}")
    return f"""Search for papers in top AI/ML/CV conferences.

Uses dual-path search: queries both arXiv and OpenReview in parallel, then merges
results. arXiv provides full paper content (abstracts, PDFs), while OpenReview
provides conference venue metadata.

AVAILABLE CONFERENCES:
{chr(10).join(conf_list)}

YEAR RANGE: 2000-present for most conferences

EXAMPLES:
- Search CVPR 2024 papers about "object detection"
- Search ICLR 2025 papers about "transformer"
- Search NeurIPS papers about "reinforcement learning"

Note: Results combine arXiv paper content with OpenReview conference metadata."""


conference_search_tool = types.Tool(
    name="conference_search",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description=_build_tool_description(),
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for paper titles and abstracts",
            },
            "conference": {
                "type": "string",
                "description": "Conference name (e.g., CVPR, ICCV, WACV, ECCV, ICLR, NeurIPS, ICML, AAAI, IJCAI, ACL, EMNLP, NAACL, COLM, CoRL, MLSYS, MICCAI, IWSLT, INTERSPEECH)",
                "enum": [
                    "CVPR",
                    "ICCV",
                    "WACV",
                    "ECCV",
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
                ],
            },
            "year": {
                "type": "integer",
                "description": "Conference year (e.g., 2024, 2025)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 50)",
                "default": 10,
            },
            "search_all": {
                "type": "boolean",
                "description": "Search across ALL conferences concurrently (default: false)",
                "default": False,
            },
            "conferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "When search_all is true: specify conferences to search (optional, searches all if empty)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string", "enum": list(CONFERENCE_CATEGORIES.keys())},
                "description": "When search_all is true: filter by conference categories",
            },
        },
        "required": ["query", "conference", "year"],
    },
)


async def _search_arxiv_for_conference(
    query: str,
    conference: str,
    year: int,
    max_results: int,
) -> List[Dict[str, Any]]:
    """Search arXiv with conference-specific category filtering and date range."""
    categories = CONFERENCE_ARXIV_CATEGORIES.get(conference.upper())
    date_from = f"{year}-01-01"
    date_to = f"{year}-12-31"

    try:
        results = await _raw_arxiv_search(
            query=query,
            max_results=max_results,
            sort_by="relevance",
            date_from=date_from,
            date_to=date_to,
            categories=categories,
        )
        return results
    except Exception as e:
        logger.warning(f"arXiv search failed for {conference} {year}: {e}")
        return []


async def _search_openreview_for_conference(
    query: str,
    conference: str,
    year: int,
    max_results: int,
) -> List[PaperMetadata]:
    """Search OpenReview for conference papers."""
    if conference.upper() not in OPENREVIEW_CONFERENCES:
        return []

    try:
        papers = await openreview_source.search(query, conference, year, max_results)
        return papers
    except Exception as e:
        logger.warning(f"OpenReview search failed for {conference} {year}: {e}")
        return []


def _merge_results(
    arxiv_results: List[Dict[str, Any]],
    openreview_papers: List[PaperMetadata],
    conference: str,
    year: int,
) -> List[Dict[str, Any]]:
    """Merge arXiv and OpenReview results.

    Strategy:
    - OpenReview papers are primary (they have conference metadata)
    - If an OpenReview paper has an arXiv ID, enrich with arXiv data
    - arXiv-only papers (not on OpenReview) are added as supplementary
    """
    # Index OpenReview papers by title (normalized) for dedup
    openreview_by_title: Dict[str, Dict[str, Any]] = {}
    for paper in openreview_papers:
        key = paper.title.lower().strip()
        entry = paper.to_dict()
        entry["source"] = "openreview"
        entry["conference"] = conference.upper()
        entry["year"] = year
        openreview_by_title[key] = entry

    # Index arXiv results by title (normalized) for dedup
    arxiv_by_title: Dict[str, Dict[str, Any]] = {}
    for result in arxiv_results:
        key = result.get("title", "").lower().strip()
        result["source"] = "arxiv"
        result["conference"] = conference.upper()
        result["year"] = year
        arxiv_by_title[key] = result

    merged: List[Dict[str, Any]] = []
    seen_titles: set = set()

    # 1. OpenReview papers (primary — have conference metadata)
    for title_key, paper in openreview_by_title.items():
        # Check if arXiv has a matching paper to enrich
        arxiv_match = arxiv_by_title.get(title_key)
        if arxiv_match:
            # Enrich OpenReview paper with arXiv data
            paper["arxiv_id"] = arxiv_match.get("id")
            paper["arxiv_categories"] = arxiv_match.get("categories", [])
            paper["pdf_url"] = arxiv_match.get("url") or paper.get("pdf_url")
        merged.append(paper)
        seen_titles.add(title_key)

    # 2. arXiv-only papers (not found on OpenReview)
    for title_key, result in arxiv_by_title.items():
        if title_key not in seen_titles:
            merged.append(result)
            seen_titles.add(title_key)

    return merged


async def _search_single_conference_dual(
    query: str,
    conference: str,
    year: int,
    max_results: int,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Search a single conference using dual-path (arXiv + OpenReview)."""

    async def _search():
        # Run both searches concurrently
        arxiv_task = _search_arxiv_for_conference(query, conference, year, max_results)
        openreview_task = _search_openreview_for_conference(
            query, conference, year, max_results
        )

        arxiv_results, openreview_papers = await asyncio.gather(
            arxiv_task, openreview_task, return_exceptions=True
        )

        if isinstance(arxiv_results, Exception):
            logger.warning(f"arXiv search exception for {conference}: {arxiv_results}")
            arxiv_results = []
        if isinstance(openreview_papers, Exception):
            logger.warning(
                f"OpenReview search exception for {conference}: {openreview_papers}"
            )
            openreview_papers = []

        return _merge_results(arxiv_results, openreview_papers, conference, year)

    if semaphore:
        async with semaphore:
            papers = await asyncio.wait_for(_search(), timeout=SEARCH_TIMEOUT)
    else:
        papers = await asyncio.wait_for(_search(), timeout=SEARCH_TIMEOUT)

    return conference, papers


async def _search_with_retry(
    query: str,
    conference: str,
    year: int,
    max_results: int,
    semaphore: asyncio.Semaphore,
) -> tuple[str, List[Dict[str, Any]]]:
    """Search with timeout and retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            return await _search_single_conference_dual(
                query, conference, year, max_results, semaphore
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout for {conference} (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt == MAX_RETRIES - 1:
                return conference, []
        except Exception as e:
            logger.warning(f"Search error for {conference}: {e}")
            if attempt == MAX_RETRIES - 1:
                return conference, []
            await asyncio.sleep(0.5 * (attempt + 1))

    return conference, []


async def handle_conference_search(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle conference paper search with dual-path (arXiv + OpenReview)."""
    try:
        query = arguments.get("query", "")
        conference = arguments.get("conference", "").upper()
        year = arguments.get("year", 2025)
        max_results = min(int(arguments.get("max_results", 10)), 50)
        search_all = arguments.get("search_all", False)

        if search_all:
            conferences = arguments.get("conferences", [])
            categories = arguments.get("categories", [])

            target_conferences = []

            if conferences:
                target_conferences = [c.upper() for c in conferences]
            elif categories:
                for category in categories:
                    if category in CONFERENCE_CATEGORIES:
                        target_conferences.extend(CONFERENCE_CATEGORIES[category])
            else:
                target_conferences = list(CONFERENCE_PRIORITY.keys())

            # Filter to supported conferences
            target_conferences = [
                c
                for c in target_conferences
                if c in OPENREVIEW_CONFERENCES or c in CONFERENCE_ARXIV_CATEGORIES
            ]

            if not target_conferences:
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps({"error": "No valid conferences to search"}),
                    )
                ]

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
            search_tasks = [
                _search_with_retry(query, conf, year, max_results, semaphore)
                for conf in target_conferences
            ]

            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            all_papers = []
            conference_results = {}

            for result in results:
                if isinstance(result, Exception):
                    continue
                conf_name, papers = result
                if papers:
                    priority = _get_conference_priority(conf_name)
                    category = _get_category(conf_name) or "other"
                    for paper in papers:
                        paper["_search_priority"] = priority
                        paper["_search_category"] = category
                        all_papers.append(paper)
                    conference_results[conf_name] = len(papers)

            all_papers.sort(
                key=lambda x: (-x.get("_search_priority", 0), x.get("title", ""))
            )

            final_papers = all_papers[: max_results * 3]
            for paper in final_papers:
                paper.pop("_search_priority", None)
                paper.pop("_search_category", None)

            response = {
                "query": query,
                "year": year,
                "total_results": len(final_papers),
                "conferences_searched": target_conferences,
                "conference_results": conference_results,
                "papers": final_papers,
            }

            return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

        if not conference or not year:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": "conference and year are required"}),
                )
            ]

        _, papers = await _search_single_conference_dual(
            query, conference, year, max_results
        )

        if not papers:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "total_results": 0,
                            "message": f"No papers found for {conference} {year} with query '{query}'",
                            "papers": [],
                        },
                        indent=2,
                    ),
                )
            ]

        results = {
            "total_results": len(papers),
            "conference": conference,
            "year": year,
            "papers": papers,
        }

        return [types.TextContent(type="text", text=json.dumps(results, indent=2))]

    except ValueError as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
    except Exception as e:
        logger.exception(f"Conference search error: {e}")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]


def _get_conference_priority(conference: str) -> int:
    """Get priority score for a conference."""
    return CONFERENCE_PRIORITY.get(conference.upper(), 0)


def _get_category(conference: str) -> Optional[str]:
    """Get category for a conference."""
    for category, conferences in CONFERENCE_CATEGORIES.items():
        if conference.upper() in conferences:
            return category
    return None


unified_search_tool = types.Tool(
    name="unified_search",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    description="""Unified search across multiple conferences with dual-path (arXiv + OpenReview).

FEATURES:
- Concurrent dual-path search: arXiv + OpenReview in parallel per conference
- Results merged by title matching — OpenReview provides conference metadata, arXiv provides content
- Priority-based ordering (CVPR > NeurIPS > ICLR > ICML > ...)
- Category-based filtering (computer_vision, machine_learning, nlp, ai, speech, medical, theory)

INPUT:
- query: Search keywords
- year: Conference year to search
- conferences: List of specific conferences (optional, searches all if empty)
- categories: Filter by categories (optional)
- max_results_per_conference: Results per conference (default: 5)
- total_results: Total results to return (default: 20)

EXAMPLES:
- Search all conferences for "transformer" in 2024
- Search computer_vision category for "object detection"
- Search specific conferences: ["CVPR", "NeurIPS", "ICLR"]""",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for paper titles and abstracts",
            },
            "year": {
                "type": "integer",
                "description": "Conference year to search (e.g., 2024, 2025)",
            },
            "conferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific conferences to search (empty = search all)",
            },
            "categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(CONFERENCE_CATEGORIES.keys()),
                },
                "description": "Filter by conference categories",
            },
            "max_results_per_conference": {
                "type": "integer",
                "description": "Maximum results per conference (default: 5)",
                "default": 5,
            },
            "total_results": {
                "type": "integer",
                "description": "Total results to return (default: 20, max: 100)",
                "default": 20,
            },
        },
        "required": ["query", "year"],
    },
)


async def handle_unified_search(
    arguments: Dict[str, Any],
) -> List[types.TextContent]:
    """Handle unified multi-conference search with dual-path concurrent execution."""
    try:
        query = arguments.get("query", "")
        year = arguments.get("year", 2025)
        specified_conferences = arguments.get("conferences", [])
        categories = arguments.get("categories", [])
        max_per_conference = min(
            int(arguments.get("max_results_per_conference", 5)), 20
        )
        total_results = min(int(arguments.get("total_results", 20)), 100)

        if not query:
            return [
                types.TextContent(
                    type="text", text=json.dumps({"error": "query is required"})
                )
            ]

        target_conferences = []

        if specified_conferences:
            target_conferences = [c.upper() for c in specified_conferences]
        elif categories:
            for category in categories:
                if category in CONFERENCE_CATEGORIES:
                    target_conferences.extend(CONFERENCE_CATEGORIES[category])
        else:
            target_conferences = list(CONFERENCE_PRIORITY.keys())

        # Filter to supported conferences
        target_conferences = [
            c
            for c in target_conferences
            if c in OPENREVIEW_CONFERENCES or c in CONFERENCE_ARXIV_CATEGORIES
        ]

        if not target_conferences:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": "No valid conferences to search"}),
                )
            ]

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)
        search_tasks = [
            _search_with_retry(query, conf, year, max_per_conference, semaphore)
            for conf in target_conferences
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_papers = []
        conference_results = {}

        for result in results:
            if isinstance(result, Exception):
                continue
            conference, papers = result
            if papers:
                priority = _get_conference_priority(conference)
                category = _get_category(conference) or "other"
                for paper in papers:
                    paper["_search_priority"] = priority
                    paper["_search_category"] = category
                    all_papers.append(paper)
                conference_results[conference] = len(papers)

        all_papers.sort(
            key=lambda x: (-x.get("_search_priority", 0), x.get("title", ""))
        )

        final_papers = all_papers[:total_results]
        for paper in final_papers:
            paper.pop("_search_priority", None)
            paper.pop("_search_category", None)

        response = {
            "query": query,
            "year": year,
            "total_results": len(final_papers),
            "conferences_searched": target_conferences,
            "conference_results": conference_results,
            "papers": final_papers,
        }

        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]

    except Exception as e:
        logger.exception(f"Unified search error: {e}")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]
