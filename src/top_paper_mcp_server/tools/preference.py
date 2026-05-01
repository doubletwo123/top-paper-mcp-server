"""Lightweight preference memory for personalized search.

Uses a Contextual Bandit approach: tracks which expansion terms lead to
useful results (user downloads/reads), and reweights future expansions.

Storage: single JSON file at ~/.top-paper-mcp-server/preferences.json
No large models, no GPU, no training data — just weighted averages.
"""

import json
import logging
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Settings

logger = logging.getLogger("top-paper-mcp-server")

_PREFERENCES_FILENAME = "preferences.json"
_DEFAULT_WEIGHT = 0.5
_INITIAL_LR = 0.3
_MIN_LR = 0.05
_LR_DECAY_RATE = 0.01


def _preferences_path() -> Path:
    """Return the path to the preferences JSON file."""
    settings = Settings()
    return Path(settings.STORAGE_PATH).parent / _PREFERENCES_FILENAME


class PreferenceStore:
    """Lightweight preference memory backed by a JSON file.

    Tracks:
    - term_weights: which query expansion terms are effective
    - category_weights: which arXiv categories the user prefers
    - interaction_count: total feedback signals received
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = path or _preferences_path()
        self._data: Dict[str, Any] = {
            "version": 1,
            "term_weights": {},
            "category_weights": {},
            "interaction_count": 0,
            "last_updated": None,
        }

    def load(self) -> None:
        """Load preferences from disk. No-op if file doesn't exist."""
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") == 1:
                self._data = data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load preferences: {e}")

    def save(self) -> None:
        """Persist preferences to disk."""
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Failed to save preferences: {e}")

    @property
    def interaction_count(self) -> int:
        return self._data.get("interaction_count", 0)

    @property
    def term_weights(self) -> Dict[str, float]:
        return dict(self._data.get("term_weights", {}))

    @property
    def category_weights(self) -> Dict[str, float]:
        return dict(self._data.get("category_weights", {}))

    def _learning_rate(self) -> float:
        """Decaying learning rate: starts at 0.3, floors at 0.05."""
        n = self.interaction_count
        return max(_MIN_LR, _INITIAL_LR * math.exp(-_LR_DECAY_RATE * n))

    def record_reward(
        self,
        terms: List[str],
        reward: float,
        categories: Optional[List[str]] = None,
    ) -> None:
        """Update weights based on a reward signal.

        For each term: w_new = w_old + α * (reward - w_old)
        This is an exponential moving average toward the reward.

        Args:
            terms: expansion terms that led to this result
            reward: positive (download/read) or negative (ignored)
            categories: arXiv categories of the paper (optional)
        """
        if not terms:
            return

        alpha = self._learning_rate()
        term_weights = self._data.setdefault("term_weights", {})

        for term in terms:
            term = term.lower().strip()
            old_w = term_weights.get(term, _DEFAULT_WEIGHT)
            term_weights[term] = old_w + alpha * (reward - old_w)

        if categories:
            cat_weights = self._data.setdefault("category_weights", {})
            for cat in categories:
                old_w = cat_weights.get(cat, _DEFAULT_WEIGHT)
                cat_weights[cat] = old_w + alpha * (reward - old_w)

        self._data["interaction_count"] = self.interaction_count + 1
        self.save()

    def select_terms(
        self, candidates: List[str], original_query: str, top_k: int = 3
    ) -> List[str]:
        """Select expansion terms using preference-weighted sampling.

        Uses softmax over term weights to probabilistically select top_k terms.
        Original query is always included. 10% chance of random exploration.

        Args:
            candidates: list of candidate expansion terms/queries
            original_query: the user's original query (always included)
            top_k: how many terms to select (default 3)

        Returns:
            List of selected terms including original_query.
        """
        if not candidates:
            return [original_query]

        term_weights = self._data.get("term_weights", {})

        # Cold start: if fewer than 5 interactions, use all candidates
        if self.interaction_count < 5:
            return candidates[:top_k]

        # ε-greedy: 10% chance of random selection
        if random.random() < 0.1:
            selected = [original_query]
            others = [c for c in candidates if c.lower() != original_query.lower()]
            if others:
                selected.extend(random.sample(others, min(top_k - 1, len(others))))
            return selected

        # Softmax-weighted selection
        scored = []
        for cand in candidates:
            w = term_weights.get(cand.lower().strip(), _DEFAULT_WEIGHT)
            scored.append((cand, w))

        # Softmax
        max_w = max(w for _, w in scored)
        exp_weights = [(c, math.exp(w - max_w)) for c, w in scored]
        total = sum(ew for _, ew in exp_weights)
        probs = [(c, ew / total) for c, ew in exp_weights]

        # Select top_k by probability (without replacement)
        selected = []
        remaining = list(probs)

        # Always include original query
        selected.append(original_query)
        remaining = [
            (c, p) for c, p in remaining if c.lower() != original_query.lower()
        ]

        while len(selected) < top_k and remaining:
            # Weighted random choice
            r = random.random()
            cumulative = 0.0
            for i, (c, p) in enumerate(remaining):
                cumulative += p
                if r <= cumulative:
                    selected.append(c)
                    remaining.pop(i)
                    # Renormalize
                    total_p = sum(p for _, p in remaining)
                    if total_p > 0:
                        remaining = [(c, p / total_p) for c, p in remaining]
                    break

        return selected


def compute_reward(paper: Dict[str, Any], user_action: str) -> float:
    """Compute reward value from user action.

    Args:
        paper: the paper dict (unused currently, reserved for future weighting)
        user_action: "download" | "read" | "search_shown"

    Returns:
        Reward float: download=1.0, read=2.0, search_shown=-0.1
    """
    rewards = {
        "download": 1.0,
        "read": 2.0,
        "search_shown": -0.1,
    }
    return rewards.get(user_action, 0.0)
