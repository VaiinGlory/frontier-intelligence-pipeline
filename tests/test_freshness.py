"""
Unit Tests for Freshness & Temporal Normalization Engine
"""

from datetime import datetime, timezone, timedelta
import pytest
from src.freshness.normalizer import DateNormalizer

def test_relative_date_parsing():
    normalizer = DateNormalizer()
    ref_time = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # 2 hours ago
    dt_2h = normalizer.parse_date("2 hours ago", reference_time=ref_time)
    assert dt_2h == datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    assert normalizer.is_within_24_hours(dt_2h, reference_time=ref_time) is True

    # 45 minutes ago
    dt_45m = normalizer.parse_date("45 minutes ago", reference_time=ref_time)
    assert dt_45m == datetime(2026, 11, 22, 11, 15, 0, tzinfo=timezone.utc)
    assert normalizer.is_within_24_hours(dt_45m, reference_time=ref_time) is True

    # Yesterday
    dt_yest = normalizer.parse_date("yesterday", reference_time=ref_time)
    assert dt_yest == datetime(2026, 11, 21, 12, 0, 0, tzinfo=timezone.utc)
    assert normalizer.is_within_24_hours(dt_yest, reference_time=ref_time) is True

    # 3 days ago (Stale > 24 hours)
    dt_3d = normalizer.parse_date("3 days ago", reference_time=ref_time)
    assert normalizer.is_within_24_hours(dt_3d, reference_time=ref_time) is False

def test_iso_and_rfc_formats():
    normalizer = DateNormalizer()
    ref_time = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)

    # RFC 2822
    rfc_date = "Sun, 22 Nov 2026 08:30:00 +0000"
    dt_rfc = normalizer.parse_date(rfc_date, reference_time=ref_time)
    assert dt_rfc is not None
    assert normalizer.is_within_24_hours(dt_rfc, reference_time=ref_time) is True

    # Epoch timestamp in seconds
    epoch_now = int(ref_time.timestamp()) - 3600  # 1 hour ago
    dt_epoch = normalizer.parse_date(str(epoch_now))
    assert normalizer.is_within_24_hours(dt_epoch, reference_time=ref_time) is True

def test_heuristic_fingerprinting():
    normalizer = DateNormalizer()
    url = "https://techcorp.ai/announcement-without-date"
    content = "We have launched our new reasoning model v1."

    # First encounter -> True (fresh)
    is_fresh, dt = normalizer.evaluate_freshness_heuristic(content, url)
    assert is_fresh is True
    assert dt is not None

    # Second encounter -> False (duplicate/stale)
    is_fresh_second, _ = normalizer.evaluate_freshness_heuristic(content, url)
    assert is_fresh_second is False
