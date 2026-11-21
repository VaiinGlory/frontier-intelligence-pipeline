"""
FrontierAtlas Data Intelligence Pipeline
Base Asynchronous Crawler with Fault Tolerance, Concurrency Governance, and Stealth Retries
"""

import asyncio
import logging
import random
from typing import Optional, Dict, Any
import aiohttp

from .antibot import AntiBotManager

logger = logging.getLogger("BaseCrawler")

class BaseAsyncCrawler:
    """
    Production-grade asynchronous crawler base.
    Features:
    - asyncio.Semaphore concurrency bounding.
    - Connection pooling via aiohttp.TCPConnector.
    - Exponential backoff with jitter on HTTP 429 and 5xx.
    - Adaptive stealth header rotation.
    """

    def __init__(
        self,
        concurrency_limit: int = 20,
        request_timeout: int = 15,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        anti_bot: Optional[AntiBotManager] = None
    ):
        self.concurrency_limit = concurrency_limit
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.anti_bot = anti_bot or AntiBotManager()
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=10,
                ssl=False,
                ttl_dns_cache=300
            )
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Fetches raw text/HTML from a URL with retry, backoff, and semaphore."""
        session = await self.get_session()
        async with self.semaphore:
            for attempt in range(self.max_retries):
                headers = self.anti_bot.get_stealth_headers(referer=referer)
                proxy = self.anti_bot.get_proxy()
                try:
                    async with session.get(url, headers=headers, proxy=proxy) as resp:
                        if resp.status == 200:
                            return await resp.text(errors="ignore")
                        elif resp.status in (429, 500, 502, 503, 504):
                            delay = random.uniform(0, self.base_backoff * (2 ** attempt))
                            logger.warning(f"HTTP {resp.status} on {url}. Retrying in {delay:.2f}s...")
                            await asyncio.sleep(delay)
                        else:
                            logger.error(f"HTTP {resp.status} unrecoverable on {url}")
                            return None
                except asyncio.TimeoutError:
                    delay = random.uniform(0.5, 2.0)
                    logger.warning(f"Timeout on {url}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.debug(f"Fetch error on {url}: {e}")
                    await asyncio.sleep(0.5)

        return None

    async def fetch_json(self, url: str, referer: Optional[str] = None) -> Optional[Any]:
        """Fetches and parses JSON from a URL."""
        session = await self.get_session()
        async with self.semaphore:
            for attempt in range(self.max_retries):
                headers = self.anti_bot.get_stealth_headers(referer=referer)
                proxy = self.anti_bot.get_proxy()
                try:
                    async with session.get(url, headers=headers, proxy=proxy) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        elif resp.status in (429, 500, 502, 503, 504):
                            delay = random.uniform(0, self.base_backoff * (2 ** attempt))
                            await asyncio.sleep(delay)
                        else:
                            return None
                except Exception as e:
                    logger.debug(f"JSON fetch error on {url}: {e}")
                    await asyncio.sleep(0.5)
        return None
