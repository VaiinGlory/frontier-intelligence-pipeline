#!/usr/bin/env python3
"""
FrontierAtlas Data Intelligence Pipeline
CLI Runner & Benchmark Entrypoint
"""

import argparse
import asyncio
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import MasterPipeline

def main():
    parser = argparse.ArgumentParser(description="FrontierAtlas Data Intelligence Ingestion Pipeline")
    parser.add_argument("--startups", type=int, default=1000, help="Target startup entities count (default: 1000)")
    parser.add_argument("--products", type=int, default=1000, help="Target product entities count (default: 1000)")
    parser.add_argument("--papers", type=int, default=1000, help="Target research papers count (default: 1000)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory for generated CSVs")

    args = parser.parse_args()

    pipeline = MasterPipeline(output_dir=args.output_dir)
    results = asyncio.run(pipeline.execute_all(
        startup_count=args.startups,
        product_count=args.products,
        paper_count=args.papers
    ))

    print("\nSummary of Generated Deliverables:")
    for f in results["files"]:
        print(f" -> {f}")

if __name__ == "__main__":
    main()
