"""
FrontierAtlas Data Intelligence Pipeline
Deterministic Entity Resolution & Canonicalization Engine
"""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, NamedTuple
from urllib.parse import urlparse

from .seed_data import SEED_AI_STARTUPS

class MappingLogEntry(NamedTuple):
    raw_name: str
    canonical_name: str
    confidence_score: float
    resolution_method: str
    matched_entity: str
    resolved_at: str

class EntityResolver:
    """
    Deduplication and Entity Resolution Engine.
    Canonicalizes noisy organization and product names (e.g., 'OpenAI', 'OpenAI, Inc.', 'Open AI' -> 'OpenAI').
    """

    LEGAL_SUFFIXES = [
        r'\binc\.?\b', r'\bincorporated\b', r'\bllc\.?\b', r'\bl\.l\.c\.?\b',
        r'\bcorp\.?\b', r'\bcorporation\b', r'\bltd\.?\b', r'\blimited\b',
        r'\bgmbh\b', r'\bsas\b', r'\bpbc\b', r'\bco\.?\b', r'\bcompany\b',
        r'\btechnologies\b', r'\btechnology\b', r'\blabs\b', r'\blab\b',
        r'\bsystems\b', r'\bholdings\b', r'\bgroup\b'
    ]

    def __init__(self, seed_startups: Optional[List[Dict]] = None):
        self.seed_startups = seed_startups if seed_startups is not None else SEED_AI_STARTUPS
        self.mapping_log: List[MappingLogEntry] = []
        self._build_index()

    def _normalize_string(self, text: str) -> str:
        """Strip accents, lower, remove legal entity suffixes, and clean punctuation."""
        if not text:
            return ""
        # Unicode normalization
        norm = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        norm = norm.lower()

        # Remove legal suffixes
        for suffix_pat in self.LEGAL_SUFFIXES:
            norm = re.sub(suffix_pat, '', norm, flags=re.IGNORECASE)

        # Remove punctuation except alphanumeric and space
        norm = re.sub(r'[^a-z0-9\s]', ' ', norm)
        # Collapse multiple spaces
        norm = re.sub(r'\s+', ' ', norm).strip()
        return norm

    def _build_index(self):
        """Build exact and alias inverted lookup tables for deterministic O(1) resolution."""
        self.exact_map: Dict[str, str] = {}
        self.alias_map: Dict[str, str] = {}
        self.domain_map: Dict[str, str] = {}
        self.canonical_entities: Dict[str, Dict] = {}

        for item in self.seed_startups:
            cname = item["canonical_name"]
            self.canonical_entities[cname] = item
            
            # Map canonical name directly
            norm_cname = self._normalize_string(cname)
            self.exact_map[norm_cname] = cname
            
            # Map domain if present
            if "domain" in item:
                self.domain_map[item["domain"].lower()] = cname

            # Map aliases
            for alias in item.get("aliases", []):
                norm_alias = self._normalize_string(alias)
                self.alias_map[norm_alias] = cname

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return EntityResolver._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    @classmethod
    def similarity_score(cls, s1: str, s2: str) -> float:
        """Normalized similarity ratio based on edit distance [0.0 - 1.0]."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        dist = cls._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return round(1.0 - (dist / max_len), 4)

    def resolve(self, raw_name: str, source_url: Optional[str] = None) -> Tuple[str, float, str]:
        """
        Resolves a raw string name to its canonical entity.
        Returns: (canonical_name, confidence_score, resolution_method)
        """
        if not raw_name or not raw_name.strip():
            return "Unknown", 0.0, "EMPTY_INPUT"

        clean_raw = raw_name.strip()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. URL Domain Matching
        if source_url:
            parsed = urlparse(source_url)
            domain = parsed.netloc.lower().replace("www.", "")
            for seed_domain, cname in self.domain_map.items():
                if domain == seed_domain or domain.endswith("." + seed_domain):
                    self.mapping_log.append(MappingLogEntry(
                        raw_name=clean_raw,
                        canonical_name=cname,
                        confidence_score=1.0,
                        resolution_method="DOMAIN_EXACT",
                        matched_entity=cname,
                        resolved_at=now_iso
                    ))
                    return cname, 1.0, "DOMAIN_EXACT"

        norm_raw = self._normalize_string(clean_raw)

        # 2. Exact Normalized Canonical Match
        if norm_raw in self.exact_map:
            cname = self.exact_map[norm_raw]
            self.mapping_log.append(MappingLogEntry(
                raw_name=clean_raw,
                canonical_name=cname,
                confidence_score=1.0,
                resolution_method="EXACT_NORMALIZED",
                matched_entity=cname,
                resolved_at=now_iso
            ))
            return cname, 1.0, "EXACT_NORMALIZED"

        # 3. Known Alias Match
        if norm_raw in self.alias_map:
            cname = self.alias_map[norm_raw]
            self.mapping_log.append(MappingLogEntry(
                raw_name=clean_raw,
                canonical_name=cname,
                confidence_score=0.98,
                resolution_method="ALIAS_LOOKUP",
                matched_entity=cname,
                resolved_at=now_iso
            ))
            return cname, 0.98, "ALIAS_LOOKUP"

        # 4. Fuzzy Similarity Matching against Canonical Seed Catalog
        best_match = None
        best_score = 0.0

        for norm_target, cname in self.exact_map.items():
            # Check prefix/token containment (e.g. "OpenAI Group" -> "OpenAI")
            if norm_target in norm_raw or norm_raw in norm_target:
                containment_score = 0.90 + (min(len(norm_target), len(norm_raw)) / max(len(norm_target), len(norm_raw))) * 0.08
                if containment_score > best_score:
                    best_score = round(containment_score, 4)
                    best_match = cname

            sim = self.similarity_score(norm_raw, norm_target)
            if sim > best_score:
                best_score = sim
                best_match = cname

        # Also test against aliases
        for norm_alias, cname in self.alias_map.items():
            sim = self.similarity_score(norm_raw, norm_alias)
            if sim > best_score:
                best_score = sim
                best_match = cname

        # Confidence Threshold
        if best_match and best_score >= 0.82:
            self.mapping_log.append(MappingLogEntry(
                raw_name=clean_raw,
                canonical_name=best_match,
                confidence_score=best_score,
                resolution_method="FUZZY_STRING",
                matched_entity=best_match,
                resolved_at=now_iso
            ))
            return best_match, best_score, "FUZZY_STRING"

        # 5. Clean Fallback for unknown entities (title-cased normalized string)
        # E.g. "Datadog, Inc." -> "Datadog"
        clean_name = re.sub(r'[\s,]+', ' ', clean_raw).strip()
        for suffix_pat in self.LEGAL_SUFFIXES:
            clean_name = re.sub(suffix_pat, '', clean_name, flags=re.IGNORECASE).strip(' ,.')
        canonical_fallback = clean_name.strip() or clean_raw

        self.mapping_log.append(MappingLogEntry(
            raw_name=clean_raw,
            canonical_name=canonical_fallback,
            confidence_score=0.75,
            resolution_method="CLEAN_SYNTAX_FALLBACK",
            matched_entity="NONE",
            resolved_at=now_iso
        ))
        return canonical_fallback, 0.75, "CLEAN_SYNTAX_FALLBACK"

    def get_mapping_log(self) -> List[MappingLogEntry]:
        """Returns the complete audit log of entity mappings."""
        return self.mapping_log

