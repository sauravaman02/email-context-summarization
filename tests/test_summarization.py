"""Tests for summarisation logic: date validation, cache behavior, key generation."""

import uuid
from datetime import datetime, timezone

import pytest

from app.services.summarization_service import SummarizationService


class TestDateRangeValidation:
    def test_valid_range(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 12, 31, tzinfo=timezone.utc)
        SummarizationService._validate_date_range(start, end)

    def test_invalid_range_raises(self):
        start = datetime(2025, 12, 31, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="start_date.*must be before"):
            SummarizationService._validate_date_range(start, end)

    def test_none_dates_pass(self):
        SummarizationService._validate_date_range(None, None)

    def test_only_start_passes(self):
        SummarizationService._validate_date_range(
            datetime(2025, 1, 1, tzinfo=timezone.utc), None
        )

    def test_only_end_passes(self):
        SummarizationService._validate_date_range(
            None, datetime(2025, 12, 31, tzinfo=timezone.utc)
        )

    def test_same_date_passes(self):
        dt = datetime(2025, 6, 15, tzinfo=timezone.utc)
        SummarizationService._validate_date_range(dt, dt)


class TestCacheKeyGeneration:
    def test_key_format(self):
        from app.services.cache_service import cache

        key = cache.make_summary_key("abc-123", "2025-01-01", "2025-12-31")
        assert key == "summary:abc-123:2025-01-01:2025-12-31"

    def test_none_dates(self):
        from app.services.cache_service import cache

        key = cache.make_summary_key("abc-123")
        assert key == "summary:abc-123:none:none"


class TestCacheTTL:
    def test_set_and_get(self):
        from app.services.cache_service import TTLCache

        c = TTLCache(default_ttl=60)
        c.set("k1", "value1")
        assert c.get("k1") == "value1"

    def test_expired_returns_none(self):
        from app.services.cache_service import TTLCache
        import time

        c = TTLCache(default_ttl=1)
        c.set("k1", "value1", ttl=1)
        time.sleep(1.1)
        assert c.get("k1") is None

    def test_delete(self):
        from app.services.cache_service import TTLCache

        c = TTLCache(default_ttl=60)
        c.set("k1", "value1")
        c.delete("k1")
        assert c.get("k1") is None

    def test_clear(self):
        from app.services.cache_service import TTLCache

        c = TTLCache(default_ttl=60)
        c.set("k1", "v1")
        c.set("k2", "v2")
        c.clear()
        assert c.get("k1") is None
        assert c.get("k2") is None
