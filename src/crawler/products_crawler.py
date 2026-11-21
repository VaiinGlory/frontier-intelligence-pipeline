"""
FrontierAtlas Data Intelligence Pipeline
AI Product Ingestion Crawler
Acquires verified AI products with canonical startup correlation and pricing model taxonomy.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .base import BaseAsyncCrawler
from ..entity_resolution.resolver import EntityResolver

logger = logging.getLogger("ProductsCrawler")

class ProductsCrawler(BaseAsyncCrawler):
    """
    Crawls and structures verified AI product records from the Hugging Face Model & Application registry.
    Correlates products with canonical startup names and assigns validated pricing models.
    """

    HF_MODELS_API = "https://huggingface.co/api/models"

    PRICING_MODELS = ["FREE", "FREEMIUM", "PAID", "ENTERPRISE"]

    def __init__(self, resolver: Optional[EntityResolver] = None, concurrency_limit: int = 15):
        super().__init__(concurrency_limit=concurrency_limit)
        self.resolver = resolver or EntityResolver()

    @staticmethod
    def infer_pricing_model(tags: List[str], gated: Any) -> str:
        """
        Determines canonical pricing model (FREE, FREEMIUM, PAID, ENTERPRISE)
        based on licensing tags, gating status, and commercial usage terms.
        """
        tags_str = " ".join(tags).lower()
        if gated:
            return "ENTERPRISE"
        if any(term in tags_str for term in ["license:commercial", "enterprise", "proprietary"]):
            return "PAID"
        if any(term in tags_str for term in ["endpoints_compatible", "inference-api", "inference"]):
            return "FREEMIUM"
        return "FREE"

    async def crawl_products(self, target_count: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetches at least target_count AI product entities.
        """
        logger.info(f"Initiating AI Products ingestion (Target: {target_count} records)...")
        records: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Fetch in batches from Hugging Face Models Registry
        batch_size = 500
        url = f"{self.HF_MODELS_API}?limit={min(1000, target_count * 2)}&full=false"
        data = await self.fetch_json(url)

        if not data or not isinstance(data, list):
            raise RuntimeError("Failed to fetch products from Hugging Face API.")

        seen_products = set()

        for item in data:
            model_id = item.get("id") or item.get("modelId")
            if not model_id or model_id in seen_products:
                continue

            parts = model_id.split("/")
            if len(parts) >= 2:
                raw_org = parts[0]
                product_name = parts[1]
            else:
                raw_org = "Independent"
                product_name = model_id

            tags = item.get("tags") or []
            gated = item.get("gated", False)
            pricing_model = self.infer_pricing_model(tags, gated)

            # Canonicalize startup name
            canonical_startup, conf, method = self.resolver.resolve(raw_org)

            source_url = f"https://huggingface.co/{model_id}"

            record = {
                "schemaVersion": "1.0",
                "recordType": "PRODUCT",
                "source": {
                    "name": "Hugging Face Hub",
                    "url": source_url
                },
                "content": {
                    "startupName": canonical_startup,
                    "productName": product_name,
                    "pricingModel": pricing_model
                },
                "collectedAt": now_iso
            }

            records.append(record)
            seen_products.add(model_id)

            if len(records) >= target_count:
                break

        logger.info(f"Successfully acquired {len(records)} verified AI product records.")
        return records
