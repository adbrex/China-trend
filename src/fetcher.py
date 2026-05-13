"""RSS feed fetcher with retry and timeout."""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

RSSHUB_BASE_URL = "https://rsshub.app"

SOURCES = [
    {"name": "微博热搜", "path": "/weibo/search/hot", "weight": 1.0},
    {"name": "知乎热榜", "path": "/zhihu/hotlist", "weight": 1.2},
    {"name": "36氪", "path": "/36kr/news/latest", "weight": 0.8},
]

MAX_ITEMS_PER_SOURCE = 30
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


@dataclass
class FeedItem:
    title: str
    link: str
    summary: str
    source_name: str
    source_weight: float
    rank: int  # 0-based position in source feed


def _fetch_with_retry(url: str) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "china-trends-bot/1.0"})
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            wait = 2 ** attempt
            logger.warning("Fetch attempt %d/%d failed for %s: %s. Retrying in %ds", attempt + 1, MAX_RETRIES, url, e, wait)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
    return None


def fetch_all_sources(rsshub_base: str = RSSHUB_BASE_URL) -> List[FeedItem]:
    all_items: List[FeedItem] = []
    any_success = False

    for source in SOURCES:
        url = rsshub_base + source["path"]
        logger.info("Fetching %s from %s", source["name"], url)

        raw = _fetch_with_retry(url)
        if raw is None:
            logger.error("Failed to fetch source: %s", source["name"])
            continue

        try:
            parsed = feedparser.parse(raw)
        except Exception as e:
            logger.error("Failed to parse feed for %s: %s", source["name"], e)
            continue

        entries = parsed.entries[:MAX_ITEMS_PER_SOURCE]
        if not entries:
            logger.warning("No entries found for %s", source["name"])
            continue

        any_success = True
        for rank, entry in enumerate(entries):
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            if not title or not link:
                continue
            all_items.append(FeedItem(
                title=title,
                link=link,
                summary=summary,
                source_name=source["name"],
                source_weight=source["weight"],
                rank=rank,
            ))

        logger.info("Fetched %d items from %s", len(entries), source["name"])

    if not any_success:
        raise RuntimeError("All RSS sources failed — aborting")

    logger.info("Total items fetched: %d", len(all_items))
    return all_items
