"""Scoring, deduplication, and seen-item filtering."""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from .fetcher import FeedItem

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80
TOP_N = 10
SEEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "seen.json")


def _jaccard_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two strings."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _char_similarity(a: str, b: str) -> float:
    """Character n-gram similarity — works better for CJK titles."""
    def ngrams(s: str, n: int = 2):
        return set(s[i:i+n] for i in range(len(s) - n + 1))

    na, nb = ngrams(a), ngrams(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)


def similarity(a: str, b: str) -> float:
    return max(_jaccard_similarity(a, b), _char_similarity(a, b))


def _compute_score(item: FeedItem) -> float:
    # Higher rank = lower score; weight by source weight
    rank_score = 1.0 / (item.rank + 1)
    return item.source_weight * rank_score


def deduplicate(items: List[FeedItem]) -> List[FeedItem]:
    """Remove cross-source duplicates by title similarity."""
    kept: List[FeedItem] = []
    for item in items:
        is_dup = False
        for existing in kept:
            if similarity(item.title, existing.title) >= SIMILARITY_THRESHOLD:
                is_dup = True
                logger.debug("Duplicate detected: '%s' ≈ '%s'", item.title, existing.title)
                break
        if not is_dup:
            kept.append(item)
    logger.info("After deduplication: %d → %d items", len(items), len(kept))
    return kept


def load_seen(path: str = SEEN_FILE) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load seen.json: %s", e)
        return []


def save_seen(seen: List[dict], path: str = SEEN_FILE) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    pruned = [s for s in seen if s.get("seen_at", "") > cutoff]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pruned, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Could not save seen.json: %s", e)


def filter_seen(items: List[FeedItem], seen: List[dict]) -> List[FeedItem]:
    """Remove items whose URL appeared in the last 24 hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_urls = {s["url"] for s in seen if s.get("seen_at", "") > cutoff}
    filtered = [i for i in items if i.link not in recent_urls]
    logger.info("After seen-filter: %d → %d items", len(items), len(filtered))
    return filtered


def select_top(items: List[FeedItem], n: int = TOP_N) -> List[FeedItem]:
    scored: List[Tuple[float, FeedItem]] = [(_compute_score(i), i) for i in items]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:n]]
