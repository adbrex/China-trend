"""RSS 2.0 feed generator."""

import logging
import os
from datetime import datetime, timezone
from email.utils import formatdate
from typing import List
from xml.sax.saxutils import escape

from .fetcher import FeedItem

logger = logging.getLogger(__name__)

FEED_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "feed.xml")
FEED_TITLE = "中国トレンド日報"
FEED_DESCRIPTION = "中国主要メディアの話題記事を日本語要約（1日2回更新）"
FEED_LANGUAGE = "ja"
FEED_LINK = "https://example.github.io/china-trends/"  # Updated at deploy time via env


def _rfc822(dt: datetime) -> str:
    return formatdate(dt.timestamp(), usegmt=True)


def _build_description_html(content: str, reason: str, value: str) -> str:
    parts = []
    if content:
        parts.append(f"<p><strong>内容:</strong> {escape(content)}</p>")
    if reason:
        parts.append(f"<p><strong>注目理由:</strong> {escape(reason)}</p>")
    if value:
        parts.append(f"<p><strong>リサーチ価値:</strong> {escape(value)}</p>")
    return "\n".join(parts) if parts else "<p>（要約なし）</p>"


def _cdata(text: str) -> str:
    # Escape CDATA end sequences
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def generate_feed(summaries: List[dict], output_path: str = FEED_FILE) -> None:
    now = datetime.now(timezone.utc)
    pub_date = _rfc822(now)
    feed_link = os.environ.get("FEED_LINK", FEED_LINK)

    items_xml = []
    for s in summaries:
        item: FeedItem = s["item"]
        title_text = f"[{item.source_name}] {s['title']}"
        description_html = _build_description_html(s["content"], s["reason"], s["value"])

        item_xml = f"""  <item>
    <title>{_cdata(title_text)}</title>
    <link>{escape(item.link)}</link>
    <description>{_cdata(description_html)}</description>
    <pubDate>{pub_date}</pubDate>
    <guid isPermaLink="true">{escape(item.link)}</guid>
  </item>"""
        items_xml.append(item_xml)

    feed_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_cdata(FEED_TITLE)}</title>
    <link>{escape(feed_link)}</link>
    <description>{_cdata(FEED_DESCRIPTION)}</description>
    <language>{FEED_LANGUAGE}</language>
    <lastBuildDate>{pub_date}</lastBuildDate>
    <atom:link href="{escape(feed_link)}feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(feed_xml)

    logger.info("Feed written to %s (%d items)", output_path, len(summaries))
