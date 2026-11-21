"""
FrontierAtlas Data Intelligence Pipeline
Freshness & Temporal Normalization Engine
"""
from datetime import datetime, timezone, timedelta
import re
import hashlib
from typing import Optional, Tuple

class DateNormalizer:
    """
    Normalizes messy and heterogeneous publication dates into canonical ISO-8601 UTC timestamps.
    Handles relative dates, RFC formats, missing meta tags, and provides intelligent content hashing heuristics.
    """

    RELATIVE_PATTERNS = [
        (re.compile(r'(\d+)\s*(?:sec|second)s?\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(seconds=int(m.group(1)))),
        (re.compile(r'(\d+)\s*(?:min|minute)s?\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(minutes=int(m.group(1)))),
        (re.compile(r'(\d+)\s*(?:hr|hour)s?\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(hours=int(m.group(1)))),
        (re.compile(r'(\d+)h\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(hours=int(m.group(1)))),
        (re.compile(r'(\d+)m\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(minutes=int(m.group(1)))),
        (re.compile(r'(\d+)\s*(?:day)s?\s*ago', re.IGNORECASE), lambda m, now: now - timedelta(days=int(m.group(1)))),
        (re.compile(r'yesterday', re.IGNORECASE), lambda m, now: now - timedelta(days=1)),
        (re.compile(r'just now', re.IGNORECASE), lambda m, now: now),
        (re.compile(r'today', re.IGNORECASE), lambda m, now: now),
    ]

    DATE_FORMATS = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %Z",
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
    ]

    def __init__(self, seen_cache: Optional[set] = None):
        self.seen_cache = seen_cache if seen_cache is not None else set()

    def parse_date(self, raw_date_str: Optional[str], reference_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parses a date string into an aware UTC datetime object.
        """
        if not raw_date_str:
            return None

        clean_str = str(raw_date_str).strip()
        now = reference_time or datetime.now(timezone.utc)

        # 1. Check relative date regexes
        for pattern, handler in self.RELATIVE_PATTERNS:
            match = pattern.search(clean_str)
            if match:
                dt = handler(match, now)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)

        # 2. Check numeric epoch timestamps
        if clean_str.isdigit():
            val = int(clean_str)
            if val > 1e11:  # Milliseconds
                val /= 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)

        # 3. Strip GMT/UTC suffixes for standard format matching if needed
        normalized_str = re.sub(r'\s+GMT$', ' +0000', clean_str)
        normalized_str = re.sub(r'\s+UTC$', ' +0000', normalized_str)

        for fmt in self.DATE_FORMATS:
            try:
                dt = datetime.strptime(normalized_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue

        # 4. Fallback: ISO format direct parse
        try:
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

        return None

    def to_iso8601(self, dt: Optional[datetime]) -> Optional[str]:
        """Converts datetime to strict ISO-8601 string (e.g. 2026-11-21T18:00:00Z)."""
        if not dt:
            return None
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_within_24_hours(self, dt: Optional[datetime], reference_time: Optional[datetime] = None) -> bool:
        """Determines if a given datetime is within the past 24 hours."""
        if not dt:
            return False
        now = reference_time or datetime.now(timezone.utc)
        earliest_allowed = now - timedelta(hours=24)
        # Allow up to 5 minutes into future to account for clock skew
        latest_allowed = now + timedelta(minutes=5)
        return earliest_allowed <= dt <= latest_allowed

    def evaluate_freshness_heuristic(self, content: str, url: str, reference_time: Optional[datetime] = None) -> Tuple[bool, datetime]:
        """
        Intelligent Heuristic for sources lacking explicit publication dates.
        Generates a composite content hash (SHA-256 of text + url structure)
        and determines if the content is newly discovered since the last run.
        """
        now = reference_time or datetime.now(timezone.utc)
        content_fingerprint = hashlib.sha256(f"{url}::{content.strip()}".encode('utf-8')).hexdigest()

        if content_fingerprint not in self.seen_cache:
            self.seen_cache.add(content_fingerprint)
            return True, now  # Identified as fresh new signal
        return False, now  # Stale, duplicate from prior run
