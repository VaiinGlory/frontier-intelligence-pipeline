"""
FrontierAtlas Data Intelligence Pipeline
High-Fidelity AI News Ingestion Crawler
Monitors 5 distinct AI news sources with strict 24-hour freshness validation and full-text extraction.
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from .base import BaseAsyncCrawler
from ..freshness.normalizer import DateNormalizer
from ..llm_engine.chunker import SmartChunker

logger = logging.getLogger("NewsCrawler")

class NewsCrawler(BaseAsyncCrawler):
    """
    Crawls 5 distinct AI news sources, extracts full text, and enforces strict 24-hour freshness.
    Sources:
    1. Google News AI Feed
    2. The Verge AI & Tech Feed
    3. Ars Technica Technology Lab
    4. MIT Technology Review
    5. BBC Technology AI Feed
    """

    NEWS_SOURCES = [
        {"name": "Google News AI", "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en", "type": "rss"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "type": "atom"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab", "type": "rss"},
        {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "type": "rss"},
        {"name": "BBC Tech", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "type": "rss"}
    ]

    def __init__(self, normalizer: Optional[DateNormalizer] = None, chunker: Optional[SmartChunker] = None):
        super().__init__(concurrency_limit=10)
        self.normalizer = normalizer or DateNormalizer()
        self.chunker = chunker or SmartChunker()

    async def crawl_fresh_news(self) -> List[Dict[str, Any]]:
        """
        Crawls all 5 sources and returns all news stories published within the last 24 hours.
        """
        logger.info("Initiating 24-hour fresh AI News monitoring across 5 sources...")
        all_news: List[Dict[str, Any]] = []
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        for src in self.NEWS_SOURCES:
            src_name = src["name"]
            feed_url = src["url"]
            logger.info(f"Checking feed: {src_name}...")

            raw_feed = await self.fetch(feed_url)
            if not raw_feed:
                logger.warning(f"Could not retrieve feed for {src_name}")
                continue

            parsed_items = self._parse_feed_items(raw_feed, src["type"])
            logger.info(f"Extracted {len(parsed_items)} raw articles from {src_name}")

            for item in parsed_items:
                title = item.get("title", "")
                link = item.get("link", "")
                pub_raw = item.get("pub_date", "")
                raw_content = item.get("description", "")

                # 1. Parse and validate freshness
                pub_dt = self.normalizer.parse_date(pub_raw, reference_time=now_dt)

                is_fresh = False
                if pub_dt:
                    is_fresh = self.normalizer.is_within_24_hours(pub_dt, reference_time=now_dt)
                else:
                    # Intelligent heuristic if source lacks strict date
                    is_fresh, pub_dt = self.normalizer.evaluate_freshness_heuristic(
                        content=f"{title} {raw_content}", url=link, reference_time=now_dt
                    )

                if not is_fresh or not pub_dt:
                    continue  # Guarantee 24-hour freshness

                pub_iso = self.normalizer.to_iso8601(pub_dt)

                # Clean full text/summary using chunker
                full_text = self.chunker.clean_html(raw_content) or title

                record = {
                    "schemaVersion": "1.0",
                    "recordType": "NEWS",
                    "source": {
                        "name": src_name,
                        "url": link
                    },
                    "content": {
                        "title": title,
                        "full_text": full_text[:4000],  # Concise full-text representation
                        "published_date": pub_iso
                    },
                    "collectedAt": now_iso
                }
                all_news.append(record)

        logger.info(f"Fresh news ingestion completed: Found {len(all_news)} verified 24-hour articles.")
        return all_news

    def _parse_feed_items(self, feed_text: str, feed_type: str) -> List[Dict[str, str]]:
        """Parses RSS / Atom feeds using ElementTree with fallback to BeautifulSoup."""
        items = []
        try:
            root = ET.fromstring(feed_text)
            # Standard RSS 2.0
            for item in root.findall(".//item"):
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                pub_date = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
                desc = item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
                items.append({"title": title.strip(), "link": link.strip(), "pub_date": pub_date.strip(), "description": desc.strip()})

            # Atom feed
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title") or ""
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_elem.get("href") if link_elem is not None else ""
                pub_date = entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("{http://www.w3.org/2005/Atom}updated") or ""
                desc = entry.findtext("{http://www.w3.org/2005/Atom}content") or entry.findtext("{http://www.w3.org/2005/Atom}summary") or ""
                items.append({"title": title.strip(), "link": link.strip(), "pub_date": pub_date.strip(), "description": desc.strip()})
        except Exception:
            # BeautifulSoup resilient fallback
            soup = BeautifulSoup(feed_text, "html.parser")
            for item in soup.find_all(["item", "entry"]):
                t = item.find(["title"])
                title = t.get_text() if t else ""
                l = item.find(["link"])
                link = (l.get("href") or l.get_text()) if l else ""
                d = item.find(["pubdate", "published", "updated"])
                pub_date = d.get_text() if d else ""
                c = item.find(["description", "content", "summary"])
                desc = c.get_text() if c else ""
                items.append({"title": title.strip(), "link": link.strip(), "pub_date": pub_date.strip(), "description": desc.strip()})

        return items
