"""Unit tests for Stage 4 (Cleaning, +03:30 Timestamp, Reconciliation) & Stage 5 (ASOF JOIN, OHLCV, Option Chain)."""
import sqlite3
from pathlib import Path

from src.config import Settings
from src.stage1_discovery import OptionDiscoveryService
from src.stage2_3_crawler_storage import RawStorageManager, TsetmcCrawler
from src.stage4_cleaning import (
    ReconciliationEngine,
    TickCleaner,
    parse_tsetmc_timestamp,
)
from src.stage5_series import (
    build_matched_option_ticks,
    build_ohlcv_candles,
    build_option_chain,
    classify_moneyness,
)


def _setup_pipeline_to_stage4(tmp_path: Path) -> Settings:
    settings = Settings(
        tsetmc_use_fixtures=True,
        tsetmc_max_rps=1000.0,
        tsetmc_max_retries=2,
        tsetmc_start_date=20230321,
        tsetmc_respect_trading_hours=False,
        data_dir=tmp_path / "data",
        raw_dir=tmp_path / "data/raw",
        processed_dir=tmp_path / "data/processed",
        fixtures_dir=tmp_path / "data/fixtures",
        state_db_path=tmp_path / "data/state.sqlite",
    )
    discovery = OptionDiscoveryService(settings)
    instruments = discovery.discover_all(reference_date=20261108)
    storage = RawStorageManager(settings)
    crawler = TsetmcCrawler(settings=settings, storage=storage, sleep_fn=lambda _: None)
    crawler.crawl_all([r.ins_code for r in instruments])
    cleaner = TickCleaner(settings=settings, storage=storage)
    cleaner.clean_all()
    return settings


def test_parse_tsetmc_timestamp_no_dst_summer_and_winter() -> None:
    # Summer date in 1402 SH: May 24, 2023 at 09:00:05 -> must use fixed +03:30 (NEVER +04:30 DST!)
    ts_teh_sum, ts_utc_sum, epoch_sum = parse_tsetmc_timestamp(20230524, 90005)
    assert ts_teh_sum == "2023-05-24T09:00:05+03:30"
    assert ts_utc_sum == "2023-05-24T05:30:05Z"
    assert epoch_sum == 1684906205

    # Autumn/Winter date: Nov 7, 2026 at 12:29:52 -> fixed +03:30
    ts_teh_win, ts_utc_win, epoch_win = parse_tsetmc_timestamp(20261107, 122952)
    assert ts_teh_win == "2026-11-07T12:29:52+03:30"
    assert ts_utc_win == "2026-11-07T08:59:52Z"
    assert epoch_win == 1794041992

    # Zero hEven -> 00:00:00+03:30
    ts_teh_zero, ts_utc_zero, _ = parse_tsetmc_timestamp(20261105, 0)
    assert ts_teh_zero == "2026-11-05T00:00:00+03:30"
    assert ts_utc_zero == "2026-11-04T20:30:00Z"


def test_tick_cleaner_injection_canceled_filtering_and_intra_second_sorting(
    tmp_path: Path,
) -> None:
    settings = _setup_pipeline_to_stage4(tmp_path)
    cleaner = TickCleaner(settings=settings)
    folad = "46348559193224090"

    # On 20261107, raw فولاد ticks have:
    # nTran=3 @ hEven=90010 BEFORE nTran=2 @ hEven=90010 in raw JSON, plus nTran=5 canceled=1
    valid_ticks = cleaner.get_clean_ticks(folad, d_even=20261107, include_canceled=False)
    all_ticks = cleaner.get_clean_ticks(folad, d_even=20261107, include_canceled=True)
    canceled_ticks = cleaner.get_canceled_ticks(folad, d_even=20261107)

    assert len(all_ticks) == 6
    assert len(valid_ticks) == 5
    assert len(canceled_ticks) == 1
    assert canceled_ticks[0]["n_tran"] == 5
    assert canceled_ticks[0]["canceled"] == 1

    # Verify insCode and dEven were injected (replacing None and 0)
    for t in all_ticks:
        assert t["ins_code"] == folad
        assert t["insCode"] == folad
        assert t["d_even"] == 20261107
        assert t["dEven"] == 20261107
        assert t["ts_tehran"].endswith("+03:30")

    # Verify deterministic intra-second sorting: (dEven ASC, hEven ASC, nTran ASC)
    assert [t["n_tran"] for t in valid_ticks] == [1, 2, 3, 4, 6]
    same_second = [t for t in valid_ticks if t["h_even"] == 90010]
    assert len(same_second) == 2
    assert same_second[0]["n_tran"] == 2
    assert same_second[0]["p_tran"] == 4400.0
    assert same_second[1]["n_tran"] == 3
    assert same_second[1]["p_tran"] == 4410.0


def test_reconciliation_engine_98_pct_target_and_anomaly_detection(
    tmp_path: Path,
) -> None:
    settings = _setup_pipeline_to_stage4(tmp_path)
    engine = ReconciliationEngine(settings=settings)

    report = engine.reconcile()
    assert report["total_traded_days"] == 12
    assert report["matched_days"] == 12
    assert report["mismatched_days"] == 0
    assert report["missing_days"] == 0
    assert report["match_rate_pct"] == 100.0
    assert report["meets_98_pct_target"] is True

    # Verify canceled trades were tracked without breaking reconciliation
    folad_20261107 = next(
        r
        for r in report["rows"]
        if r["ins_code"] == "46348559193224090" and r["d_even"] == 20261107
    )
    assert folad_20261107["status"] == "MATCH"
    assert folad_20261107["daily_trade_count"] == 5
    assert folad_20261107["tick_valid_count"] == 5
    assert folad_20261107["tick_canceled_count"] == 1
    assert folad_20261107["daily_volume"] == 7700.0
    assert folad_20261107["tick_valid_volume"] == 7700.0

    # Simulate a volume/count MISMATCH on one day and MISSING_TICKS on another day
    with sqlite3.connect(settings.state_db_path) as conn:
        # Corrupt one valid tick volume on 90000000000000004 (20261107)
        conn.execute(
            """
            UPDATE clean_ticks
            SET q_tit_tran = 999.0
            WHERE ins_code = '90000000000000004' AND d_even = 20261107 AND n_tran = 1
            """
        )
        # Delete ticks for 90000000000000006 (20230524) to trigger MISSING_TICKS
        conn.execute(
            """
            DELETE FROM clean_ticks
            WHERE ins_code = '90000000000000006' AND d_even = 20230524
            """
        )
        conn.commit()

    report_after = engine.reconcile()
    assert report_after["total_traded_days"] == 12
    assert report_after["matched_days"] == 10
    assert report_after["mismatched_days"] == 1
    assert report_after["missing_days"] == 1
    assert report_after["meets_98_pct_target"] is False

    status_by_key = {
        (r["ins_code"], r["d_even"]): r["status"] for r in report_after["rows"]
    }
    assert status_by_key[("90000000000000004", 20261107)] == "MISMATCH"
    assert status_by_key[("90000000000000006", 20230524)] == "MISSING_TICKS"


def test_stage5_asof_join_matched_option_ticks_no_future_leak(tmp_path: Path) -> None:
    settings = _setup_pipeline_to_stage4(tmp_path)
    matched = build_matched_option_ticks(settings=settings)
    assert len(matched) == 16  # Total valid option ticks across all 6 option contracts
    assert (settings.processed_dir / "option_ticks_matched.jsonl").is_file()

    # Check every matched option tick strictly satisfies ts_underlying <= ts_option
    for row in matched:
        assert row["underlying_price"] is not None
        assert row["underlying_ts_epoch"] <= row["ts_epoch"]
        assert row["moneyness_status"] in ("ITM", "ATM", "OTM")

    # Verify exact ASOF matching for ضفلا1100 (90000000000000001) on 20261107:
    # Underlying فولاد valid trades on 20261107:
    #   09:00:02 (n=1, p=4390), 09:00:10 (n=2, p=4400), 09:00:10 (n=3, p=4410),
    #   09:30:45 (n=4, p=4420), [11:00:00 canceled @ 4450], 12:29:52 (n=6, p=4410)
    opt_c_20261107 = [
        r
        for r in matched
        if r["ins_code"] == "90000000000000001" and r["d_even"] == 20261107
    ]
    assert [r["n_tran"] for r in opt_c_20261107] == [1, 2, 3, 5]
    # Option ticks at 09:00:20 (n=1, n=2) must match underlying 09:00:10 (n=3 @ 4410.0)
    assert opt_c_20261107[0]["underlying_price"] == 4410.0
    assert opt_c_20261107[0]["underlying_n_tran"] == 3
    assert opt_c_20261107[1]["underlying_price"] == 4410.0
    # Option tick at 09:35:00 (n=3) must match underlying 09:30:45 (n=4 @ 4420.0)
    # and MUST NOT leak future 12:29:52 trade or canceled 11:00:00 (4450.0) trade!
    assert opt_c_20261107[2]["underlying_price"] == 4420.0
    assert opt_c_20261107[2]["underlying_n_tran"] == 4
    # Option tick at 12:29:55 (n=5) must match underlying 12:29:52 (n=6 @ 4410.0)
    assert opt_c_20261107[3]["underlying_price"] == 4410.0
    assert opt_c_20261107[3]["underlying_n_tran"] == 6


def test_stage5_multi_timeframe_ohlcv_candles_and_sparse_ffill(tmp_path: Path) -> None:
    settings = _setup_pipeline_to_stage4(tmp_path)
    candles_by_tf = build_ohlcv_candles(settings=settings)

    for tf in ("1m", "5m", "15m", "1h", "1d"):
        assert tf in candles_by_tf
        assert len(candles_by_tf[tf]) > 0
        assert (settings.processed_dir / f"ohlcv_{tf}.jsonl").is_file()

    # Inspect 1m candles for فولاد (46348559193224090) on 20230524:
    # Valid trades at 09:00:05 (n=1 @ 4100 vol 1000, n=2 @ 4120 vol 1500) and 09:15:20 (n=3 @ 4150 vol 2500).
    # That spans 09:00 to 09:15 inclusive = 16 one-minute buckets (2 active + 14 sparse).
    folad_1m = [
        c
        for c in candles_by_tf["1m"]
        if c["ins_code"] == "46348559193224090" and c["d_even"] == 20230524
    ]
    assert len(folad_1m) == 16

    first_bar = folad_1m[0]
    assert first_bar["bucket_ts_tehran"] == "2023-05-24T09:00:00+03:30"
    assert first_bar["open"] == 4100.0
    assert first_bar["high"] == 4120.0
    assert first_bar["low"] == 4100.0
    assert first_bar["close"] == 4120.0
    assert first_bar["close_ffill"] == 4120.0
    assert first_bar["volume"] == 2500.0
    assert first_bar["trade_count"] == 2
    assert first_bar["is_sparse"] == 0

    # Minutes 09:01 through 09:14 are sparse buckets with volume == 0, is_sparse == 1, close_ffill == 4120.0
    for sparse_bar in folad_1m[1:-1]:
        assert sparse_bar["is_sparse"] == 1
        assert sparse_bar["volume"] == 0.0
        assert sparse_bar["trade_count"] == 0
        assert sparse_bar["open"] == 4120.0
        assert sparse_bar["high"] == 4120.0
        assert sparse_bar["low"] == 4120.0
        assert sparse_bar["close"] == 4120.0
        assert sparse_bar["close_ffill"] == 4120.0

    last_bar = folad_1m[-1]
    assert last_bar["bucket_ts_tehran"] == "2023-05-24T09:15:00+03:30"
    assert last_bar["open"] == 4150.0
    assert last_bar["close"] == 4150.0
    assert last_bar["close_ffill"] == 4150.0
    assert last_bar["volume"] == 2500.0
    assert last_bar["trade_count"] == 1
    assert last_bar["is_sparse"] == 0

    # Verify 1d candles for فولاد exclude pre-1402 (20230315) and mark zero-trade day 20261105 as sparse
    folad_1d = [
        c for c in candles_by_tf["1d"] if c["ins_code"] == "46348559193224090"
    ]
    assert [c["d_even"] for c in folad_1d] == [20230524, 20261104, 20261105, 20261107]
    sparse_day = next(c for c in folad_1d if c["d_even"] == 20261105)
    assert sparse_day["is_sparse"] == 1
    assert sparse_day["volume"] == 0.0
    assert sparse_day["close_ffill"] == 4290.0


def test_stage5_option_chain_builder_dte_pairing_and_moneyness(tmp_path: Path) -> None:
    settings = _setup_pipeline_to_stage4(tmp_path)
    folad = "46348559193224090"

    # 1. Option chain on 20261107 (underlying price = 4410.0)
    chain_20261107 = build_option_chain(
        ua_ins_code=folad, d_even=20261107, settings=settings, include_expired=True
    )
    assert len(chain_20261107) == 2

    # First row: expired 1402 pair (endDate=20230809, strike=4000.0)
    row_exp = chain_20261107[0]
    assert row_exp["end_date"] == 20230809
    assert row_exp["strike_price"] == 4000.0
    assert row_exp["dte"] == 0
    assert row_exp["underlying_price"] == 4410.0
    assert row_exp["call_symbol"] == "ضفلا0205"
    assert row_exp["put_symbol"] == "طفلا0205"
    assert row_exp["call_moneyness"] == "ITM"
    assert row_exp["put_moneyness"] == "OTM"

    # Second row: active pair (endDate=20261221, strike=4500.0)
    # DTE from 2026-11-07 to 2026-12-21 is 44 days.
    # Relative diff = |4410 - 4500| / 4500 = 0.02 <= 0.02 -> ATM
    row_act = chain_20261107[1]
    assert row_act["end_date"] == 20261221
    assert row_act["strike_price"] == 4500.0
    assert row_act["dte"] == 44
    assert row_act["underlying_price"] == 4410.0
    assert row_act["call_ins_code"] == "90000000000000001"
    assert row_act["put_ins_code"] == "90000000000000002"
    assert row_act["call_symbol"] == "ضفلا1100"
    assert row_act["put_symbol"] == "طفلا1100"
    assert row_act["call_close"] == 329.0
    assert row_act["call_volume"] == 85.0
    assert row_act["call_bid"] == 320.0
    assert row_act["call_ask"] == 335.0
    assert row_act["put_close"] == 188.0
    assert row_act["put_volume"] == 20.0
    assert row_act["put_bid"] == 180.0
    assert row_act["put_ask"] == 195.0
    assert row_act["call_moneyness"] == "ATM"
    assert row_act["put_moneyness"] == "ATM"

    # 2. Historical option chain on 20230524 (underlying last price = 4150.0)
    # DTE from 2023-05-24 to 2023-08-09 is 77 days
    chain_20230524 = build_option_chain(
        ua_ins_code=folad, d_even=20230524, settings=settings, include_expired=False
    )
    row_2023 = next(r for r in chain_20230524 if r["end_date"] == 20230809)
    assert row_2023["dte"] == 77
    assert row_2023["underlying_price"] == 4150.0
    assert row_2023["call_moneyness"] == "ITM"
    assert row_2023["put_moneyness"] == "OTM"

    # Direct moneyness classification checks
    assert classify_moneyness("call", 4500.0, 4000.0) == "ITM"
    assert classify_moneyness("put", 4500.0, 4000.0) == "OTM"
    assert classify_moneyness("call", 3800.0, 4000.0) == "OTM"
    assert classify_moneyness("put", 3800.0, 4000.0) == "ITM"
    assert classify_moneyness("call", 4050.0, 4000.0) == "ATM"
