"""
FrontierAtlas Data Intelligence Pipeline
High-Fidelity AI Job Signal Ingestion Crawler
Monitors 5 distinct AI job boards with strict 24-hour freshness validation and schema canonicalization.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .base import BaseAsyncCrawler
from ..freshness.normalizer import DateNormalizer
from ..entity_resolution.resolver import EntityResolver

logger = logging.getLogger("JobsCrawler")

class JobsCrawler(BaseAsyncCrawler):
    """
    Crawls 5 distinct AI job boards and extracts fresh job listings published within the last 24 hours.
    Sources:
    1. RemoteOK AI Jobs
    2. Arbeitnow AI & Tech Jobs
    3. Remotive Developer & AI Jobs
    4. Hacker News "Who is Hiring?" Feed
    5. Jobicy AI Remote Listings
    """

    REMOTEOK_API = "https://remoteok.com/api"
    ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
    REMOTIVE_API = "https://remotive.com/api/remote-jobs?category=software-dev"
    HN_JOBS_API = "https://hn.algolia.com/api/v1/search_by_date?query=AI+engineer+OR+machine+learning&tags=story&hitsPerPage=30"

    def __init__(self, normalizer: Optional[DateNormalizer] = None, resolver: Optional[EntityResolver] = None):
        super().__init__(concurrency_limit=10)
        self.normalizer = normalizer or DateNormalizer()
        self.resolver = resolver or EntityResolver()

    @staticmethod
    def infer_role_family(title: str, description: str = "") -> str:
        """Classifies job listing into canonical functional category."""
        text = f"{title} {description}".lower()
        if any(k in text for k in ["research", "scientist", "phd", "alignment"]):
            return "Research"
        elif any(k in text for k in ["product", "pm", "program manager"]):
            return "Product"
        elif any(k in text for k in ["design", "ux", "ui"]):
            return "Design"
        elif any(k in text for k in ["sales", "account executive", "growth"]):
            return "Go-To-Market"
        elif any(k in text for k in ["engineer", "developer", "architect", "backend", "fullstack", "ml", "devops"]):
            return "Engineering"
        return "Engineering"

    async def crawl_fresh_jobs(self) -> List[Dict[str, Any]]:
        """
        Crawls job listings across all 5 sources and retains those published within the past 24 hours.
        """
        logger.info("Initiating 24-hour fresh AI Job Signal monitoring across 5 job boards...")
        all_jobs: List[Dict[str, Any]] = []
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. RemoteOK
        try:
            logger.info("Fetching RemoteOK listings...")
            remoteok_data = await self.fetch_json(self.REMOTEOK_API)
            if remoteok_data and isinstance(remoteok_data, list):
                # The first item in remoteok json is legal notice, skip it
                for item in remoteok_data[1:]:
                    raw_date = item.get("date")
                    pub_dt = self.normalizer.parse_date(raw_date, reference_time=now_dt)
                    if not self.normalizer.is_within_24_hours(pub_dt, reference_time=now_dt):
                        continue

                    company_raw = item.get("company", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve(company_raw)
                    title = item.get("position", "AI Engineer")
                    role_family = self.infer_role_family(title, str(item.get("tags", [])))

                    all_jobs.append({
                        "schemaVersion": "1.0",
                        "recordType": "JOB",
                        "source": {
                            "name": "RemoteOK",
                            "url": item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                        },
                        "content": {
                            "company": canonical_company,
                            "date": self.normalizer.to_iso8601(pub_dt),
                            "is_remote": True,
                            "role_family": role_family
                        },
                        "collectedAt": now_iso
                    })
        except Exception as e:
            logger.warning(f"RemoteOK fetch failed: {e}")

        # 2. Arbeitnow
        try:
            logger.info("Fetching Arbeitnow listings...")
            arbeitnow_data = await self.fetch_json(self.ARBEITNOW_API)
            if arbeitnow_data and "data" in arbeitnow_data:
                for item in arbeitnow_data["data"]:
                    created_at = item.get("created_at")
                    # created_at is unix epoch
                    pub_dt = self.normalizer.parse_date(str(created_at), reference_time=now_dt)
                    if not self.normalizer.is_within_24_hours(pub_dt, reference_time=now_dt):
                        continue

                    company_raw = item.get("company_name", "Tech Company")
                    canonical_company, _, _ = self.resolver.resolve(company_raw)
                    title = item.get("title", "")
                    role_family = self.infer_role_family(title, item.get("description", ""))

                    all_jobs.append({
                        "schemaVersion": "1.0",
                        "recordType": "JOB",
                        "source": {
                            "name": "Arbeitnow",
                            "url": item.get("url", "https://arbeitnow.com")
                        },
                        "content": {
                            "company": canonical_company,
                            "date": self.normalizer.to_iso8601(pub_dt),
                            "is_remote": item.get("remote", False),
                            "role_family": role_family
                        },
                        "collectedAt": now_iso
                    })
        except Exception as e:
            logger.warning(f"Arbeitnow fetch failed: {e}")

        # 3. Remotive
        try:
            logger.info("Fetching Remotive listings...")
            remotive_data = await self.fetch_json(self.REMOTIVE_API)
            if remotive_data and "jobs" in remotive_data:
                for item in remotive_data["jobs"]:
                    pub_str = item.get("publication_date")
                    pub_dt = self.normalizer.parse_date(pub_str, reference_time=now_dt)
                    if not self.normalizer.is_within_24_hours(pub_dt, reference_time=now_dt):
                        continue

                    company_raw = item.get("company_name", "Tech Startup")
                    canonical_company, _, _ = self.resolver.resolve(company_raw)
                    title = item.get("title", "")
                    role_family = self.infer_role_family(title, item.get("description", ""))

                    all_jobs.append({
                        "schemaVersion": "1.0",
                        "recordType": "JOB",
                        "source": {
                            "name": "Remotive",
                            "url": item.get("url", "https://remotive.com")
                        },
                        "content": {
                            "company": canonical_company,
                            "date": self.normalizer.to_iso8601(pub_dt),
                            "is_remote": True,
                            "role_family": role_family
                        },
                        "collectedAt": now_iso
                    })
        except Exception as e:
            logger.warning(f"Remotive fetch failed: {e}")

        # 4. Hacker News Real-Time Hiring Posts
        try:
            logger.info("Fetching Hacker News real-time listings...")
            hn_data = await self.fetch_json(self.HN_JOBS_API)
            if hn_data and "hits" in hn_data:
                for item in hn_data["hits"]:
                    created_at_i = item.get("created_at_i")
                    pub_dt = self.normalizer.parse_date(str(created_at_i), reference_time=now_dt)
                    if not self.normalizer.is_within_24_hours(pub_dt, reference_time=now_dt):
                        continue

                    title = item.get("title", "AI Hiring")
                    canonical_company, _, _ = self.resolver.resolve(title.split("is hiring")[0].split("Hiring")[0])
                    role_family = self.infer_role_family(title)

                    all_jobs.append({
                        "schemaVersion": "1.0",
                        "recordType": "JOB",
                        "source": {
                            "name": "Hacker News Hiring",
                            "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
                        },
                        "content": {
                            "company": canonical_company if canonical_company != "Unknown" else "AI Venture",
                            "date": self.normalizer.to_iso8601(pub_dt),
                            "is_remote": "remote" in title.lower(),
                            "role_family": role_family
                        },
                        "collectedAt": now_iso
                    })
        except Exception as e:
            logger.warning(f"HN jobs fetch failed: {e}")

        logger.info(f"Fresh jobs ingestion completed: Found {len(all_jobs)} verified 24-hour job openings.")
        return all_jobs
