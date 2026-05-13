"""Tests for scorer logic."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.fetcher import FeedItem
from src.scorer import (
    similarity,
    deduplicate,
    filter_seen,
    select_top,
    load_seen,
    save_seen,
)


def make_item(title: str, link: str = "https://example.com", source: str = "test", weight: float = 1.0, rank: int = 0) -> FeedItem:
    return FeedItem(title=title, link=link, summary="", source_name=source, source_weight=weight, rank=rank)


class TestSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(similarity("hello world", "hello world"), 1.0)

    def test_completely_different(self):
        self.assertLess(similarity("hello world", "foo bar baz"), 0.5)

    def test_cjk_similarity(self):
        # Nearly identical CJK titles should be caught
        self.assertGreaterEqual(similarity("中国经济最新动向", "中国经济最新动向"), 0.8)

    def test_cjk_dissimilar(self):
        self.assertLess(similarity("中国经济动向", "美国政治选举"), 0.5)


class TestDeduplicate(unittest.TestCase):
    def test_removes_near_duplicates(self):
        # Same title from two different sources (minor punctuation difference)
        items = [
            make_item("中国经济一季度GDP增速超预期 专家解读", link="https://a.com"),
            make_item("中国经济一季度GDP增速超预期专家解读", link="https://b.com"),
            make_item("美股大涨创历史新高", link="https://c.com"),
        ]
        result = deduplicate(items)
        self.assertEqual(len(result), 2)

    def test_keeps_distinct_items(self):
        items = [make_item(f"Article {i}", link=f"https://ex.com/{i}") for i in range(5)]
        result = deduplicate(items)
        self.assertEqual(len(result), 5)

    def test_first_item_wins(self):
        items = [
            make_item("中国GDP増長超预期", link="https://first.com"),
            make_item("中国GDP増長超預期", link="https://second.com"),
        ]
        result = deduplicate(items)
        self.assertEqual(result[0].link, "https://first.com")


class TestFilterSeen(unittest.TestCase):
    def test_filters_recent_urls(self):
        now = datetime.now(timezone.utc)
        seen = [{"url": "https://example.com/old", "seen_at": (now - timedelta(hours=12)).isoformat()}]
        items = [
            make_item("Old article", link="https://example.com/old"),
            make_item("New article", link="https://example.com/new"),
        ]
        result = filter_seen(items, seen)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].link, "https://example.com/new")

    def test_allows_old_urls(self):
        now = datetime.now(timezone.utc)
        seen = [{"url": "https://example.com/old", "seen_at": (now - timedelta(hours=25)).isoformat()}]
        items = [make_item("Old article", link="https://example.com/old")]
        result = filter_seen(items, seen)
        self.assertEqual(len(result), 1)


class TestSelectTop(unittest.TestCase):
    def test_returns_top_n(self):
        items = [make_item(f"Article {i}", link=f"https://ex.com/{i}", rank=i) for i in range(20)]
        result = select_top(items, n=10)
        self.assertEqual(len(result), 10)

    def test_higher_weight_preferred(self):
        low = make_item("Low weight", link="https://low.com", weight=0.5, rank=0)
        high = make_item("High weight", link="https://high.com", weight=2.0, rank=0)
        result = select_top([low, high], n=1)
        self.assertEqual(result[0].link, "https://high.com")

    def test_lower_rank_preferred(self):
        rank0 = make_item("First", link="https://first.com", rank=0)
        rank5 = make_item("Sixth", link="https://sixth.com", rank=5)
        result = select_top([rank5, rank0], n=1)
        self.assertEqual(result[0].link, "https://first.com")


class TestSeenPersistence(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("[]")
            path = f.name
        try:
            now = datetime.now(timezone.utc).isoformat()
            data = [{"url": "https://example.com", "seen_at": now}]
            save_seen(data, path=path)
            loaded = load_seen(path=path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["url"], "https://example.com")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
