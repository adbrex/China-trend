"""Claude Haiku summarizer — one API call for all items."""

import logging
import os
import time
from typing import List

import anthropic

from .fetcher import FeedItem

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 4000
MAX_RETRIES = 3

PROMPT_TEMPLATE = """\
以下は中国の主要メディアで話題の記事10本です。
リサーチ用途の日本人読者向けに、各記事を以下のフォーマットで日本語要約してください。

[番号] 日本語訳タイトル
- 内容: 2〜3行で記事の要点
- 注目理由: なぜ中国で話題になっているか（1行）
- リサーチ価値: ★☆☆ / ★★☆ / ★★★（日本人リサーチャー視点での重要度）

記事リスト:
{items_block}"""


def _build_items_block(items: List[FeedItem]) -> str:
    lines = []
    for i, item in enumerate(items, start=1):
        lines.append(f"{i}. [{item.source_name}] {item.title}")
        if item.summary:
            # Truncate long summaries to keep prompt size reasonable
            snippet = item.summary[:300].replace("\n", " ")
            lines.append(f"   概要: {snippet}")
        lines.append(f"   URL: {item.link}")
        lines.append("")
    return "\n".join(lines)


def _call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except anthropic.RateLimitError as e:
            wait = 2 ** (attempt + 2)
            logger.warning("Rate limit hit (attempt %d/%d). Retrying in %ds: %s", attempt + 1, MAX_RETRIES, wait, e)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            wait = 2 ** (attempt + 1)
            logger.warning("API error (attempt %d/%d): %s. Retrying in %ds", attempt + 1, MAX_RETRIES, e, wait)
            time.sleep(wait)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** (attempt + 1)
            logger.warning("Unexpected error (attempt %d/%d): %s. Retrying in %ds", attempt + 1, MAX_RETRIES, e, wait)
            time.sleep(wait)

    raise RuntimeError(f"Claude API failed after {MAX_RETRIES} retries")


def _parse_summary_block(text: str, index: int) -> dict:
    """Extract structured fields from one numbered block."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    title_line = lines[0] if lines else f"記事 {index}"
    # Strip leading "[番号] " prefix if present
    import re
    title_line = re.sub(r"^\[\d+\]\s*", "", title_line).strip()

    content = ""
    reason = ""
    value = ""

    for line in lines[1:]:
        if line.startswith("- 内容:"):
            content = line[len("- 内容:"):].strip()
        elif line.startswith("- 注目理由:"):
            reason = line[len("- 注目理由:"):].strip()
        elif line.startswith("- リサーチ価値:"):
            value = line[len("- リサーチ価値:"):].strip()

    return {"title": title_line, "content": content, "reason": reason, "value": value}


def _split_into_blocks(raw: str, n: int) -> List[str]:
    """Split Claude's response into per-item blocks by [N] markers."""
    import re
    parts = re.split(r"(?=\[\d+\])", raw.strip())
    blocks = [p.strip() for p in parts if p.strip()]
    # If splitting didn't yield enough blocks, return what we have
    return blocks[:n]


def summarize(items: List[FeedItem]) -> List[dict]:
    """
    Call Claude once for all items.
    Returns list of dicts with keys: title, content, reason, value (plus original item).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=api_key)

    items_block = _build_items_block(items)
    prompt = PROMPT_TEMPLATE.format(items_block=items_block)

    logger.info("Calling Claude %s for %d items (max_tokens=%d)", MODEL, len(items), MAX_TOKENS)
    raw_response = _call_claude(client, prompt)
    logger.info("Received %d chars from Claude", len(raw_response))

    blocks = _split_into_blocks(raw_response, len(items))

    results = []
    for i, item in enumerate(items):
        if i < len(blocks):
            parsed = _parse_summary_block(blocks[i], i + 1)
        else:
            logger.warning("No summary block for item %d (%s), using fallback", i + 1, item.title)
            parsed = {"title": item.title, "content": "", "reason": "", "value": ""}
        results.append({**parsed, "item": item})

    return results
