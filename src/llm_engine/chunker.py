"""
FrontierAtlas Data Intelligence Pipeline
Intelligent Semantic Chunking & Payload Truncation Engine
Prevents HTTP 413 (Payload Too Large) errors while retaining maximum semantic density.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

class SmartChunker:
    """
    Intelligently reduces raw HTML/text into semantically dense chunks.
    Strips noise (boilerplate, scripts, styles, tracking tags) and applies
    token-aware sliding-window chunking.
    """

    DEFAULT_MAX_CHARS = 32000  # Approx 8,000 tokens, well below 413 thresholds

    NOISY_TAGS = [
        "script", "style", "noscript", "svg", "nav", "footer", 
        "header", "aside", "form", "iframe", "symbol"
    ]

    HIGH_VALUE_TAGS = ["main", "article", "section", "div.content", "div.job-description"]

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS):
        self.max_chars = max_chars

    def clean_html(self, raw_html: str) -> str:
        """Removes script, style, navigation, and boilerplate markup."""
        if not raw_html:
            return ""

        soup = BeautifulSoup(raw_html, "html.parser")

        # 1. Strip useless tags
        for tag in soup(self.NOISY_TAGS):
            tag.decompose()

        # 2. Extract meta tags of interest (author, published, description)
        meta_info = []
        for meta in soup.find_all("meta"):
            name = meta.get("name") or meta.get("property") or ""
            content = meta.get("content") or ""
            if any(k in name.lower() for k in ["title", "description", "date", "time", "author", "price", "company"]):
                meta_info.append(f"{name}: {content}")

        meta_block = "\n".join(meta_info[:15])

        # 3. Target main content if available
        main_content = None
        for selector in ["main", "article", "[role='main']"]:
            found = soup.select_one(selector)
            if found:
                main_content = found.get_text(separator="\n", strip=True)
                break

        if not main_content:
            main_content = soup.get_text(separator="\n", strip=True)

        # 4. Clean consecutive whitespaces and empty lines
        clean_text = re.sub(r'\n{3,}', '\n\n', main_content)
        clean_text = re.sub(r'[ \t]{2,}', ' ', clean_text)

        if meta_block:
            clean_text = f"--- METADATA ---\n{meta_block}\n--- BODY ---\n{clean_text}"

        return clean_text.strip()

    def chunk_text(self, text: str, max_chars: Optional[int] = None) -> List[str]:
        """
        Splits text into chunks of at most max_chars, breaking on paragraph or sentence boundaries.
        Guarantees that no individual chunk exceeds max_chars.
        """
        limit = max_chars or self.max_chars
        if len(text) <= limit:
            return [text]

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_len = len(para) + 2

            # If a single paragraph is longer than limit, split by sentence or hard limit
            if para_len > limit:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence_len = len(sentence) + 1
                    if current_len + sentence_len > limit:
                        if current_chunk:
                            chunks.append("\n\n".join(current_chunk))
                            current_chunk = []
                            current_len = 0
                    if sentence_len > limit:
                        # Hard slice
                        for i in range(0, len(sentence), limit):
                            chunks.append(sentence[i:i + limit])
                    else:
                        current_chunk.append(sentence)
                        current_len += sentence_len
            elif current_len + para_len > limit:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def prune_for_extraction(self, raw_html_or_text: str) -> str:
        """
        End-to-end cleaning and truncation: converts raw input into a safe,
        semantically rich string strictly within context bounds.
        """
        if "<html" in raw_html_or_text.lower() or "<body" in raw_html_or_text.lower() or "</" in raw_html_or_text:
            text = self.clean_html(raw_html_or_text)
        else:
            text = raw_html_or_text.strip()

        chunks = self.chunk_text(text, max_chars=self.max_chars)
        # For single entity extraction, chunk 0 retains title, metadata, and opening core body
        return chunks[0] if chunks else ""

