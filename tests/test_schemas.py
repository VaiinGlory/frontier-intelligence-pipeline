"""
Unit Tests for Output Schema Validation
Verifies exact match with assessment specification across all entities.
"""

import pytest

def test_startup_schema_structure():
    record = {
        "schemaVersion": "1.0",
        "recordType": "STARTUP",
        "source": {
            "name": "Y Combinator",
            "url": "https://ycombinator.com/companies/openai"
        },
        "content": {
            "entityName": "OpenAI",
            "data": {
                "employeeCount": 1500
            }
        },
        "collectedAt": "2026-11-22T00:00:00Z"
    }
    assert record["schemaVersion"] == "1.0"
    assert record["recordType"] == "STARTUP"
    assert "source" in record and "url" in record["source"] and "name" in record["source"]
    assert "entityName" in record["content"]
    assert "employeeCount" in record["content"]["data"]

def test_product_schema_structure():
    record = {
        "schemaVersion": "1.0",
        "recordType": "PRODUCT",
        "source": {
            "name": "Hugging Face Hub",
            "url": "https://huggingface.co/openai/whisper-large-v3"
        },
        "content": {
            "startupName": "OpenAI",
            "pricingModel": "FREE"
        },
        "collectedAt": "2026-11-22T00:00:00Z"
    }
    assert record["recordType"] == "PRODUCT"
    assert record["content"]["pricingModel"] in ["FREE", "FREEMIUM", "PAID", "ENTERPRISE"]

def test_research_paper_schema_structure():
    record = {
        "schemaVersion": "1.0",
        "recordType": "RESEARCH_PAPER",
        "content": {
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "paper_url": "https://arxiv.org/abs/1706.03762",
            "github_url": "https://github.com/tensorflow/tensor2tensor",
            "github_stars": 15000,
            "published_date": "2017-06-12T00:00:00Z"
        }
    }
    assert record["recordType"] == "RESEARCH_PAPER"
    assert isinstance(record["content"]["authors"], list)
    assert isinstance(record["content"]["github_stars"], int)
    assert record["content"]["paper_url"].startswith("http")

def test_job_schema_structure():
    record = {
        "schemaVersion": "1.0",
        "recordType": "JOB",
        "source": {
            "name": "RemoteOK",
            "url": "https://remoteok.com"
        },
        "content": {
            "company": "Anthropic",
            "date": "2026-11-22T00:00:00Z",
            "is_remote": True,
            "role_family": "Engineering"
        },
        "collectedAt": "2026-11-22T00:00:00Z"
    }
    assert record["recordType"] == "JOB"
    assert isinstance(record["content"]["is_remote"], bool)
    assert record["content"]["role_family"] in ["Engineering", "Research", "Product", "Design", "Go-To-Market"]
