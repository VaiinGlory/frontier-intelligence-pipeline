"""
FrontierAtlas Data Intelligence Pipeline
Data Storage & Canonical CSV / JSON Exporter Engine
Generates publication-ready CSVs mapped 1:1 to Google Sheets tabs.
"""

import csv
import json
import logging
import os
from typing import List, Dict, Any

from ..entity_resolution.resolver import MappingLogEntry

logger = logging.getLogger("DataExporter")

class DataExporter:
    """
    Exports structured pipeline entities into canonical CSV and JSON formats.
    """

    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_startups_csv(self, records: List[Dict[str, Any]], filename: str = "startups.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "schemaVersion", "recordType", "source.name", "source.url",
            "content.entityName", "content.data.employeeCount", "collectedAt"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.get("schemaVersion", "1.0"),
                    r.get("recordType", "STARTUP"),
                    r.get("source", {}).get("name", ""),
                    r.get("source", {}).get("url", ""),
                    r.get("content", {}).get("entityName", ""),
                    r.get("content", {}).get("data", {}).get("employeeCount", ""),
                    r.get("collectedAt", "")
                ])
        logger.info(f"Exported {len(records)} startups to {filepath}")
        return filepath

    def export_products_csv(self, records: List[Dict[str, Any]], filename: str = "products.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "schemaVersion", "recordType", "source.name", "source.url",
            "content.startupName", "content.pricingModel", "collectedAt"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.get("schemaVersion", "1.0"),
                    r.get("recordType", "PRODUCT"),
                    r.get("source", {}).get("name", ""),
                    r.get("source", {}).get("url", ""),
                    r.get("content", {}).get("startupName", ""),
                    r.get("content", {}).get("pricingModel", ""),
                    r.get("collectedAt", "")
                ])
        logger.info(f"Exported {len(records)} products to {filepath}")
        return filepath

    def export_papers_csv(self, records: List[Dict[str, Any]], filename: str = "research_papers.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "schemaVersion", "recordType", "content.title", "content.authors",
            "content.paper_url", "content.github_url", "content.github_stars",
            "content.published_date"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                authors_val = r.get("content", {}).get("authors", [])
                if isinstance(authors_val, list):
                    authors_str = "; ".join(authors_val)
                else:
                    authors_str = str(authors_val)

                writer.writerow([
                    r.get("schemaVersion", "1.0"),
                    r.get("recordType", "RESEARCH_PAPER"),
                    r.get("content", {}).get("title", ""),
                    authors_str,
                    r.get("content", {}).get("paper_url", ""),
                    r.get("content", {}).get("github_url", ""),
                    r.get("content", {}).get("github_stars", 0),
                    r.get("content", {}).get("published_date", "")
                ])
        logger.info(f"Exported {len(records)} research papers to {filepath}")
        return filepath

    def export_jobs_csv(self, records: List[Dict[str, Any]], filename: str = "jobs.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "schemaVersion", "recordType", "source.name", "source.url",
            "content.company", "content.date", "content.is_remote",
            "content.role_family", "collectedAt"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.get("schemaVersion", "1.0"),
                    r.get("recordType", "JOB"),
                    r.get("source", {}).get("name", ""),
                    r.get("source", {}).get("url", ""),
                    r.get("content", {}).get("company", ""),
                    r.get("content", {}).get("date", ""),
                    r.get("content", {}).get("is_remote", False),
                    r.get("content", {}).get("role_family", ""),
                    r.get("collectedAt", "")
                ])
        logger.info(f"Exported {len(records)} jobs to {filepath}")
        return filepath

    def export_news_csv(self, records: List[Dict[str, Any]], filename: str = "news.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "schemaVersion", "recordType", "source.name", "source.url",
            "content.title", "content.full_text", "content.published_date", "collectedAt"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                writer.writerow([
                    r.get("schemaVersion", "1.0"),
                    r.get("recordType", "NEWS"),
                    r.get("source", {}).get("name", ""),
                    r.get("source", {}).get("url", ""),
                    r.get("content", {}).get("title", ""),
                    r.get("content", {}).get("full_text", ""),
                    r.get("content", {}).get("published_date", ""),
                    r.get("collectedAt", "")
                ])
        logger.info(f"Exported {len(records)} news stories to {filepath}")
        return filepath

    def export_entity_mapping_csv(self, entries: List[MappingLogEntry], filename: str = "entity_mapping_log.csv") -> str:
        filepath = os.path.join(self.output_dir, filename)
        headers = [
            "raw_name", "canonical_name", "confidence_score",
            "resolution_method", "matched_entity", "resolved_at"
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for entry in entries:
                writer.writerow([
                    entry.raw_name,
                    entry.canonical_name,
                    entry.confidence_score,
                    entry.resolution_method,
                    entry.matched_entity,
                    entry.resolved_at
                ])
        logger.info(f"Exported {len(entries)} entity resolution logs to {filepath}")
        return filepath
