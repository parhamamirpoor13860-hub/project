"""CLI entrypoint for running individual pipeline stages, seeding fixtures, and printing reports."""
import argparse
import json
import sys
from typing import List, Optional

from src.config import get_settings
from src.seed import run_seed_pipeline
from src.stage1_discovery import OptionDiscoveryService
from src.stage2_3_crawler_storage import RawStorageManager, TsetmcCrawler
from src.stage4_cleaning import ReconciliationEngine, TickCleaner
from src.stage5_series import SUPPORTED_TIMEFRAMES, build_matched_option_ticks, build_ohlcv_candles


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m src.cli",
        description="TSETMC Options Market Tick-Data Platform Pipeline CLI",
    )
    parser.add_argument(
        "command",
        choices=["stage1", "stage2-3", "stage4", "stage5", "seed", "report"],
        help="Pipeline stage or action to execute",
    )
    parser.add_argument(
        "--use-fixtures",
        action="store_true",
        help="Force using local deterministic fixtures in data/fixtures/",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.use_fixtures:
        settings.tsetmc_use_fixtures = True

    if args.command == "seed":
        out = run_seed_pipeline(settings=settings, force_fixtures=True)
    elif args.command == "stage1":
        svc = OptionDiscoveryService(settings)
        records = svc.discover_all()
        out = {
            "stage": "stage1",
            "discovered_total": len(records),
            "underlyings": sum(1 for r in records if r.instrument_type == "underlying"),
            "options": sum(1 for r in records if r.instrument_type in ("call", "put")),
        }
    elif args.command == "stage2-3":
        svc = OptionDiscoveryService(settings)
        records = svc.list_instruments() or svc.discover_all()
        storage = RawStorageManager(settings)
        crawler = TsetmcCrawler(settings=settings, storage=storage)
        out = crawler.crawl_all([r.ins_code for r in records])
    elif args.command == "stage4":
        storage = RawStorageManager(settings)
        cleaner = TickCleaner(settings=settings, storage=storage)
        clean_res = cleaner.clean_all()
        recon_res = ReconciliationEngine(settings=settings).reconcile()
        out = {"clean": clean_res, "reconciliation": recon_res}
    elif args.command == "stage5":
        matched = build_matched_option_ticks(settings=settings)
        candles = build_ohlcv_candles(settings=settings, timeframes=SUPPORTED_TIMEFRAMES)
        out = {
            "matched_option_ticks": len(matched),
            "candles": {tf: len(rows) for tf, rows in candles.items()},
        }
    elif args.command == "report":
        recon_res = ReconciliationEngine(settings=settings).reconcile()
        out = recon_res
    else:
        return 1

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
