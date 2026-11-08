"""Stage 5: Unified Sequences (ASOF JOIN Tick Stream), Multi-Timeframe OHLCV Candles & Option Chain Builder."""
import bisect
import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.config import Settings, get_settings
from src.fixtures import OPTION_CONTRACTS_FIXTURE, build_option_market_watch_fixture
from src.stage4_cleaning import IRAN_STANDARD_TZ

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}
SUPPORTED_TIMEFRAMES: Tuple[str, ...] = ("1m", "5m", "15m", "1h", "1d")
TEHRAN_OFFSET_SECONDS = 3 * 3600 + 30 * 60  # +03:30 = 12,600s


def _int_date_to_date(d_even: int) -> date:
    d_str = f"{int(d_even):08d}"
    return date(int(d_str[0:4]), int(d_str[4:6]), int(d_str[6:8]))


def _epoch_to_iso_pair(epoch_sec: int) -> Tuple[str, str]:
    dt_utc = datetime.fromtimestamp(int(epoch_sec), tz=timezone.utc)
    dt_tehran = dt_utc.astimezone(IRAN_STANDARD_TZ)
    return dt_tehran.isoformat(), dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _align_bucket_epoch(ts_epoch: int, interval_sec: int) -> int:
    """Align timestamp epoch to Tehran local interval boundary (+03:30 offset)."""
    shifted = int(ts_epoch) + TEHRAN_OFFSET_SECONDS
    return (shifted // interval_sec) * interval_sec - TEHRAN_OFFSET_SECONDS


def classify_moneyness(
    instrument_type: str,
    underlying_price: Optional[float],
    strike_price: Optional[float],
    atm_band: float = 0.02,
) -> str:
    """
    Classify option moneyness relative to the underlying asset price:
    - If abs(underlying_price - strike_price) / strike_price <= 0.02 -> "ATM"
    - Else for Call: underlying_price > strike_price -> "ITM" else "OTM"
    - Else for Put: underlying_price < strike_price -> "ITM" else "OTM"
    """
    if underlying_price is None or strike_price is None or strike_price <= 0:
        return "ATM"
    rel_diff = abs(float(underlying_price) - float(strike_price)) / float(strike_price)
    if rel_diff <= atm_band + 1e-12:
        return "ATM"
    if str(instrument_type).lower() == "call":
        return "ITM" if float(underlying_price) > float(strike_price) else "OTM"
    return "ITM" if float(underlying_price) < float(strike_price) else "OTM"


def _init_stage5_tables(settings: Settings) -> None:
    settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.state_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS option_ticks_matched (
                ins_code TEXT NOT NULL,
                symbol TEXT NOT NULL,
                ua_ins_code TEXT NOT NULL,
                d_even INTEGER NOT NULL,
                h_even INTEGER NOT NULL,
                n_tran INTEGER NOT NULL,
                ts_tehran TEXT NOT NULL,
                ts_utc TEXT NOT NULL,
                ts_epoch INTEGER NOT NULL,
                price REAL NOT NULL,
                volume REAL NOT NULL,
                underlying_price REAL,
                underlying_ts_utc TEXT,
                underlying_ts_epoch INTEGER,
                underlying_n_tran INTEGER,
                moneyness_status TEXT NOT NULL,
                PRIMARY KEY (ins_code, d_even, n_tran)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv_candles (
                ins_code TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                d_even INTEGER NOT NULL,
                bucket_epoch INTEGER NOT NULL,
                bucket_ts_tehran TEXT NOT NULL,
                bucket_ts_utc TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                last_price REAL NOT NULL,
                close_ffill REAL NOT NULL,
                volume REAL NOT NULL,
                value REAL NOT NULL,
                trade_count INTEGER NOT NULL,
                is_sparse INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (ins_code, timeframe, bucket_epoch)
            )
            """
        )
        conn.commit()


def _load_option_metadata_map(settings: Settings) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    with sqlite3.connect(settings.state_db_path) as conn:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instruments'"
        ).fetchone()
        if table_exists:
            rows = conn.execute(
                """
                SELECT ins_code, symbol, full_name, instrument_type,
                       ua_ins_code, strike_price, end_date, contract_size
                FROM instruments
                WHERE instrument_type IN ('call', 'put')
                """
            ).fetchall()
            for r in rows:
                meta[str(r[0])] = {
                    "ins_code": str(r[0]),
                    "symbol": str(r[1]),
                    "full_name": str(r[2]),
                    "instrument_type": str(r[3]),
                    "ua_ins_code": str(r[4]) if r[4] else "",
                    "strike_price": float(r[5]) if r[5] is not None else 0.0,
                    "end_date": int(r[6]) if r[6] is not None else 0,
                    "contract_size": int(r[7] or 1000),
                }

    # Ensure fallback fixture options are also known if instruments table is partial
    for opt in OPTION_CONTRACTS_FIXTURE:
        code = str(opt["insCode"])
        if code not in meta:
            meta[code] = {
                "ins_code": code,
                "symbol": str(opt["lVal18AFC"]),
                "full_name": str(opt["lVal30"]),
                "instrument_type": str(opt["instrument_type"]),
                "ua_ins_code": str(opt["uaInsCode"]),
                "strike_price": float(opt["strikePrice"]),
                "end_date": int(opt["endDate"]),
                "contract_size": int(opt["contractSize"]),
            }
    return meta


def build_matched_option_ticks(
    settings: Optional[Settings] = None,
    ins_code: Optional[str] = None,
    d_even: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Stage 5.1: Clean Tick Stream with Underlying Price (ASOF JOIN).
    For every valid option tick (canceled == 0), links it with the most recent valid trade
    (canceled == 0) of its underlying asset (ua_ins_code) where ts_underlying <= ts_option
    using bisect_right. Never leaks a future underlying trade.
    Persists to SQLite `option_ticks_matched` and `data/processed/option_ticks_matched.jsonl`.
    """
    cfg = settings or get_settings()
    cfg.ensure_dirs()
    _init_stage5_tables(cfg)

    opt_meta = _load_option_metadata_map(cfg)
    if not opt_meta:
        return []

    target_opt_codes = (
        [str(ins_code)] if ins_code is not None and str(ins_code) in opt_meta else sorted(opt_meta.keys())
    )
    ua_codes = sorted({opt_meta[c]["ua_ins_code"] for c in target_opt_codes if opt_meta[c]["ua_ins_code"]})

    # Load all valid underlying ticks sorted chronologically by (ts_epoch ASC, n_tran ASC)
    ua_ticks_map: Dict[str, List[Dict[str, Any]]] = {}
    ua_epochs_map: Dict[str, List[int]] = {}

    with sqlite3.connect(cfg.state_db_path) as conn:
        for ua_code in ua_codes:
            rows = conn.execute(
                """
                SELECT d_even, h_even, n_tran, ts_tehran, ts_utc, ts_epoch, p_tran, q_tit_tran
                FROM clean_ticks
                WHERE ins_code = ? AND canceled = 0
                ORDER BY ts_epoch ASC, n_tran ASC
                """,
                (ua_code,),
            ).fetchall()
            ticks = [
                {
                    "d_even": int(r[0]),
                    "h_even": int(r[1]),
                    "n_tran": int(r[2]),
                    "ts_tehran": str(r[3]),
                    "ts_utc": str(r[4]),
                    "ts_epoch": int(r[5]),
                    "p_tran": float(r[6]),
                    "q_tit_tran": float(r[7]),
                }
                for r in rows
            ]
            ua_ticks_map[ua_code] = ticks
            ua_epochs_map[ua_code] = [t["ts_epoch"] for t in ticks]

        # Query valid option ticks
        clauses = ["canceled = 0"]
        params: List[Any] = []
        if ins_code is not None:
            clauses.append("ins_code = ?")
            params.append(str(ins_code))
        else:
            placeholders = ",".join("?" for _ in target_opt_codes)
            clauses.append(f"ins_code IN ({placeholders})")
            params.extend(target_opt_codes)

        if d_even is not None:
            clauses.append("d_even = ?")
            params.append(int(d_even))

        opt_rows = conn.execute(
            f"""
            SELECT ins_code, d_even, h_even, n_tran, ts_tehran, ts_utc, ts_epoch, p_tran, q_tit_tran
            FROM clean_ticks
            WHERE {' AND '.join(clauses)}
            ORDER BY ins_code ASC, d_even ASC, h_even ASC, n_tran ASC
            """,
            params,
        ).fetchall()

    matched_records: List[Dict[str, Any]] = []
    for r in opt_rows:
        o_code = str(r[0])
        if o_code not in opt_meta:
            continue
        meta = opt_meta[o_code]
        ua_code = meta["ua_ins_code"]
        o_d_even = int(r[1])
        o_h_even = int(r[2])
        o_n_tran = int(r[3])
        o_ts_tehran = str(r[4])
        o_ts_utc = str(r[5])
        o_ts_epoch = int(r[6])
        o_price = float(r[7])
        o_volume = float(r[8])

        ua_ticks = ua_ticks_map.get(ua_code, [])
        ua_epochs = ua_epochs_map.get(ua_code, [])

        # ASOF JOIN: rightmost underlying trade where ts_underlying <= ts_option
        idx = bisect.bisect_right(ua_epochs, o_ts_epoch) - 1
        if idx >= 0:
            matched_ua = ua_ticks[idx]
            underlying_price: Optional[float] = matched_ua["p_tran"]
            underlying_ts_utc: Optional[str] = matched_ua["ts_utc"]
            underlying_ts_epoch: Optional[int] = matched_ua["ts_epoch"]
            underlying_n_tran: Optional[int] = matched_ua["n_tran"]
        else:
            underlying_price = None
            underlying_ts_utc = None
            underlying_ts_epoch = None
            underlying_n_tran = None

        moneyness = classify_moneyness(
            meta["instrument_type"], underlying_price, meta["strike_price"]
        )

        matched_records.append(
            {
                "ins_code": o_code,
                "symbol": meta["symbol"],
                "ua_ins_code": ua_code,
                "d_even": o_d_even,
                "h_even": o_h_even,
                "n_tran": o_n_tran,
                "ts_tehran": o_ts_tehran,
                "ts_utc": o_ts_utc,
                "ts_epoch": o_ts_epoch,
                "price": o_price,
                "volume": o_volume,
                "underlying_price": underlying_price,
                "underlying_ts_utc": underlying_ts_utc,
                "underlying_ts_epoch": underlying_ts_epoch,
                "underlying_n_tran": underlying_n_tran,
                "moneyness_status": moneyness,
            }
        )

    with sqlite3.connect(cfg.state_db_path) as conn:
        if matched_records:
            conn.executemany(
                """
                INSERT INTO option_ticks_matched (
                    ins_code, symbol, ua_ins_code, d_even, h_even, n_tran,
                    ts_tehran, ts_utc, ts_epoch, price, volume,
                    underlying_price, underlying_ts_utc, underlying_ts_epoch,
                    underlying_n_tran, moneyness_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ins_code, d_even, n_tran) DO UPDATE SET
                    symbol = excluded.symbol,
                    ua_ins_code = excluded.ua_ins_code,
                    h_even = excluded.h_even,
                    ts_tehran = excluded.ts_tehran,
                    ts_utc = excluded.ts_utc,
                    ts_epoch = excluded.ts_epoch,
                    price = excluded.price,
                    volume = excluded.volume,
                    underlying_price = excluded.underlying_price,
                    underlying_ts_utc = excluded.underlying_ts_utc,
                    underlying_ts_epoch = excluded.underlying_ts_epoch,
                    underlying_n_tran = excluded.underlying_n_tran,
                    moneyness_status = excluded.moneyness_status
                """,
                [
                    (
                        m["ins_code"],
                        m["symbol"],
                        m["ua_ins_code"],
                        m["d_even"],
                        m["h_even"],
                        m["n_tran"],
                        m["ts_tehran"],
                        m["ts_utc"],
                        m["ts_epoch"],
                        m["price"],
                        m["volume"],
                        m["underlying_price"],
                        m["underlying_ts_utc"],
                        m["underlying_ts_epoch"],
                        m["underlying_n_tran"],
                        m["moneyness_status"],
                    )
                    for m in matched_records
                ],
            )
            conn.commit()

    # Export all stored matched ticks to data/processed/option_ticks_matched.jsonl
    jsonl_path = cfg.processed_dir / "option_ticks_matched.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cfg.state_db_path) as conn:
        all_rows = conn.execute(
            """
            SELECT ins_code, symbol, ua_ins_code, d_even, h_even, n_tran,
                   ts_tehran, ts_utc, ts_epoch, price, volume,
                   underlying_price, underlying_ts_utc, underlying_ts_epoch,
                   underlying_n_tran, moneyness_status
            FROM option_ticks_matched
            ORDER BY ins_code ASC, d_even ASC, h_even ASC, n_tran ASC
            """
        ).fetchall()

    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in all_rows:
            obj = {
                "ins_code": r[0],
                "symbol": r[1],
                "ua_ins_code": r[2],
                "d_even": r[3],
                "h_even": r[4],
                "n_tran": r[5],
                "ts_tehran": r[6],
                "ts_utc": r[7],
                "ts_epoch": r[8],
                "price": r[9],
                "volume": r[10],
                "underlying_price": r[11],
                "underlying_ts_utc": r[12],
                "underlying_ts_epoch": r[13],
                "underlying_n_tran": r[14],
                "moneyness_status": r[15],
            }
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return matched_records


def build_ohlcv_candles(
    settings: Optional[Settings] = None,
    timeframes: Optional[Iterable[str]] = None,
    timeframe: Optional[str] = None,
    ins_code: Optional[str] = None,
    d_even: Optional[int] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Stage 5.2: Multi-Timeframe OHLCV Candles with Sparse Forward-Fill.
    Supports timeframes: "1m" (60s), "5m" (300s), "15m" (900s), "1h" (3600s), and "1d" (daily).
    - Intraday intervals generate a continuous grid of buckets between the day's first trade bucket
      and last trade bucket for each (ins_code, d_even), forward-filling sparse buckets with
      volume=0, trade_count=0, close_ffill=previous_close_ffill, is_sparse=1.
    - "1d" builds daily candles from `clean_daily`.
    Persists to SQLite `ohlcv_candles` and exports to `data/processed/ohlcv_{timeframe}.jsonl`.
    """
    cfg = settings or get_settings()
    cfg.ensure_dirs()
    _init_stage5_tables(cfg)

    if timeframe is not None:
        tf_list = [str(timeframe)]
    elif timeframes is not None:
        tf_list = [str(tf) for tf in timeframes]
    else:
        tf_list = list(SUPPORTED_TIMEFRAMES)

    for tf in tf_list:
        if tf not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe '{tf}'. Expected one of {SUPPORTED_TIMEFRAMES}.")

    # Fetch valid ticks grouped by (ins_code, d_even)
    tick_clauses = ["canceled = 0"]
    tick_params: List[Any] = []
    if ins_code is not None:
        tick_clauses.append("ins_code = ?")
        tick_params.append(str(ins_code))
    if d_even is not None:
        tick_clauses.append("d_even = ?")
        tick_params.append(int(d_even))

    with sqlite3.connect(cfg.state_db_path) as conn:
        tick_rows = conn.execute(
            f"""
            SELECT ins_code, d_even, h_even, n_tran, ts_epoch, p_tran, q_tit_tran
            FROM clean_ticks
            WHERE {' AND '.join(tick_clauses)}
            ORDER BY ins_code ASC, d_even ASC, h_even ASC, n_tran ASC
            """,
            tick_params,
        ).fetchall()

        daily_clauses = ["d_even >= ?"]
        daily_params: List[Any] = [int(cfg.tsetmc_start_date)]
        if ins_code is not None:
            daily_clauses.append("ins_code = ?")
            daily_params.append(str(ins_code))
        if d_even is not None:
            daily_clauses.append("d_even = ?")
            daily_params.append(int(d_even))

        daily_rows = conn.execute(
            f"""
            SELECT ins_code, d_even, ts_tehran, ts_utc, ts_epoch,
                   price_first, price_max, price_min, p_closing, p_dr_cot_val,
                   z_tot_tran, q_tot_tran5j, q_tot_cap
            FROM clean_daily
            WHERE {' AND '.join(daily_clauses)}
            ORDER BY ins_code ASC, d_even ASC
            """,
            daily_params,
        ).fetchall()

    # Group ticks by (ins_code, d_even)
    grouped_ticks: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
    for r in tick_rows:
        key = (str(r[0]), int(r[1]))
        grouped_ticks.setdefault(key, []).append(
            {
                "h_even": int(r[2]),
                "n_tran": int(r[3]),
                "ts_epoch": int(r[4]),
                "p_tran": float(r[5]),
                "q_tit_tran": float(r[6]),
            }
        )

    result_by_tf: Dict[str, List[Dict[str, Any]]] = {}

    for tf in tf_list:
        tf_candles: List[Dict[str, Any]] = []
        if tf in TIMEFRAME_SECONDS:
            interval_sec = TIMEFRAME_SECONDS[tf]
            for (code, day_val), day_ticks in sorted(grouped_ticks.items()):
                if not day_ticks:
                    continue
                buckets: Dict[int, List[Dict[str, Any]]] = {}
                for t in day_ticks:
                    b_epoch = _align_bucket_epoch(t["ts_epoch"], interval_sec)
                    buckets.setdefault(b_epoch, []).append(t)

                first_bucket = min(buckets.keys())
                last_bucket = max(buckets.keys())
                prev_close_ffill = float(day_ticks[0]["p_tran"])

                for b_epoch in range(first_bucket, last_bucket + 1, interval_sec):
                    b_ts_tehran, b_ts_utc = _epoch_to_iso_pair(b_epoch)
                    b_ticks = buckets.get(b_epoch)
                    if b_ticks:
                        o_val = float(b_ticks[0]["p_tran"])
                        h_val = max(float(x["p_tran"]) for x in b_ticks)
                        l_val = min(float(x["p_tran"]) for x in b_ticks)
                        c_val = float(b_ticks[-1]["p_tran"])
                        vol_val = sum(float(x["q_tit_tran"]) for x in b_ticks)
                        val_val = sum(float(x["p_tran"]) * float(x["q_tit_tran"]) for x in b_ticks)
                        cnt_val = len(b_ticks)
                        prev_close_ffill = c_val
                        is_sparse = 0
                    else:
                        o_val = prev_close_ffill
                        h_val = prev_close_ffill
                        l_val = prev_close_ffill
                        c_val = prev_close_ffill
                        vol_val = 0.0
                        val_val = 0.0
                        cnt_val = 0
                        is_sparse = 1

                    tf_candles.append(
                        {
                            "ins_code": code,
                            "timeframe": tf,
                            "d_even": day_val,
                            "bucket_epoch": b_epoch,
                            "bucket_ts_tehran": b_ts_tehran,
                            "bucket_ts_utc": b_ts_utc,
                            "open": o_val,
                            "high": h_val,
                            "low": l_val,
                            "close": c_val,
                            "last_price": c_val,
                            "close_ffill": prev_close_ffill,
                            "volume": vol_val,
                            "value": val_val,
                            "trade_count": cnt_val,
                            "is_sparse": is_sparse,
                        }
                    )
        elif tf == "1d":
            prev_ffill_by_ins: Dict[str, float] = {}
            for r in daily_rows:
                code = str(r[0])
                day_val = int(r[1])
                ts_tehran = str(r[2])
                ts_utc = str(r[3])
                ts_epoch = int(r[4])
                p_first = float(r[5])
                p_max = float(r[6])
                p_min = float(r[7])
                p_closing = float(r[8])
                p_last = float(r[9])
                z_tran = int(r[10])
                q_vol = float(r[11])
                q_cap = float(r[12])

                if z_tran > 0:
                    o_val = p_first if p_first > 0 else p_closing
                    h_val = p_max if p_max > 0 else p_closing
                    l_val = p_min if p_min > 0 else p_closing
                    c_val = p_closing
                    last_val = p_last if p_last > 0 else p_closing
                    ffill_val = p_closing
                    prev_ffill_by_ins[code] = ffill_val
                    is_sparse = 0
                else:
                    ffill_val = prev_ffill_by_ins.get(code, p_closing)
                    o_val = ffill_val
                    h_val = ffill_val
                    l_val = ffill_val
                    c_val = ffill_val
                    last_val = p_last if p_last > 0 else ffill_val
                    prev_ffill_by_ins[code] = ffill_val
                    q_vol = 0.0
                    q_cap = 0.0
                    is_sparse = 1

                tf_candles.append(
                    {
                        "ins_code": code,
                        "timeframe": "1d",
                        "d_even": day_val,
                        "bucket_epoch": ts_epoch,
                        "bucket_ts_tehran": ts_tehran,
                        "bucket_ts_utc": ts_utc,
                        "open": o_val,
                        "high": h_val,
                        "low": l_val,
                        "close": c_val,
                        "last_price": last_val,
                        "close_ffill": ffill_val,
                        "volume": q_vol,
                        "value": q_cap,
                        "trade_count": z_tran,
                        "is_sparse": is_sparse,
                    }
                )

        # Save to SQLite ohlcv_candles
        with sqlite3.connect(cfg.state_db_path) as conn:
            if tf_candles:
                conn.executemany(
                    """
                    INSERT INTO ohlcv_candles (
                        ins_code, timeframe, d_even, bucket_epoch,
                        bucket_ts_tehran, bucket_ts_utc,
                        open, high, low, close, last_price, close_ffill,
                        volume, value, trade_count, is_sparse
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ins_code, timeframe, bucket_epoch) DO UPDATE SET
                        d_even = excluded.d_even,
                        bucket_ts_tehran = excluded.bucket_ts_tehran,
                        bucket_ts_utc = excluded.bucket_ts_utc,
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        last_price = excluded.last_price,
                        close_ffill = excluded.close_ffill,
                        volume = excluded.volume,
                        value = excluded.value,
                        trade_count = excluded.trade_count,
                        is_sparse = excluded.is_sparse
                    """,
                    [
                        (
                            c["ins_code"],
                            c["timeframe"],
                            c["d_even"],
                            c["bucket_epoch"],
                            c["bucket_ts_tehran"],
                            c["bucket_ts_utc"],
                            c["open"],
                            c["high"],
                            c["low"],
                            c["close"],
                            c["last_price"],
                            c["close_ffill"],
                            c["volume"],
                            c["value"],
                            c["trade_count"],
                            c["is_sparse"],
                        )
                        for c in tf_candles
                    ],
                )
                conn.commit()

        # Export JSONL file data/processed/ohlcv_{timeframe}.jsonl
        jsonl_path = cfg.processed_dir / f"ohlcv_{tf}.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_path.open("w", encoding="utf-8") as f:
            for c in tf_candles:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        result_by_tf[tf] = tf_candles

    return result_by_tf


def build_option_chain(
    ua_ins_code: str,
    d_even: Optional[int] = None,
    settings: Optional[Settings] = None,
    include_expired: bool = True,
) -> List[Dict[str, Any]]:
    """
    Stage 5.3: Historical & Current Option Chain Builder.
    Given ua_ins_code and d_even (or latest trading date), returns option chain rows
    grouped and sorted by (end_date ASC, strike_price ASC) with:
      - dte: max(0, (end_dt - trade_dt).days)
      - underlying_price on d_even
      - Call side (call_ins_code, call_symbol, call_close, call_last, call_volume, call_trades, call_bid, call_ask, call_moneyness)
      - Put side (put_ins_code, put_symbol, put_close, put_last, put_volume, put_trades, put_bid, put_ask, put_moneyness)
    """
    cfg = settings or get_settings()
    cfg.ensure_dirs()
    _init_stage5_tables(cfg)

    ua_code = str(ua_ins_code)
    opt_meta = _load_option_metadata_map(cfg)
    ua_options = [m for m in opt_meta.values() if m["ua_ins_code"] == ua_code]

    with sqlite3.connect(cfg.state_db_path) as conn:
        if d_even is None:
            row = conn.execute(
                "SELECT MAX(d_even) FROM clean_daily WHERE ins_code = ? AND z_tot_tran > 0",
                (ua_code,),
            ).fetchone()
            target_date = int(row[0]) if row and row[0] else 20261107
        else:
            target_date = int(d_even)

        ua_daily_row = conn.execute(
            """
            SELECT p_closing, p_dr_cot_val
            FROM clean_daily
            WHERE ins_code = ? AND d_even <= ?
            ORDER BY d_even DESC
            LIMIT 1
            """,
            (ua_code, target_date),
        ).fetchone()

        if ua_daily_row:
            p_close, p_last = float(ua_daily_row[0]), float(ua_daily_row[1])
            underlying_price = p_last if p_last > 0 else p_close
        else:
            underlying_price = 0.0

        # Load daily stats for all option contracts of this underlying on target_date
        opt_codes = [m["ins_code"] for m in ua_options]
        daily_stats: Dict[str, Dict[str, Any]] = {}
        if opt_codes:
            placeholders = ",".join("?" for _ in opt_codes)
            rows = conn.execute(
                f"""
                SELECT ins_code, p_closing, p_dr_cot_val, q_tot_tran5j, z_tot_tran
                FROM clean_daily
                WHERE d_even = ? AND ins_code IN ({placeholders})
                """,
                [target_date, *opt_codes],
            ).fetchall()
            for r in rows:
                daily_stats[str(r[0])] = {
                    "close": float(r[1]),
                    "last": float(r[2]),
                    "volume": float(r[3]),
                    "trades": int(r[4]),
                }

    # Load best bid/ask from option_market_watch fixture if available
    bid_ask_map: Dict[str, Tuple[float, float]] = {}
    watch_file = cfg.fixtures_dir / "option_market_watch.json"
    watch_payload = (
        json.loads(watch_file.read_text(encoding="utf-8"))
        if watch_file.is_file()
        else build_option_market_watch_fixture()
    )
    for w_row in watch_payload.get("instrumentOptMarketWatch", []):
        c_code = str(w_row.get("insCode_C") or "")
        p_code = str(w_row.get("insCode_P") or "")
        if c_code:
            bid_ask_map[c_code] = (
                float(w_row.get("pMeDem_C") or 0.0),
                float(w_row.get("pMeOf_C") or 0.0),
            )
        if p_code:
            bid_ask_map[p_code] = (
                float(w_row.get("pMeDem_P") or 0.0),
                float(w_row.get("pMeOf_P") or 0.0),
            )

    # Pair Call and Put contracts by (end_date, strike_price)
    grouped_pairs: Dict[Tuple[int, float], Dict[str, Any]] = {}
    for m in ua_options:
        end_date = int(m["end_date"])
        if not include_expired and end_date < target_date:
            continue
        strike = float(m["strike_price"])
        key = (end_date, strike)
        pair = grouped_pairs.setdefault(
            key,
            {
                "end_date": end_date,
                "strike_price": strike,
                "contract_size": int(m["contract_size"]),
                "call": None,
                "put": None,
            },
        )
        if m["instrument_type"] == "call":
            pair["call"] = m
        elif m["instrument_type"] == "put":
            pair["put"] = m

    trade_dt = _int_date_to_date(target_date)
    chain_rows: List[Dict[str, Any]] = []

    for (end_date, strike), pair in sorted(grouped_pairs.items(), key=lambda x: (x[0][0], x[0][1])):
        end_dt = _int_date_to_date(end_date)
        dte = max(0, (end_dt - trade_dt).days)

        c_meta = pair["call"]
        p_meta = pair["put"]

        c_code = c_meta["ins_code"] if c_meta else None
        c_sym = c_meta["symbol"] if c_meta else None
        c_stat = daily_stats.get(c_code, {}) if c_code else {}
        c_bid, c_ask = bid_ask_map.get(c_code, (0.0, 0.0)) if c_code else (0.0, 0.0)
        c_moneyness = (
            classify_moneyness("call", underlying_price, strike) if c_meta else None
        )

        p_code = p_meta["ins_code"] if p_meta else None
        p_sym = p_meta["symbol"] if p_meta else None
        p_stat = daily_stats.get(p_code, {}) if p_code else {}
        p_bid, p_ask = bid_ask_map.get(p_code, (0.0, 0.0)) if p_code else (0.0, 0.0)
        p_moneyness = (
            classify_moneyness("put", underlying_price, strike) if p_meta else None
        )

        chain_rows.append(
            {
                "ua_ins_code": ua_code,
                "d_even": target_date,
                "end_date": end_date,
                "dte": dte,
                "strike_price": strike,
                "contract_size": pair["contract_size"],
                "underlying_price": underlying_price,
                "call_ins_code": c_code,
                "call_symbol": c_sym,
                "call_close": float(c_stat.get("close", 0.0)),
                "call_last": float(c_stat.get("last", 0.0)),
                "call_volume": float(c_stat.get("volume", 0.0)),
                "call_trades": int(c_stat.get("trades", 0)),
                "call_bid": c_bid,
                "call_ask": c_ask,
                "call_moneyness": c_moneyness,
                "put_ins_code": p_code,
                "put_symbol": p_sym,
                "put_close": float(p_stat.get("close", 0.0)),
                "put_last": float(p_stat.get("last", 0.0)),
                "put_volume": float(p_stat.get("volume", 0.0)),
                "put_trades": int(p_stat.get("trades", 0)),
                "put_bid": p_bid,
                "put_ask": p_ask,
                "put_moneyness": p_moneyness,
            }
        )

    return chain_rows
