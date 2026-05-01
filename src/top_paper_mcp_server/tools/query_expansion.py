"""Query expansion and result fusion for smart search.

Provides rule-based query expansion as a fallback, and Reciprocal Rank Fusion (RRF)
for merging results from multiple query variants.
"""

import logging
import re
from collections import Counter
from typing import Any, Dict, List

logger = logging.getLogger("top-paper-mcp-server")

# Common academic suffixes to generate query variants
_ACADEMIC_SUFFIXES = [
    "method",
    "approach",
    "framework",
    "model",
    "network",
    "architecture",
    "algorithm",
    "technique",
    "system",
    "mechanism",
]

# Minimal stopwords for keyword extraction
_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "and or but not no nor so yet both either neither each every all "
    "any few more most other some such than too very just about also "
    "that this these those it its we our they their he she his her "
    "which what when where how who whom whose if then else while "
    "up out off over under again further once here there".split()
)


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip punctuation, collapse whitespace."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _fuzzy_title_match(t1: str, t2: str) -> bool:
    """Check if two titles refer to the same paper.

    Uses Jaccard word overlap. Also handles the case where one title
    is a prefix of the other (handles subtitle differences).
    """
    words1 = set(_normalize_title(t1).split())
    words2 = set(_normalize_title(t2).split())
    if not words1 or not words2:
        return False
    intersection = words1 & words2
    union = words1 | words2
    jaccard = len(intersection) / len(union)
    # High overlap or one is a prefix subset of the other
    if jaccard > 0.7:
        return True
    smaller = words1 if len(words1) < len(words2) else words2
    larger = words2 if len(words1) < len(words2) else words1
    if smaller and smaller.issubset(larger):
        return True
    return False


def _generate_candidates(query: str) -> List[str]:
    """Generate expansion candidates from a query string.

    Returns: list of query strings (original always first, typically 3-5 total).
    """
    query = query.strip()
    if not query:
        return []

    candidates = [query]
    tokens = query.lower().split()

    # Single-word query: add academic suffix variants
    if len(tokens) == 1:
        for suffix in _ACADEMIC_SUFFIXES[:3]:
            candidates.append(f"{query} {suffix}")
        return candidates

    # Multi-word query: add bigrams and token-level variants
    # Bigrams
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i+1]}"
        if bigram != query.lower():
            candidates.append(bigram)

    # Each core token + first token
    for token in tokens[1:]:
        if token not in _STOPWORDS and len(token) > 2:
            candidates.append(f"{tokens[0]} {token}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        key = c.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    return unique[:5]


def _extract_keywords_from_results(
    papers: List[Dict[str, Any]], top_k: int = 10
) -> List[str]:
    """Extract top keywords from paper abstracts using TF.

    Returns list of keyword strings, useful for feeding back into future expansions.
    """
    word_counts: Counter = Counter()
    for paper in papers:
        abstract = paper.get("abstract", "")
        # Remove the [EXTERNAL CONTENT] prefix if present
        abstract = re.sub(r"^\[EXTERNAL CONTENT\]\s*", "", abstract)
        words = re.findall(r"\b[a-z]{3,}\b", abstract.lower())
        for w in words:
            if w not in _STOPWORDS:
                word_counts[w] += 1

    return [word for word, _ in word_counts.most_common(top_k)]


def _rrf_fuse(
    result_lists: List[List[Dict[str, Any]]], k: int = 20
) -> List[Dict[str, Any]]:
    """Merge multiple result lists using Reciprocal Rank Fusion.

    For each paper across all lists: score = sum(1 / (k + rank_in_list)).
    Papers are keyed by normalized title for dedup.

    Args:
        result_lists: each inner list is ranked (index 0 = rank 1).
        k: RRF constant (default 20, per literature).

    Returns:
        List of paper dicts sorted by RRF score descending, with 'rrf_score' added.
    """
    paper_scores: Dict[str, float] = {}
    paper_objects: Dict[str, Dict[str, Any]] = {}

    for result_list in result_lists:
        for rank, paper in enumerate(result_list):
            title = paper.get("title", "")
            norm_title = _normalize_title(title)

            # Find existing key if fuzzy match
            match_key = None
            for existing_key in paper_scores:
                if _fuzzy_title_match(existing_key, title):
                    match_key = existing_key
                    break

            key = match_key if match_key else norm_title

            if key not in paper_scores:
                paper_scores[key] = 0.0
                paper_objects[key] = paper

            paper_scores[key] += 1.0 / (k + rank + 1)  # rank is 0-indexed, formula uses 1-indexed

    # Sort by RRF score descending
    sorted_keys = sorted(paper_scores.keys(), key=lambda x: paper_scores[x], reverse=True)

    results = []
    for key in sorted_keys:
        paper = paper_objects[key].copy()
        paper["rrf_score"] = round(paper_scores[key], 6)
        results.append(paper)

    return results
