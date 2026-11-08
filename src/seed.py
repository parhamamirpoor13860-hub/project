"""End-to-end seed data loader executing Stages 1 through 5 on TSETMC fixtures."""
import json
import sqlite3
from typing import Any, Dict, Optional

from src.config import Settings, get_settings
from src.fixtures import generate_fixtures
from src.stage1_discovery import OptionDiscoveryService
from src.stage2_3_crawler_storage import RawStorageManager, TsetmcCrawler
from src.stage4_cleaning import ReconciliationEngine, TickCleaner
from src.stage5_series import SUPPORTED_TIMEFRAMES, build_matched_option_ticks, build_ohlcv_candles


def run_seed_pipeline(
    settings: Optional[Settings] = None,
    force_fixtures: bool = True,
) -> Dict[str, Any]:
    """
    Execute the complete 5-stage TSETMC pipeline against deterministic fixtures
    so the database, raw .json.gz archive, and processed .jsonl series are populated.
    """
    base = settings or get_settings()
    cfg = Settings(
        tsetmc_base_url=base.tsetmc_base_url,
        tsetmc_timeout_seconds=base.tsetmc_timeout_seconds,
        tsetmc_max_rps=base.tsetmc_max_rps,
        tsetmc_max_concurrency=base.tsetmc_max_concurrency,
        tsetmc_max_retries=base.tsetmc_max_retries,
        tsetmc_start_date=base.tsetmc_start_date,
        tsetmc_respect_trading_hours=base.tsetmc_respect_trading_hours,
        tsetmc_use_fixtures=True if force_fixtures else base.tsetmc_use_fixtures,
        data_dir=base.data_dir,
        raw_dir=base.raw_dir,
        processed_dir=base.processed_dir,
        fixtures_dir=base.fixtures_dir,
        state_db_path=base.state_db_path,
        duckdb_path=base.duckdb_path,
        backend_host=base.backend_host,
        backend_port=base.backend_port,
    )
    cfg.ensure_dirs()
    generate_fixtures(cfg.fixtures_dir)

    # Stage 1: Discovery & Instrument Registry
    discovery = OptionDiscoveryService(cfg)
    instruments = discovery.discover_all(reference_date=20261108)

    # Stage 2 & 3: Fault-Tolerant Crawler & Immutable .json.gz Raw Storage
    storage = RawStorageManager(cfg)
    crawler = TsetmcCrawler(
        settings=cfg,
        storage=storage,
        sleep_fn=(lambda _: None) if cfg.tsetmc_use_fixtures else None,  # type: ignore[arg-type]
    )
    crawl_summary = crawler.crawl_all(
        [r.ins_code for r in instruments], pause_on_trading_hours=False
    )

    # Stage 4: Cleaning, +03:30 Standardization & Reconciliation
    cleaner = TickCleaner(settings=cfg, storage=storage)
    clean_summary = cleaner.clean_all()
    recon_engine = ReconciliationEngine(settings=cfg)
    recon_summary = recon_engine.reconcile()

    # Stage 5: ASOF JOIN Matched Option Tick Stream & Multi-Timeframe OHLCV Candles
    matched_ticks = build_matched_option_ticks(settings=cfg)
    candles_by_tf = build_ohlcv_candles(settings=cfg, timeframes=SUPPORTED_TIMEFRAMES)

    return {
        "instruments_total": len(instruments),
        "underlyings_count": sum(1 for r in instruments if r.instrument_type == "underlying"),
        "options_count": sum(1 for r in instruments if r.instrument_type in ("call", "put")),
        "crawl": {
            "daily_fetched": crawl_summary["daily_fetched"],
            "ticks_fetched": crawl_summary["ticks_fetched"],
            "ticks_skipped_checkpoint": crawl_summary["ticks_skipped_checkpoint"],
        },
        "clean": clean_summary,
        "reconciliation": {
            "total_traded_days": recon_summary["total_traded_days"],
            "matched_days": recon_summary["matched_days"],
            "match_rate_pct": recon_summary["match_rate_pct"],
            "meets_98_pct_target": recon_summary["meets_98_pct_target"],
        },
        "stage5": {
            "matched_option_ticks": len(matched_ticks),
            "candles_counts": {tf: len(rows) for tf, rows in candles_by_tf.items()},
        },
    }


def ensure_seeded(settings: Optional[Settings] = None) -> bool:
    """Seed the database from fixtures if `instruments` or `reconciliation_report` is empty."""
    cfg = settings or get_settings()
    cfg.ensure_dirs()
    if cfg.state_db_path.is_file():
        try:
            with sqlite3.connect(cfg.state_db_path) as conn:
                inst_count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
                recon_count = conn.execute("SELECT COUNT(*) FROM reconciliation_report").fetchone()[0]
                if inst_count > 0 and recon_count > 0:
                    return False
        except sqlite3.Error:
            pass
    run_seed_pipeline(cfg, force_fixtures=True)
    return True


if __name__ == "__main__":
    summary = run_seed_pipeline()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
