"""
Unit Tests for Deterministic Entity Resolution Engine
"""

import pytest
from src.entity_resolution.resolver import EntityResolver

def test_prompt_canonicalization_requirement():
    """
    Directly tests assessment specification:
    'For example, "OpenAI", "OpenAI, Inc.", and "Open AI" must resolve to the canonical "OpenAI".'
    """
    resolver = EntityResolver()

    cases = [
        "OpenAI",
        "OpenAI, Inc.",
        "Open AI",
        "OpenAI Inc",
        "OpenAI Global LLC",
        "OpenAI technologies"
    ]

    for raw in cases:
        canonical, score, method = resolver.resolve(raw)
        assert canonical == "OpenAI", f"Failed on {raw} -> got {canonical}"
        assert score >= 0.85

def test_other_canonical_ai_startups():
    resolver = EntityResolver()

    assert resolver.resolve("Anthropic PBC")[0] == "Anthropic"
    assert resolver.resolve("Anthropic AI")[0] == "Anthropic"
    assert resolver.resolve("Mistral AI SAS")[0] == "Mistral AI"
    assert resolver.resolve("Perplexity, Inc.")[0] == "Perplexity AI"
    assert resolver.resolve("Scale AI Inc")[0] == "Scale AI"
    assert resolver.resolve("HuggingFace Inc.")[0] == "Hugging Face"
    assert resolver.resolve("Cursor AI")[0] == "Anysphere"
    assert resolver.resolve("Stability AI Ltd")[0] == "Stability AI"
    assert resolver.resolve("Together Computer Inc")[0] == "Together AI"

def test_domain_matching():
    resolver = EntityResolver()
    cname, score, method = resolver.resolve("Random Text Name", source_url="https://openai.com/research")
    assert cname == "OpenAI"
    assert method == "DOMAIN_EXACT"
    assert score == 1.0

def test_mapping_log_generation():
    resolver = EntityResolver()
    resolver.resolve("OpenAI, Inc.")
    resolver.resolve("Anthropic PBC")

    log = resolver.get_mapping_log()
    assert len(log) == 2
    assert log[0].raw_name == "OpenAI, Inc."
    assert log[0].canonical_name == "OpenAI"
    assert log[1].raw_name == "Anthropic PBC"
    assert log[1].canonical_name == "Anthropic"
