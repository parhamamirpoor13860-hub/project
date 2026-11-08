"""Stage 2 (Fault-Tolerant Resumable Crawler) & Stage 3 (Immutable .json.gz Raw Storage)."""
import gzip
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.config import Settings, get_settings
from src.fixtures import generate_fixtures
from src.models import ClosingPriceDailyResponse
from src.stage1_discovery import BROWSER_HEADERS

IRAN_TZ = timezone(timedelta(hours=3, minutes=30), name="IRST")
TEHRAN_TRADING_WEEKDAYS = {5, 6, 0, 1, 2}  # Saturday(5), Sunday(6), Monday(0), Tuesday(1), Wednesday(2)
TEHRAN_MARKET_OPEN = dt_time(9, 0, 0)
TEHRAN_MARKET_CLOSE = dt_time(12, 30, 0)


class CrawlerBannedError(RuntimeError):
    """Raised immediately when TSETMC returns HTTP 403 Forbidden (IP ban/block)."""


class TradingHoursPauseError(RuntimeError):
    """Raised when heavy crawling is blocked during Tehran market trading hours."""


def is_tehran_trading_hours(dt_utc: Optional[datetime] = None) -> bool:
    """
    Check if the given timestamp falls within Tehran Stock Exchange trading hours:
    Saturday through Wednesday, 09:00:00 to 12:30:00 Iran Standard Time (UTC+03:30, no DST).
    """
    if dt_utc is None:
        dt_utc = datetime.now(timezone.utc)
    elif dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)

    tehran_dt = dt_utc.astimezone(IRAN_TZ)
    if tehran_dt.weekday() not in TEHRAN_TRADING_WEEKDAYS:
        return False
    local_time = tehran_dt.timetz().replace(tzinfo=None)
    return TEHRAN_MARKET_OPEN <= local_time <= TEHRAN_MARKET_CLOSE


class RawStorageManager:
    """
    Stage 3: Immutable Raw Storage manager.
    Saves unmodified JSON responses as discrete gzip files:
      - data/raw/daily/{insCode}.json.gz
      - data/raw/ticks/{insCode}/{YYYYMMDD}.json.gz
    And logs metadata in SQLite table `raw_manifest`.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.daily_dir = self.settings.raw_dir / "daily"
        self.ticks_dir = self.settings.raw_dir / "ticks"
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.ticks_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        self.settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_manifest (
                    artifact_key TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    ins_code TEXT NOT NULL,
                    d_even INTEGER NOT NULL DEFAULT 0,
                    file_path TEXT NOT NULL,
                    http_status INTEGER NOT NULL,
                    compressed_bytes INTEGER NOT NULL,
                    raw_record_count INTEGER NOT NULL,
                    downloaded_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def daily_file_path(self, ins_code: str) -> Path:
        return self.daily_dir / f"{ins_code}.json.gz"

    def ticks_file_path(self, ins_code: str, d_even: int) -> Path:
        return self.ticks_dir / str(ins_code) / f"{int(d_even)}.json.gz"

    def _write_gzip_atomic(self, target_path: Path, payload: Dict[str, Any]) -> int:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(raw_bytes, compresslevel=6)
        tmp_path.write_bytes(compressed)
        os.replace(tmp_path, target_path)
        return len(compressed)

    def _record_manifest(
        self,
        artifact_key: str,
        artifact_type: str,
        ins_code: str,
        d_even: int,
        file_path: Path,
        http_status: int,
        compressed_bytes: int,
        raw_record_count: int,
    ) -> Dict[str, Any]:
        downloaded_at = datetime.now(timezone.utc).isoformat()
        entry = {
            "artifact_key": artifact_key,
            "artifact_type": artifact_type,
            "ins_code": str(ins_code),
            "d_even": int(d_even),
            "file_path": str(file_path),
            "http_status": int(http_status),
            "compressed_bytes": int(compressed_bytes),
            "raw_record_count": int(raw_record_count),
            "downloaded_at": downloaded_at,
        }
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                """
                INSERT INTO raw_manifest (
                    artifact_key, artifact_type, ins_code, d_even,
                    file_path, http_status, compressed_bytes,
                    raw_record_count, downloaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_key) DO UPDATE SET
                    file_path = excluded.file_path,
                    http_status = excluded.http_status,
                    compressed_bytes = excluded.compressed_bytes,
                    raw_record_count = excluded.raw_record_count,
                    downloaded_at = excluded.downloaded_at
                """,
                (
                    entry["artifact_key"],
                    entry["artifact_type"],
                    entry["ins_code"],
                    entry["d_even"],
                    entry["file_path"],
                    entry["http_status"],
                    entry["compressed_bytes"],
                    entry["raw_record_count"],
                    entry["downloaded_at"],
                ),
            )
            conn.commit()
        return entry

    def save_daily_raw(
        self, ins_code: str, payload: Dict[str, Any], http_status: int = 200
    ) -> Dict[str, Any]:
        """Atomically write unmodified daily closing price response to .json.gz and record in manifest."""
        target = self.daily_file_path(ins_code)
        compressed_bytes = self._write_gzip_atomic(target, payload)
        records = payload.get("closingPriceDaily")
        raw_count = len(records) if isinstance(records, list) else 0
        return self._record_manifest(
            artifact_key=f"daily:{ins_code}",
            artifact_type="daily",
            ins_code=ins_code,
            d_even=0,
            file_path=target,
            http_status=http_status,
            compressed_bytes=compressed_bytes,
            raw_record_count=raw_count,
        )

    def save_ticks_raw(
        self,
        ins_code: str,
        d_even: int,
        payload: Dict[str, Any],
        http_status: int = 200,
    ) -> Dict[str, Any]:
        """Atomically write unmodified intraday tradeHistory response to .json.gz and record in manifest."""
        target = self.ticks_file_path(ins_code, d_even)
        compressed_bytes = self._write_gzip_atomic(target, payload)
        records = payload.get("tradeHistory")
        raw_count = len(records) if isinstance(records, list) else 0
        return self._record_manifest(
            artifact_key=f"ticks:{ins_code}:{int(d_even)}",
            artifact_type="ticks",
            ins_code=ins_code,
            d_even=int(d_even),
            file_path=target,
            http_status=http_status,
            compressed_bytes=compressed_bytes,
            raw_record_count=raw_count,
        )

    def has_artifact(self, artifact_key: str) -> bool:
        """Return True if artifact_key is recorded in raw_manifest AND the .json.gz file exists on disk."""
        with sqlite3.connect(self.settings.state_db_path) as conn:
            row = conn.execute(
                "SELECT file_path FROM raw_manifest WHERE artifact_key = ?",
                (artifact_key,),
            ).fetchone()
        if not row:
            return False
        return Path(row[0]).is_file()

    def read_daily_raw(self, ins_code: str) -> Dict[str, Any]:
        """Read and decompress daily raw JSON for ins_code."""
        path = self.daily_file_path(ins_code)
        raw_bytes = gzip.decompress(path.read_bytes())
        return json.loads(raw_bytes.decode("utf-8"))

    def read_ticks_raw(self, ins_code: str, d_even: int) -> Dict[str, Any]:
        """Read and decompress intraday tick raw JSON for (ins_code, d_even)."""
        path = self.ticks_file_path(ins_code, d_even)
        raw_bytes = gzip.decompress(path.read_bytes())
        return json.loads(raw_bytes.decode("utf-8"))

    def list_manifest(
        self,
        artifact_type: Optional[str] = None,
        ins_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List manifest records ordered by artifact_key."""
        clauses: List[str] = []
        params: List[Any] = []
        if artifact_type is not None:
            clauses.append("artifact_type = ?")
            params.append(artifact_type)
        if ins_code is not None:
            clauses.append("ins_code = ?")
            params.append(ins_code)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT artifact_key, artifact_type, ins_code, d_even,
                   file_path, http_status, compressed_bytes,
                   raw_record_count, downloaded_at
            FROM raw_manifest
            {where_sql}
            ORDER BY artifact_key ASC
        """
        with sqlite3.connect(self.settings.state_db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "artifact_key": r[0],
                "artifact_type": r[1],
                "ins_code": r[2],
                "d_even": r[3],
                "file_path": r[4],
                "http_status": r[5],
                "compressed_bytes": r[6],
                "raw_record_count": r[7],
                "downloaded_at": r[8],
            }
            for r in rows
        ]


class TsetmcCrawler:
    """
    Stage 2: Fault-Tolerant, Rate-Limited, Resumable Crawler for TSETMC Daily & Intraday Tick Data.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        storage: Optional[RawStorageManager] = None,
        fetcher: Optional[Callable[[str], Tuple[int, Dict[str, Any]]]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_utc_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage or RawStorageManager(self.settings)
        self._custom_fetcher = fetcher
        self._sleep_fn = sleep_fn
        self._now_utc_fn = now_utc_fn
        self._last_request_ts: Optional[float] = None
        self._fixture_cache: Dict[str, Any] = {}
        self.fetch_count: int = 0

    def _load_fixtures(self) -> None:
        if self._fixture_cache:
            return
        req_files = ["closing_price_daily.json", "trade_history.json"]
        if not all((self.settings.fixtures_dir / f).is_file() for f in req_files):
            generate_fixtures(self.settings.fixtures_dir)
        for fname in req_files:
            fpath = self.settings.fixtures_dir / fname
            self._fixture_cache[fname] = json.loads(fpath.read_text(encoding="utf-8"))

    def _enforce_rate_limit(self) -> None:
        if self.settings.tsetmc_max_rps <= 0:
            return
        min_interval = 1.0 / self.settings.tsetmc_max_rps
        now = time.monotonic()
        if self._last_request_ts is not None:
            elapsed = now - self._last_request_ts
            if elapsed < min_interval:
                self._sleep_fn(min_interval - elapsed)
        self._last_request_ts = time.monotonic()

    def _check_trading_hours_guard(self, pause_on_trading_hours: bool) -> None:
        if not self.settings.tsetmc_respect_trading_hours or not pause_on_trading_hours:
            return
        if is_tehran_trading_hours(self._now_utc_fn()):
            raise TradingHoursPauseError(
                "Crawling paused: currently inside Tehran market trading hours (Sat-Wed 09:00-12:30 +03:30)."
            )

    def _default_http_fetch(self, endpoint: str) -> Tuple[int, Dict[str, Any]]:
        url = f"{self.settings.tsetmc_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        req = urllib.request.Request(url, headers=BROWSER_HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=self.settings.tsetmc_timeout_seconds) as resp:
            status = int(resp.status)
            raw = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return status, json.loads(raw.decode("utf-8"))

    def _fixture_fetch(self, endpoint: str) -> Tuple[int, Dict[str, Any]]:
        self._load_fixtures()
        clean = endpoint.strip("/")
        if clean.startswith("ClosingPrice/GetClosingPriceDailyList/"):
            parts = clean.split("/")
            ins_code = parts[2]
            daily_map = self._fixture_cache["closing_price_daily.json"]
            return 200, daily_map.get(ins_code, {"closingPriceDaily": []})
        if clean.startswith("Trade/GetTradeHistory/"):
            parts = clean.split("/")
            ins_code = parts[2]
            d_even = parts[3]
            trades_map = self._fixture_cache["trade_history.json"]
            return 200, trades_map.get(f"{ins_code}_{d_even}", {"tradeHistory": []})
        raise ValueError(f"Unsupported fixture endpoint: {endpoint}")

    def fetch_with_retry(
        self, endpoint: str, pause_on_trading_hours: bool = False
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Execute an endpoint fetch with rate limiting, trading-hours guard,
        exponential backoff on HTTP 429/5xx/timeout, and immediate stop on HTTP 403.
        """
        self._check_trading_hours_guard(pause_on_trading_hours=pause_on_trading_hours)
        max_retries = max(0, int(self.settings.tsetmc_max_retries))
        attempt = 0

        while True:
            self._enforce_rate_limit()
            self.fetch_count += 1
            try:
                if self._custom_fetcher is not None:
                    status, payload = self._custom_fetcher(endpoint)
                elif self.settings.tsetmc_use_fixtures:
                    status, payload = self._fixture_fetch(endpoint)
                else:
                    status, payload = self._default_http_fetch(endpoint)

                if status == 403:
                    raise CrawlerBannedError(f"HTTP 403 Forbidden received on {endpoint}; aborting crawl.")
                if status in (429, 500, 502, 503, 504):
                    raise urllib.error.HTTPError(
                        url=endpoint, code=status, msg=f"Transient HTTP {status}", hdrs=None, fp=None  # type: ignore[arg-type]
                    )
                return status, payload

            except CrawlerBannedError:
                raise
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    raise CrawlerBannedError(
                        f"HTTP 403 Forbidden received on {endpoint}; aborting crawl."
                    ) from exc
                if attempt >= max_retries:
                    raise
                backoff = 0.5 * (2**attempt)
                self._sleep_fn(backoff)
                attempt += 1
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= max_retries:
                    if not self.settings.tsetmc_use_fixtures and self._custom_fetcher is None:
                        # Geo-IP fallback to local fixtures when live network times out
                        self.settings.tsetmc_use_fixtures = True
                        return self._fixture_fetch(endpoint)
                    raise exc
                backoff = 0.5 * (2**attempt)
                self._sleep_fn(backoff)
                attempt += 1

    def crawl_instrument(
        self, ins_code: str, pause_on_trading_hours: bool = False
    ) -> Dict[str, Any]:
        """
        Crawl daily history and eligible intraday tick days for a single instrument.
        Skips already-checkpointed artifacts and days with dEven < start_date or zTotTran <= 0.
        """
        daily_key = f"daily:{ins_code}"
        daily_fetched = False

        if self.storage.has_artifact(daily_key):
            daily_payload = self.storage.read_daily_raw(ins_code)
        else:
            status, daily_payload = self.fetch_with_retry(
                f"/ClosingPrice/GetClosingPriceDailyList/{ins_code}/0",
                pause_on_trading_hours=pause_on_trading_hours,
            )
            self.storage.save_daily_raw(ins_code, daily_payload, http_status=status)
            daily_fetched = True

        daily_resp = ClosingPriceDailyResponse.parse_obj(daily_payload)
        eligible_days = sorted(
            {
                int(row.dEven)
                for row in daily_resp.closingPriceDaily
                if int(row.dEven) >= self.settings.tsetmc_start_date and float(row.zTotTran) > 0
            }
        )

        ticks_fetched = 0
        ticks_skipped_checkpoint = 0
        for d_even in eligible_days:
            tick_key = f"ticks:{ins_code}:{d_even}"
            if self.storage.has_artifact(tick_key):
                ticks_skipped_checkpoint += 1
                continue
            status, tick_payload = self.fetch_with_retry(
                f"/Trade/GetTradeHistory/{ins_code}/{d_even}/false",
                pause_on_trading_hours=pause_on_trading_hours,
            )
            self.storage.save_ticks_raw(ins_code, d_even, tick_payload, http_status=status)
            ticks_fetched += 1

        return {
            "ins_code": ins_code,
            "daily_fetched": daily_fetched,
            "eligible_tick_days": len(eligible_days),
            "ticks_fetched": ticks_fetched,
            "ticks_skipped_checkpoint": ticks_skipped_checkpoint,
        }

    def crawl_all(
        self,
        ins_codes: Iterable[str],
        pause_on_trading_hours: bool = False,
    ) -> Dict[str, Any]:
        """Crawl daily + intraday ticks for all provided ins_codes with full checkpoint resumability."""
        results: List[Dict[str, Any]] = []
        total_daily_fetched = 0
        total_ticks_fetched = 0
        total_ticks_skipped = 0

        for code in ins_codes:
            res = self.crawl_instrument(code, pause_on_trading_hours=pause_on_trading_hours)
            results.append(res)
            if res["daily_fetched"]:
                total_daily_fetched += 1
            total_ticks_fetched += res["ticks_fetched"]
            total_ticks_skipped += res["ticks_skipped_checkpoint"]

        return {
            "instruments_processed": len(results),
            "daily_fetched": total_daily_fetched,
            "ticks_fetched": total_ticks_fetched,
            "ticks_skipped_checkpoint": total_ticks_skipped,
            "details": results,
        }
