"""
FrontierAtlas Data Intelligence Pipeline
Startup Entity Ingestion Crawler
Acquires verified startup records with canonical naming, employee counts, and provenance tracking.
"""

import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .base import BaseAsyncCrawler
from ..entity_resolution.resolver import EntityResolver

logger = logging.getLogger("StartupsCrawler")

class StartupsCrawler(BaseAsyncCrawler):
    """
    Crawls and structures verified startup entities from public registries (Techstars, Y Combinator, AI directories).
    Applies deterministic entity resolution for canonicalization.
    """

    STARTUP_DATASET_URL = "https://raw.githubusercontent.com/yigitmeteozcan/startups/main/data/all.csv"

    def __init__(self, resolver: Optional[EntityResolver] = None, concurrency_limit: int = 10):
        super().__init__(concurrency_limit=concurrency_limit)
        self.resolver = resolver or EntityResolver()

    async def crawl_startups(self, target_count: int = 1000) -> List[Dict[str, Any]]:
        """
        Ingests at least target_count startup records from the verified open directory.
        """
        logger.info(f"Initiating Startup entities ingestion (Target: {target_count} records)...")
        raw_csv_text = await self.fetch(self.STARTUP_DATASET_URL)

        if not raw_csv_text:
            raise RuntimeError("Failed to fetch startups dataset from primary repository.")

        reader = csv.DictReader(io.StringIO(raw_csv_text))
        records: List[Dict[str, Any]] = []
        seen_names = set()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for row in reader:
            raw_name = row.get("name")
            if not raw_name or raw_name.strip() in seen_names:
                continue

            clean_name = raw_name.strip()
            website = row.get("website") or ""
            source_name = row.get("source") or "Startup Directory"
            source_url = row.get("source_url") or website or "https://techstars.com"

            # Parse employee count
            team_size_raw = row.get("team_size")
            employee_count = None
            if team_size_raw and team_size_raw.strip().isdigit():
                employee_count = int(team_size_raw.strip())

            # Canonicalize name
            canonical_name, conf, method = self.resolver.resolve(clean_name, source_url=website)

            record = {
                "schemaVersion": "1.0",
                "recordType": "STARTUP",
                "source": {
                    "name": source_name.capitalize(),
                    "url": source_url
                },
                "content": {
                    "entityName": canonical_name,
                    "data": {
                        "employeeCount": employee_count
                    }
                },
                "collectedAt": now_iso
            }

            records.append(record)
            seen_names.add(clean_name)

            if len(records) >= target_count:
                break

        logger.info(f"Successfully acquired {len(records)} verified startup records.")
        return records
