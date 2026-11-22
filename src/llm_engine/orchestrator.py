"""
FrontierAtlas Data Intelligence Pipeline
Multi-Tier LLM Extraction Engine with Resilient Fallback Chain & 429/413 Handling
"""

import json
import logging
import math
import os
import random
import time
from typing import Dict, Any, Optional, List, Tuple

from .chunker import SmartChunker

logger = logging.getLogger("LLMOrchestrator")

class LLMProviderException(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code

class RateLimitException(LLMProviderException):
    def __init__(self, message: str = "429 Too Many Requests"):
        super().__init__(message, status_code=429)

class PayloadTooLargeException(LLMProviderException):
    def __init__(self, message: str = "413 Payload Too Large"):
        super().__init__(message, status_code=413)

class LLMOrchestrator:
    """
    Multi-tier LLM orchestration system.
    Chain: Tier 1 (Gemini Flash) -> Tier 2 (Groq Llama 3) -> Tier 3 (DeepSeek).
    Features:
    - Automatic exponential backoff with Full Jitter for 429 rate limits.
    - Intelligent payload chunking to prevent 413 errors.
    - Canonical schema enforcement.
    """

    PROVIDERS = ["gemini_flash", "groq_llama3", "deepseek"]

    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        max_retries_per_tier: int = 3,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
        chunker: Optional[SmartChunker] = None,
        mock_mode: bool = False
    ):
        self.api_keys = api_keys or {
            "gemini": os.getenv("GEMINI_API_KEY", ""),
            "groq": os.getenv("GROQ_API_KEY", ""),
            "deepseek": os.getenv("DEEPSEEK_API_KEY", "")
        }
        self.max_retries_per_tier = max_retries_per_tier
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.chunker = chunker or SmartChunker()
        self.mock_mode = mock_mode

        # Telemetry metrics
        self.metrics = {
            "calls_attempted": 0,
            "calls_succeeded": 0,
            "fallback_events": 0,
            "rate_limits_encountered": 0,
            "chunks_pruned": 0,
            "provider_success_distribution": {p: 0 for p in self.PROVIDERS}
        }

    def _calculate_backoff(self, attempt: int) -> float:
        """Computes exponential backoff with Full Jitter."""
        cap = min(self.max_backoff_seconds, self.base_backoff_seconds * (2 ** attempt))
        return random.uniform(0, cap)

    def _call_provider_mock(self, provider: str, prompt: str, schema_type: str) -> str:
        """Simulates high-fidelity extraction in dry-run/mock mode."""
        if schema_type == "STARTUP":
            return json.dumps({
                "schemaVersion": "1.0",
                "recordType": "STARTUP",
                "content": {
                    "entityName": "OpenAI",
                    "data": {"employeeCount": 1500}
                }
            })
        elif schema_type == "PRODUCT":
            return json.dumps({
                "schemaVersion": "1.0",
                "recordType": "PRODUCT",
                "content": {
                    "startupName": "OpenAI",
                    "pricingModel": "FREEMIUM"
                }
            })
        elif schema_type == "JOB":
            return json.dumps({
                "schemaVersion": "1.0",
                "recordType": "JOB",
                "content": {
                    "company": "Anthropic",
                    "is_remote": True,
                    "role_family": "Engineering"
                }
            })
        return json.dumps({"status": "parsed", "provider": provider})

    def _call_gemini_flash(self, prompt: str, schema_type: str) -> str:
        """Tier 1: Gemini Flash API caller."""
        if self.mock_mode or not self.api_keys.get("gemini"):
            return self._call_provider_mock("gemini_flash", prompt, schema_type)
        # Production REST invocation for Gemini Flash
        import urllib.request
        key = self.api_keys["gemini"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode('utf-8'))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitException("Gemini Flash 429 Quota Exceeded")
            elif e.code == 413:
                raise PayloadTooLargeException("Gemini Flash 413 Payload Too Large")
            raise LLMProviderException(f"Gemini Flash HTTP {e.code}: {e.reason}", e.code)

    def _call_groq_llama3(self, prompt: str, schema_type: str) -> str:
        """Tier 2: Groq Llama 3 API caller."""
        if self.mock_mode or not self.api_keys.get("groq"):
            return self._call_provider_mock("groq_llama3", prompt, schema_type)
        import urllib.request
        key = self.api_keys["groq"]
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                data = json.loads(res.read().decode('utf-8'))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitException("Groq Llama3 429 Rate Limited")
            elif e.code == 413:
                raise PayloadTooLargeException("Groq Llama3 413 Payload Too Large")
            raise LLMProviderException(f"Groq HTTP {e.code}: {e.reason}", e.code)

    def _call_deepseek(self, prompt: str, schema_type: str) -> str:
        """Tier 3: DeepSeek API caller."""
        if self.mock_mode or not self.api_keys.get("deepseek"):
            return self._call_provider_mock("deepseek", prompt, schema_type)
        import urllib.request
        key = self.api_keys["deepseek"]
        url = "https://api.deepseek.com/v1/chat/completions"
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                data = json.loads(res.read().decode('utf-8'))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitException("DeepSeek 429 Rate Limited")
            elif e.code == 413:
                raise PayloadTooLargeException("DeepSeek 413 Payload Too Large")
            raise LLMProviderException(f"DeepSeek HTTP {e.code}: {e.reason}", e.code)

    def extract_with_fallback(self, raw_content: str, schema_type: str, system_instruction: str) -> Dict[str, Any]:
        """
        Executes multi-tier fallback extraction with chunk pruning and 429 retries.
        """
        self.metrics["calls_attempted"] += 1

        # 1. Chunk & Prune payload to guarantee 413 safety
        pruned_content = self.chunker.prune_for_extraction(raw_content)
        if len(pruned_content) < len(raw_content):
            self.metrics["chunks_pruned"] += 1

        prompt = f"{system_instruction}\n\nCanonical Schema Target: {schema_type}\n\nCONTENT:\n{pruned_content}\n\nRespond ONLY with valid JSON."

        provider_funcs = [
            ("gemini_flash", self._call_gemini_flash),
            ("groq_llama3", self._call_groq_llama3),
            ("deepseek", self._call_deepseek)
        ]

        last_exception = None

        for tier_idx, (provider_name, call_fn) in enumerate(provider_funcs):
            for attempt in range(self.max_retries_per_tier):
                try:
                    logger.debug(f"Attempting extraction via {provider_name} (attempt {attempt + 1})")
                    raw_resp = call_fn(prompt, schema_type)
                    parsed_json = json.loads(raw_resp)

                    # Update telemetry
                    self.metrics["calls_succeeded"] += 1
                    self.metrics["provider_success_distribution"][provider_name] += 1
                    return parsed_json

                except RateLimitException as rle:
                    self.metrics["rate_limits_encountered"] += 1
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(f"Rate limited (429) on {provider_name}. Backing off {backoff:.2f}s...")
                    time.sleep(backoff)
                    last_exception = rle

                except PayloadTooLargeException as ptle:
                    # If 413 occurs despite initial pruning, aggressively halve context
                    logger.warning(f"Payload 413 on {provider_name}. Reducing chunk limit by 50%...")
                    self.chunker.max_chars = max(2000, self.chunker.max_chars // 2)
                    pruned_content = self.chunker.prune_for_extraction(raw_content)
                    prompt = f"{system_instruction}\n\nSchema: {schema_type}\n\nCONTENT:\n{pruned_content}\n\nJSON:"
                    last_exception = ptle

                except Exception as ex:
                    logger.error(f"Error on {provider_name}: {ex}")
                    last_exception = ex
                    break  # Failover to next tier for fatal provider errors

            # If retries exhausted for this tier, record fallback event and proceed to next provider
            if tier_idx < len(provider_funcs) - 1:
                self.metrics["fallback_events"] += 1
                logger.info(f"Failing over from {provider_name} to next tier: {provider_funcs[tier_idx + 1][0]}")

        # If all tiers fail
        raise RuntimeError(f"All LLM extraction tiers exhausted. Last error: {last_exception}")

