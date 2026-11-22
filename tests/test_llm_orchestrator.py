"""
Unit Tests for Multi-Tier LLM Orchestration & Intelligent Chunking
"""

import pytest
from src.llm_engine.chunker import SmartChunker
from src.llm_engine.orchestrator import LLMOrchestrator, RateLimitException, PayloadTooLargeException

def test_smart_chunker_html_cleaning():
    chunker = SmartChunker(max_chars=500)
    raw_html = """
    <html>
        <head>
            <script>var x = 10;</script>
            <style>.body { color: red; }</style>
            <meta name="description" content="AI platform description" />
        </head>
        <body>
            <nav><a href="/home">Home</a></nav>
            <article>
                <h1>Leading AI Laboratory</h1>
                <p>We train state-of-the-art multimodal foundation models.</p>
            </article>
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    cleaned = chunker.clean_html(raw_html)
    assert "Leading AI Laboratory" in cleaned
    assert "foundation models" in cleaned
    assert "var x = 10" not in cleaned
    assert "color: red" not in cleaned
    assert "Copyright 2026" not in cleaned
    assert "description: AI platform description" in cleaned

def test_chunker_size_bounding():
    chunker = SmartChunker(max_chars=100)
    long_text = "Paragraph One.\n\n" + ("Long sentence about artificial intelligence and neural networks. " * 5)
    chunks = chunker.chunk_text(long_text, max_chars=100)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100

def test_llm_orchestrator_mock_extraction():
    orchestrator = LLMOrchestrator(mock_mode=True)
    res = orchestrator.extract_with_fallback(
        raw_content="OpenAI employs 1500 engineers.",
        schema_type="STARTUP",
        system_instruction="Extract startup data."
    )
    assert res["recordType"] == "STARTUP"
    assert res["content"]["entityName"] == "OpenAI"
    assert res["content"]["data"]["employeeCount"] == 1500

def test_exponential_backoff_jitter_bounds():
    orchestrator = LLMOrchestrator(base_backoff_seconds=1.0, max_backoff_seconds=16.0)
    for attempt in range(5):
        backoff = orchestrator._calculate_backoff(attempt)
        max_possible = min(16.0, 1.0 * (2 ** attempt))
        assert 0.0 <= backoff <= max_possible

