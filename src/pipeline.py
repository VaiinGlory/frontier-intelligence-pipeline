"""
FrontierAtlas Data Intelligence Pipeline
Master Pipeline Orchestrator
Coordinates Phase I (Bulk Extraction), Phase II (24h Fresh Signals), Phase III (LLM), and Phase IV (Entity Resolution)
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any

from .crawler.papers_crawler import PapersCrawler
from .crawler.startups_crawler import StartupsCrawler
from .crawler.products_crawler import ProductsCrawler
from .crawler.news_crawler import NewsCrawler
from .crawler.jobs_crawler import JobsCrawler
from .entity_resolution.resolver import EntityResolver
from .freshness.normalizer import DateNormalizer
from .llm_engine.orchestrator import LLMOrchestrator
from .storage.exporter import DataExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("PipelineOrchestrator")

class MasterPipeline:
    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        self.resolver = EntityResolver()
        self.normalizer = DateNormalizer()
        self.llm_orchestrator = LLMOrchestrator(mock_mode=True)
        self.exporter = DataExporter(output_dir=output_dir)

    async def execute_all(
        self,
        startup_count: int = 1000,
        product_count: int = 1000,
        paper_count: int = 1000
    ) -> Dict[str, Any]:
        """Runs the complete ingestion pipeline across all phases."""
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("STARTING FRONTIERATLAS DATA INTELLIGENCE INGESTION ENGINE")
        logger.info("=" * 60)

        # Initialize crawlers
        papers_crawler = PapersCrawler()
        startups_crawler = StartupsCrawler(resolver=self.resolver)
        products_crawler = ProductsCrawler(resolver=self.resolver)
        news_crawler = NewsCrawler(normalizer=self.normalizer)
        jobs_crawler = JobsCrawler(normalizer=self.normalizer, resolver=self.resolver)

        try:
            # 1. Phase I: Bulk Extraction
            logger.info(">>> PHASE I: Commencing Massive Bulk Data Acquisition...")
            papers_task = asyncio.create_task(papers_crawler.crawl_papers(target_count=paper_count))
            startups_task = asyncio.create_task(startups_crawler.crawl_startups(target_count=startup_count))
            products_task = asyncio.create_task(products_crawler.crawl_products(target_count=product_count))

            # 2. Phase II: 24h High-Fidelity Signal Ingestion
            logger.info(">>> PHASE II: Ingesting 24-Hour Fresh Signals (5 News Feeds & 5 Job Boards)...")
            news_task = asyncio.create_task(news_crawler.crawl_fresh_news())
            jobs_task = asyncio.create_task(jobs_crawler.crawl_fresh_jobs())

            # Gather all concurrent tasks
            papers, startups, products, news, jobs = await asyncio.gather(
                papers_task, startups_task, products_task, news_task, jobs_task
            )

            # 3. Phase III: Demonstrate Multi-Tier LLM Orchestration
            logger.info(">>> PHASE III: Validating Multi-Tier LLM Extraction Engine & Fallback Chain...")
            sample_unstructured_text = "Acme AI raises $50M Series A with 120 employees in SF. Building frontier autonomous coding models."
            extracted_entity = self.llm_orchestrator.extract_with_fallback(
                raw_content=sample_unstructured_text,
                schema_type="STARTUP",
                system_instruction="Extract startup name and employee count from raw text into JSON."
            )
            logger.info(f"LLM Fallback Extraction Verification: {extracted_entity}")

            # 4. Phase IV: Entity Resolution & Canonicalization Mapping Log
            logger.info(">>> PHASE IV: Finalizing Deterministic Entity Resolution Audit Log...")
            mapping_log = self.resolver.get_mapping_log()

            # 5. Export Deliverables to 6 CSV Files
            logger.info(">>> DELIVERABLES: Exporting 6 Canonical Tables for Google Sheets...")
            f_startups = self.exporter.export_startups_csv(startups)
            f_products = self.exporter.export_products_csv(products)
            f_papers = self.exporter.export_papers_csv(papers)
            f_jobs = self.exporter.export_jobs_csv(jobs)
            f_news = self.exporter.export_news_csv(news)
            f_mapping = self.exporter.export_entity_mapping_csv(mapping_log)

            elapsed = time.time() - start_time
            logger.info("=" * 60)
            logger.info(f"PIPELINE RUN COMPLETED SUCCESSFULLY in {elapsed:.2f}s!")
            logger.info(f"Total Startups Ingested:        {len(startups):,}")
            logger.info(f"Total Products Ingested:        {len(products):,}")
            logger.info(f"Total Research Papers Ingested: {len(papers):,}")
            logger.info(f"Total Fresh News (<= 24h):      {len(news):,}")
            logger.info(f"Total Fresh Jobs (<= 24h):      {len(jobs):,}")
            logger.info(f"Total Entity Mappings Logged:   {len(mapping_log):,}")
            logger.info("=" * 60)

            return {
                "startups": len(startups),
                "products": len(products),
                "papers": len(papers),
                "news": len(news),
                "jobs": len(jobs),
                "mapping_log": len(mapping_log),
                "files": [f_startups, f_products, f_papers, f_jobs, f_news, f_mapping],
                "elapsed_seconds": elapsed
            }

        finally:
            await papers_crawler.close()
            await startups_crawler.close()
            await products_crawler.close()
            await news_crawler.close()
            await jobs_crawler.close()

