"""Unit tests for Stage 2 (Fault-Tolerant Resumable Crawler) & Stage 3 (Immutable .json.gz Raw Storage)."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from src.config import Settings
from src.stage1_discovery import OptionDiscoveryService
from src.stage2_3_crawler_storage import (
    CrawlerBannedError,
    RawStorageManager,
    TradingHoursPauseError,
    TsetmcCrawler,
    is_tehran_trading_hours,
)


def _make_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        tsetmc_use_fixtures=True,
        tsetmc_max_rps=1000.0,
        tsetmc_max_retries=3,
        tsetmc_start_date=20230321,
        tsetmc_respect_trading_hours=True,
        data_dir=tmp_path / "data",
        raw_dir=tmp_path / "data/raw",
        processed_dir=tmp_path / "data/processed",
        fixtures_dir=tmp_path / "data/fixtures",
        state_db_path=tmp_path / "data/state.sqlite",
    )


def test_stage3_immutable_raw_storage_and_manifest(tmp_path: Path) -> None:
    settings = _make_test_settings(tmp_path)
    storage = RawStorageManager(settings)

    raw_daily = {
        "closingPriceDaily": [
            {"insCode": "46348559193224090", "dEven": 20261107, "zTotTran": 5.0}
        ]
    }
    daily_entry = storage.save_daily_raw("46348559193224090", raw_daily, http_status=200)
    expected_daily_path = settings.raw_dir / "daily" / "46348559193224090.json.gz"
    assert expected_daily_path.is_file()
    assert daily_entry["compressed_bytes"] > 0
    assert daily_entry["raw_record_count"] == 1
    assert daily_entry["http_status"] == 200
    assert storage.has_artifact("daily:46348559193224090")
    assert storage.read_daily_raw("46348559193224090") == raw_daily

    # Raw tick payload with TSETMC quirk: insCode=None, dEven=0
    raw_ticks = {
        "tradeHistory": [
            {"insCode": None, "dEven": 0, "nTran": 1, "hEven": 90002, "qTitTran": 1200, "pTran": 4390.0, "canceled": 0},
            {"insCode": None, "dEven": 0, "nTran": 2, "hEven": 90010, "qTitTran": 900, "pTran": 4450.0, "canceled": 1},
        ]
    }
    tick_entry = storage.save_ticks_raw("46348559193224090", 20261107, raw_ticks, http_status=200)
    expected_tick_path = settings.raw_dir / "ticks" / "46348559193224090" / "20261107.json.gz"
    assert expected_tick_path.is_file()
    assert tick_entry["compressed_bytes"] > 0
    assert tick_entry["raw_record_count"] == 2
    assert storage.has_artifact("ticks:46348559193224090:20261107")

    loaded_ticks = storage.read_ticks_raw("46348559193224090", 20261107)
    assert loaded_ticks == raw_ticks
    assert loaded_ticks["tradeHistory"][0]["insCode"] is None
    assert loaded_ticks["tradeHistory"][0]["dEven"] == 0

    manifest = storage.list_manifest()
    assert len(manifest) == 2


def test_stage2_crawler_filtering_and_resumability(tmp_path: Path) -> None:
    settings = _make_test_settings(tmp_path)
    discovery = OptionDiscoveryService(settings)
    instruments = discovery.discover_all(reference_date=20261108)
    assert len(instruments) == 31

    storage = RawStorageManager(settings)
    crawler = TsetmcCrawler(settings=settings, storage=storage, sleep_fn=lambda _: None)

    summary_1 = crawler.crawl_all([r.ins_code for r in instruments])
    assert summary_1["instruments_processed"] == 31
    assert summary_1["daily_fetched"] == 31
    # Traded days >= 20230321 with zTotTran > 0 across our fixture instruments:
    # فولاد (3 days: 20230524, 20261104, 20261107; skips 20230315 < 20230321 and 20261105 zTotTran=0)
    # فملی (2 days: 20261104, 20261107)
    # ضفلا1100 (2 days: 20261104, 20261107; skips 20261105 zTotTran=0)
    # طفلا1100 (1 day: 20261107)
    # ضفمل1200 (1 day: 20261107)
    # طفمل1200 (1 day: 20261107)
    # ضفلا0205 (1 day: 20230524)
    # طفلا0205 (1 day: 20230524)
    # Total eligible tick days = 12
    assert summary_1["ticks_fetched"] == 12
    assert summary_1["ticks_skipped_checkpoint"] == 0

    # Verify pre-1402 day (20230315) and zero-trade day (20261105) were NOT crawled
    assert not storage.has_artifact("ticks:46348559193224090:20230315")
    assert not storage.has_artifact("ticks:46348559193224090:20261105")
    assert storage.has_artifact("ticks:46348559193224090:20230524")
    assert storage.has_artifact("ticks:46348559193224090:20261107")

    fetches_after_run1 = crawler.fetch_count
    assert fetches_after_run1 == 31 + 12

    # Second run: 100% resumable from checkpoint, 0 new HTTP/fixture fetches!
    summary_2 = crawler.crawl_all([r.ins_code for r in instruments])
    assert summary_2["daily_fetched"] == 0
    assert summary_2["ticks_fetched"] == 0
    assert summary_2["ticks_skipped_checkpoint"] == 12
    assert crawler.fetch_count == fetches_after_run1


def test_crawler_exponential_backoff_and_http_403_ban(tmp_path: Path) -> None:
    settings = _make_test_settings(tmp_path)
    sleeps: List[float] = []
    attempts = {"count": 0}

    def flaky_fetcher(endpoint: str) -> Tuple[int, Dict[str, Any]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 429, {}
        if attempts["count"] == 2:
            return 503, {}
        return 200, {"closingPriceDaily": []}

    crawler = TsetmcCrawler(
        settings=settings,
        fetcher=flaky_fetcher,
        sleep_fn=lambda s: sleeps.append(s),
    )
    status, payload = crawler.fetch_with_retry("/ClosingPrice/GetClosingPriceDailyList/46348559193224090/0")
    assert status == 200
    assert payload == {"closingPriceDaily": []}
    assert attempts["count"] == 3
    assert any(s >= 0.5 for s in sleeps)

    # HTTP 403 must immediately raise CrawlerBannedError without retrying
    ban_attempts = {"count": 0}

    def banned_fetcher(endpoint: str) -> Tuple[int, Dict[str, Any]]:
        ban_attempts["count"] += 1
        return 403, {}

    banned_crawler = TsetmcCrawler(
        settings=settings,
        fetcher=banned_fetcher,
        sleep_fn=lambda _: None,
    )
    with pytest.raises(CrawlerBannedError):
        banned_crawler.fetch_with_retry("/ClosingPrice/GetClosingPriceDailyList/46348559193224090/0")
    assert ban_attempts["count"] == 1


def test_tehran_trading_hours_guard(tmp_path: Path) -> None:
    # Monday 2026-11-09 06:30 UTC == 10:00 +03:30 (Inside Sat-Wed 09:00-12:30 Tehran trading hours)
    dt_inside = datetime(2026, 11, 9, 6, 30, 0, tzinfo=timezone.utc)
    assert is_tehran_trading_hours(dt_inside) is True

    # Monday 2026-11-09 10:00 UTC == 13:30 +03:30 (After 12:30 market close)
    dt_after = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)
    assert is_tehran_trading_hours(dt_after) is False

    # Thursday 2026-11-05 06:30 UTC == 10:00 +03:30 Thursday (Market closed on Thu/Fri)
    dt_thursday = datetime(2026, 11, 5, 6, 30, 0, tzinfo=timezone.utc)
    assert is_tehran_trading_hours(dt_thursday) is False

    settings = _make_test_settings(tmp_path)
    crawler = TsetmcCrawler(
        settings=settings,
        now_utc_fn=lambda: dt_inside,
        sleep_fn=lambda _: None,
    )
    with pytest.raises(TradingHoursPauseError):
        crawler.crawl_instrument("46348559193224090", pause_on_trading_hours=True)
