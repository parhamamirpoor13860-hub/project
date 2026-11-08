"""Unit and integration tests for Stage 6 (Seed Pipeline, CLI, and FastAPI Backend Endpoints)."""
from pathlib import Path

from src.api import AsgiTestClient, create_app
from src.config import Settings
from src.cli import main as cli_main
from src.seed import run_seed_pipeline


def _make_stage6_settings(tmp_path: Path) -> Settings:
    return Settings(
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


def test_seed_pipeline_end_to_end(tmp_path: Path) -> None:
    settings = _make_stage6_settings(tmp_path)
    summary = run_seed_pipeline(settings=settings, force_fixtures=True)

    assert summary["instruments_total"] == 31
    assert summary["underlyings_count"] == 25
    assert summary["options_count"] == 6
    assert summary["crawl"]["daily_fetched"] == 31
    assert summary["crawl"]["ticks_fetched"] == 12
    assert summary["reconciliation"]["total_traded_days"] == 12
    assert summary["reconciliation"]["matched_days"] == 12
    assert summary["reconciliation"]["match_rate_pct"] == 100.0
    assert summary["reconciliation"]["meets_98_pct_target"] is True
    assert summary["stage5"]["matched_option_ticks"] > 0
    for tf in ("1m", "5m", "15m", "1h", "1d"):
        assert summary["stage5"]["candles_counts"][tf] > 0
        assert (settings.processed_dir / f"ohlcv_{tf}.jsonl").is_file()
    assert (settings.processed_dir / "option_ticks_matched.jsonl").is_file()


def test_fastapi_endpoints_via_asgi_client(tmp_path: Path) -> None:
    settings = _make_stage6_settings(tmp_path)
    app = create_app(settings=settings)
    client = AsgiTestClient(app)

    # 1. Root HTML dashboard
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert "TSETMC" in root_resp.text

    # 2. Health endpoint (also verifies auto-seeding when database starts empty)
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health["status"] == "ok"
    assert health["underlyings_count"] == 25
    assert health["options_count"] == 6
    assert health["reconciliation_match_rate"] >= 98.0
    assert health["meets_98_pct_target"] is True

    # 3. Underlyings list
    ua_resp = client.get("/api/underlyings")
    assert ua_resp.status_code == 200
    ua_data = ua_resp.json()
    assert ua_data["count"] == 25
    folad = next(u for u in ua_data["underlyings"] if u["ins_code"] == "46348559193224090")
    assert folad["symbol"] == "فولاد"
    assert folad["latest_price"] == 4410.0
    assert folad["active_options_count"] == 2
    assert folad["expired_options_count"] == 2

    # 4. Options filtering (active vs expired, Call vs Put, underlying filter, query search)
    opt_all = client.get("/api/options").json()
    assert opt_all["count"] == 6

    opt_active_only = client.get("/api/options", params={"include_expired": "false"}).json()
    assert opt_active_only["count"] == 4

    opt_folad_calls = client.get(
        "/api/options",
        params={"ua_ins_code": "46348559193224090", "option_type": "call"},
    ).json()
    assert opt_folad_calls["count"] == 2

    # 5. Option Chain endpoint
    chain_resp = client.get(
        "/api/option-chain",
        params={"ua_ins_code": "46348559193224090", "d_even": 20261107},
    )
    assert chain_resp.status_code == 200
    chain_data = chain_resp.json()
    assert chain_data["symbol"] == "فولاد"
    assert chain_data["d_even"] == 20261107
    assert chain_data["underlying_price"] == 4410.0
    assert chain_data["count"] >= 2
    active_pair = next(r for r in chain_data["chain"] if r["end_date"] == 20261221)
    assert active_pair["strike_price"] == 4500.0
    assert active_pair["call_symbol"] == "ضفلا1100"
    assert active_pair["put_symbol"] == "طفلا1100"
    assert active_pair["dte"] == 44

    # 6. Ticks endpoint (Option ASOF JOIN matched stream vs Underlying clean ticks)
    opt_ticks_resp = client.get(
        "/api/ticks",
        params={"ins_code": "90000000000000001", "d_even": 20261107},
    )
    assert opt_ticks_resp.status_code == 200
    opt_ticks = opt_ticks_resp.json()
    assert opt_ticks["instrument_type"] == "call"
    assert opt_ticks["count"] == 4
    first_tick = opt_ticks["ticks"][0]
    assert first_tick["n_tran"] == 1
    assert first_tick["underlying_price"] == 4410.0
    assert first_tick["ts_tehran"].endswith("+03:30")
    assert first_tick["underlying_ts_epoch"] <= first_tick["ts_epoch"]

    ua_ticks_resp = client.get(
        "/api/ticks",
        params={"ins_code": "46348559193224090", "d_even": 20261107},
    )
    assert ua_ticks_resp.status_code == 200
    assert ua_ticks_resp.json()["count"] == 5

    # 7. Candles endpoint across all 5 timeframes (1m, 5m, 15m, 1h, 1d)
    for tf in ("1m", "5m", "15m", "1h", "1d"):
        c_resp = client.get(
            "/api/candles",
            params={"ins_code": "90000000000000001", "timeframe": tf},
        )
        assert c_resp.status_code == 200
        c_data = c_resp.json()
        assert c_data["timeframe"] == tf
        assert c_data["count"] > 0
        if tf == "1m":
            assert any(c["is_sparse"] == 1 and c["volume"] == 0 for c in c_data["candles"])

    bad_tf = client.get("/api/candles", params={"ins_code": "90000000000000001", "timeframe": "2h"})
    assert bad_tf.status_code == 400

    # 8. Data Quality & Reconciliation report endpoint
    qr_resp = client.get("/api/quality-report")
    assert qr_resp.status_code == 200
    qr = qr_resp.json()
    assert qr["total_traded_days"] == 12
    assert qr["matched_days"] == 12
    assert qr["match_rate_pct"] == 100.0
    assert qr["meets_98_pct_target"] is True
    assert qr["canceled_trades_count"] == 5
    assert all(r["status"] == "MATCH" for r in qr["rows"])


def test_cli_commands(tmp_path: Path, monkeypatch) -> None:
    import src.cli as cli_mod

    settings = _make_stage6_settings(tmp_path)
    monkeypatch.setattr(cli_mod, "get_settings", lambda: settings)
    assert cli_main(["seed", "--use-fixtures"]) == 0
    assert cli_main(["report"]) == 0

