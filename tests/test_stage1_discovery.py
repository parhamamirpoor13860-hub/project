"""Unit tests for Stage 1 (Option & Underlying Asset Discovery, Fixtures, and SQLite Registry)."""
import json
from pathlib import Path

from src.config import Settings
from src.fixtures import UNDERLYING_ASSETS_25, generate_fixtures
from src.models import (
    ClosingPriceDailyResponse,
    InstrumentInfoResponse,
    InstrumentSearchResponse,
    OptionMarketWatchResponse,
    TradeHistoryResponse,
)
from src.stage1_discovery import OptionDiscoveryService, parse_option_lval30


def test_fixtures_match_tsetmc_api_schemas(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "fixtures"
    written = generate_fixtures(fixtures_dir)
    assert len(written) == 5

    # 1. option_market_watch.json
    omw_raw = json.loads((fixtures_dir / "option_market_watch.json").read_text(encoding="utf-8"))
    omw = OptionMarketWatchResponse.parse_obj(omw_raw)
    assert len(omw.instrumentOptMarketWatch) == 2
    folad_pair = omw.instrumentOptMarketWatch[0]
    assert folad_pair.insCode_C == "90000000000000001"
    assert folad_pair.insCode_P == "90000000000000002"
    assert folad_pair.uaInsCode == "46348559193224090"
    assert folad_pair.strikePrice == 4500.0
    assert folad_pair.endDate == 20261221
    assert folad_pair.contractSize == 1000

    # 2. instrument_search.json
    search_raw = json.loads((fixtures_dir / "instrument_search.json").read_text(encoding="utf-8"))
    search_resp = InstrumentSearchResponse.parse_obj(search_raw)
    assert len(search_resp.instrumentSearch) == 25 + 6

    # 3. instrument_info.json
    info_raw = json.loads((fixtures_dir / "instrument_info.json").read_text(encoding="utf-8"))
    assert "46348559193224090" in info_raw
    assert "90000000000000005" in info_raw
    folad_info = InstrumentInfoResponse.parse_obj(info_raw["46348559193224090"])
    assert folad_info.instrumentInfo.lVal18AFC == "فولاد"
    exp_call_info = InstrumentInfoResponse.parse_obj(info_raw["90000000000000005"])
    assert exp_call_info.instrumentInfo.lVal30 == "اختيارخ فولاد-4000-20230809"

    # 4. closing_price_daily.json & 5. trade_history.json reconciliation check
    daily_raw = json.loads((fixtures_dir / "closing_price_daily.json").read_text(encoding="utf-8"))
    trades_raw = json.loads((fixtures_dir / "trade_history.json").read_text(encoding="utf-8"))

    for ins_code, payload in daily_raw.items():
        daily_resp = ClosingPriceDailyResponse.parse_obj(payload)
        for day in daily_resp.closingPriceDaily:
            if day.dEven >= 20230321 and day.zTotTran > 0:
                key = f"{ins_code}_{day.dEven}"
                assert key in trades_raw
                th_resp = TradeHistoryResponse.parse_obj(trades_raw[key])
                for t in th_resp.tradeHistory:
                    assert t.insCode is None
                    assert t.dEven == 0
                valid_ticks = [t for t in th_resp.tradeHistory if t.canceled == 0]
                assert len(valid_ticks) == int(day.zTotTran)
                assert sum(t.qTitTran for t in valid_ticks) == day.qTotTran5J


def test_parse_option_lval30() -> None:
    inst_type, ua_hint, strike, end_date = parse_option_lval30(
        "اختيارخ فولاد-4500-20261221", "ضفلا1100"
    )
    assert inst_type == "call"
    assert ua_hint == "فولاد"
    assert strike == 4500.0
    assert end_date == 20261221

    inst_type_p, ua_hint_p, strike_p, end_date_p = parse_option_lval30(
        "اختيارف فولاد-4000-20230809", "طفلا0205"
    )
    assert inst_type_p == "put"
    assert ua_hint_p == "فولاد"
    assert strike_p == 4000.0
    assert end_date_p == 20230809


def test_stage1_discovery_and_sqlite_registry(tmp_path: Path) -> None:
    settings = Settings(
        tsetmc_use_fixtures=True,
        data_dir=tmp_path / "data",
        raw_dir=tmp_path / "data/raw",
        processed_dir=tmp_path / "data/processed",
        fixtures_dir=tmp_path / "data/fixtures",
        state_db_path=tmp_path / "data/state.sqlite",
    )
    service = OptionDiscoveryService(settings=settings)
    records = service.discover_all(reference_date=20261108)

    # 25 underlyings + 4 active options + 2 expired options = 31 total instruments
    assert len(records) == 31

    underlyings = service.list_instruments(instrument_type="underlying")
    assert len(underlyings) == 25
    expected_symbols = {ua["lVal18AFC"] for ua in UNDERLYING_ASSETS_25}
    assert {u.symbol for u in underlyings} == expected_symbols

    calls = service.list_instruments(instrument_type="call")
    puts = service.list_instruments(instrument_type="put")
    assert len(calls) == 3
    assert len(puts) == 3

    # Verify active vs expired options
    active_opts = [
        r for r in service.list_instruments(is_expired=False) if r.instrument_type in ("call", "put")
    ]
    expired_opts = service.list_instruments(is_expired=True)
    assert len(active_opts) == 4
    assert len(expired_opts) == 2

    # Check specific active Call on فولاد
    active_call = service.get_instrument("90000000000000001")
    assert active_call is not None
    assert active_call.symbol == "ضفلا1100"
    assert active_call.instrument_type == "call"
    assert active_call.ua_ins_code == "46348559193224090"
    assert active_call.strike_price == 4500.0
    assert active_call.end_date == 20261221
    assert active_call.contract_size == 1000
    assert active_call.is_expired is False

    # Check specific expired Put on فولاد from 1402
    expired_put = service.get_instrument("90000000000000006")
    assert expired_put is not None
    assert expired_put.symbol == "طفلا0205"
    assert expired_put.instrument_type == "put"
    assert expired_put.ua_ins_code == "46348559193224090"
    assert expired_put.strike_price == 4000.0
    assert expired_put.end_date == 20230809
    assert expired_put.contract_size == 1000
    assert expired_put.is_expired is True

    # Filter by ua_ins_code for فملی
    femeli_opts = service.list_instruments(ua_ins_code="35425587644337450")
    assert len(femeli_opts) == 2
    assert {o.symbol for o in femeli_opts} == {"ضفمل1200", "طفمل1200"}

    # Re-running discovery is idempotent (no duplicate rows)
    records_second = service.discover_all(reference_date=20261108)
    assert len(records_second) == 31
    assert len(service.list_instruments()) == 31
