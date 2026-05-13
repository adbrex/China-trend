"""Entry point: python -m src.main"""

import logging
import sys
from datetime import datetime, timezone

from .fetcher import fetch_all_sources
from .scorer import deduplicate, filter_seen, load_seen, save_seen, select_top
from .summarizer import summarize
from .feed_writer import generate_feed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("=== China Trends Feed Generator starting ===")

    # 1. Fetch
    try:
        items = fetch_all_sources()
    except RuntimeError as e:
        logger.error("Fatal fetch error: %s", e)
        return 1

    # 2. Deduplicate across sources
    items = deduplicate(items)

    # 3. Filter already-seen items
    seen = load_seen()
    items = filter_seen(items, seen)

    if not items:
        logger.warning("No new items after filtering — skipping API call and feed update")
        return 0

    # 4. Score and pick top N
    top_items = select_top(items)
    logger.info("Selected %d items for summarization", len(top_items))

    # 5. Summarize with Claude (single API call)
    try:
        summaries = summarize(top_items)
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        return 1

    # 6. Write RSS feed
    try:
        generate_feed(summaries)
    except Exception as e:
        logger.error("Feed generation failed: %s", e)
        return 1

    # 7. Update seen list
    now = datetime.now(timezone.utc).isoformat()
    new_seen = seen + [{"url": item.link, "seen_at": now} for item in top_items]
    save_seen(new_seen)

    logger.info("=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
