"""Stage 4: Cleaning, +03:30 Timestamp Standardization, Deterministic Sorting & Reconciliation."""
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.config import Settings, get_settings
from src.models import ClosingPriceDailyResponse, TradeHistoryResponse
from src.stage2_3_crawler_storage import RawStorageManager

# CRITICAL NO-DST RULE:
# Iran permanently abolished Daylight Saving Time (DST) in 1402 SH (March 2023).
# Always use a fixed +03:30 offset and NEVER use OS ZoneInfo("Asia/Tehran").
IRAN_STANDARD_TZ = timezone(timedelta(hours=3, minutes=30), name="IRST")


def parse_tsetmc_timestamp(d_even: int, h_even: int) -> Tuple[str, str, int]:
    """
    Convert TSETMC integer date (YYYYMMDD) and time (HHMMSS / HMMSS / 0) into:
      - ts_tehran_iso: ISO-8601 string with fixed +03:30 offset (e.g. '2023-05-24T09:00:05+03:30')
      - ts_utc_iso: ISO-8601 UTC string with 'Z' suffix (e.g. '2023-05-24T05:30:05Z')
      - ts_epoch: integer Unix epoch seconds (e.g. 1684906205)
    """
    d_str = f"{int(d_even):08d}"
    year = int(d_str[0:4])
    month = int(d_str[4:6])
    day = int(d_str[6:8])

    h_val = max(0, int(h_even))
    h_str = f"{h_val:06d}"
    hour = int(h_str[0:2])
    minute = int(h_str[2:4])
    second = int(h_str[4:6])

    dt_tehran = datetime(year, month, day, hour, minute, second, tzinfo=IRAN_STANDARD_TZ)
    dt_utc = dt_tehran.astimezone(timezone.utc)

    ts_tehran_iso = dt_tehran.isoformat()
    ts_utc_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    ts_epoch = int(dt_utc.timestamp())
    return ts_tehran_iso, ts_utc_iso, ts_epoch


class TickCleaner:
    """
    Stage 4 Cleaner:
    - Reads raw daily and tick .json.gz files via RawStorageManager.
    - Injects insCode and dEven into raw tradeHistory records (replacing None and 0).
    - Standardizes timestamps with fixed +03:30 offset (no DST).
    - Deterministically sorts intra-second trades by (dEven ASC, hEven ASC, nTran ASC).
    - Separates/flags canceled trades (canceled != 0) into `canceled_ticks` audit table
      and stores cleaned rows in `clean_daily` and `clean_ticks`.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        storage: Optional[RawStorageManager] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.storage = storage or RawStorageManager(self.settings)
        self._init_db()

    def _init_db(self) -> None:
        self.settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clean_daily (
                    ins_code TEXT NOT NULL,
                    d_even INTEGER NOT NULL,
                    h_even INTEGER NOT NULL,
                    ts_tehran TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    ts_epoch INTEGER NOT NULL,
                    price_first REAL NOT NULL,
                    price_max REAL NOT NULL,
                    price_min REAL NOT NULL,
                    p_closing REAL NOT NULL,
                    p_dr_cot_val REAL NOT NULL,
                    price_yesterday REAL NOT NULL,
                    price_change REAL NOT NULL,
                    z_tot_tran INTEGER NOT NULL,
                    q_tot_tran5j REAL NOT NULL,
                    q_tot_cap REAL NOT NULL,
                    last INTEGER NOT NULL DEFAULT 0,
                    id INTEGER NOT NULL DEFAULT 0,
                    i_close INTEGER NOT NULL DEFAULT 0,
                    y_close INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (ins_code, d_even)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clean_ticks (
                    ins_code TEXT NOT NULL,
                    d_even INTEGER NOT NULL,
                    n_tran INTEGER NOT NULL,
                    h_even INTEGER NOT NULL,
                    ts_tehran TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    ts_epoch INTEGER NOT NULL,
                    p_tran REAL NOT NULL,
                    q_tit_tran REAL NOT NULL,
                    canceled INTEGER NOT NULL DEFAULT 0,
                    q_tit_ng_j INTEGER NOT NULL DEFAULT 0,
                    i_sens_var_p TEXT NOT NULL DEFAULT '',
                    p_ph_sea_cot_j REAL NOT NULL DEFAULT 0.0,
                    p_pb_sea_cot_j REAL NOT NULL DEFAULT 0.0,
                    i_anu_tran INTEGER NOT NULL DEFAULT 0,
                    xq_var_pj_dr_prf REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (ins_code, d_even, n_tran)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canceled_ticks (
                    ins_code TEXT NOT NULL,
                    d_even INTEGER NOT NULL,
                    n_tran INTEGER NOT NULL,
                    h_even INTEGER NOT NULL,
                    ts_tehran TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    ts_epoch INTEGER NOT NULL,
                    p_tran REAL NOT NULL,
                    q_tit_tran REAL NOT NULL,
                    canceled INTEGER NOT NULL,
                    q_tit_ng_j INTEGER NOT NULL DEFAULT 0,
                    i_sens_var_p TEXT NOT NULL DEFAULT '',
                    p_ph_sea_cot_j REAL NOT NULL DEFAULT 0.0,
                    p_pb_sea_cot_j REAL NOT NULL DEFAULT 0.0,
                    i_anu_tran INTEGER NOT NULL DEFAULT 0,
                    xq_var_pj_dr_prf REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (ins_code, d_even, n_tran)
                )
                """
            )
            conn.commit()

    def clean_daily(
        self, ins_code: str, raw_payload: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Clean and persist daily closing price records for an instrument."""
        payload = raw_payload if raw_payload is not None else self.storage.read_daily_raw(ins_code)
        parsed = ClosingPriceDailyResponse.parse_obj(payload)
        sorted_items = sorted(parsed.closingPriceDaily, key=lambda x: int(x.dEven))

        cleaned_rows: List[Dict[str, Any]] = []
        for item in sorted_items:
            d_val = int(item.dEven)
            h_val = int(item.hEven)
            ts_tehran, ts_utc, ts_epoch = parse_tsetmc_timestamp(d_val, h_val)
            row = {
                "ins_code": str(ins_code),
                "insCode": str(ins_code),
                "d_even": d_val,
                "dEven": d_val,
                "h_even": h_val,
                "hEven": h_val,
                "ts_tehran": ts_tehran,
                "ts_utc": ts_utc,
                "ts_epoch": ts_epoch,
                "price_first": float(item.priceFirst),
                "price_max": float(item.priceMax),
                "price_min": float(item.priceMin),
                "p_closing": float(item.pClosing),
                "p_dr_cot_val": float(item.pDrCotVal),
                "price_yesterday": float(item.priceYesterday),
                "price_change": float(item.priceChange),
                "z_tot_tran": int(round(float(item.zTotTran))),
                "q_tot_tran5j": float(item.qTotTran5J),
                "q_tot_cap": float(item.qTotCap),
                "last": 1 if item.last else 0,
                "id": int(item.id),
                "i_close": 1 if item.iClose else 0,
                "y_close": 1 if item.yClose else 0,
            }
            cleaned_rows.append(row)

        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.executemany(
                """
                INSERT INTO clean_daily (
                    ins_code, d_even, h_even, ts_tehran, ts_utc, ts_epoch,
                    price_first, price_max, price_min, p_closing, p_dr_cot_val,
                    price_yesterday, price_change, z_tot_tran, q_tot_tran5j, q_tot_cap,
                    last, id, i_close, y_close
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ins_code, d_even) DO UPDATE SET
                    h_even = excluded.h_even,
                    ts_tehran = excluded.ts_tehran,
                    ts_utc = excluded.ts_utc,
                    ts_epoch = excluded.ts_epoch,
                    price_first = excluded.price_first,
                    price_max = excluded.price_max,
                    price_min = excluded.price_min,
                    p_closing = excluded.p_closing,
                    p_dr_cot_val = excluded.p_dr_cot_val,
                    price_yesterday = excluded.price_yesterday,
                    price_change = excluded.price_change,
                    z_tot_tran = excluded.z_tot_tran,
                    q_tot_tran5j = excluded.q_tot_tran5j,
                    q_tot_cap = excluded.q_tot_cap,
                    last = excluded.last,
                    id = excluded.id,
                    i_close = excluded.i_close,
                    y_close = excluded.y_close
                """,
                [
                    (
                        r["ins_code"],
                        r["d_even"],
                        r["h_even"],
                        r["ts_tehran"],
                        r["ts_utc"],
                        r["ts_epoch"],
                        r["price_first"],
                        r["price_max"],
                        r["price_min"],
                        r["p_closing"],
                        r["p_dr_cot_val"],
                        r["price_yesterday"],
                        r["price_change"],
                        r["z_tot_tran"],
                        r["q_tot_tran5j"],
                        r["q_tot_cap"],
                        r["last"],
                        r["id"],
                        r["i_close"],
                        r["y_close"],
                    )
                    for r in cleaned_rows
                ],
            )
            conn.commit()

        return cleaned_rows

    def clean_ticks_day(
        self,
        ins_code: str,
        d_even: int,
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Clean and persist a single instrument-day of tick data:
        - Injects ins_code and d_even (replacing None and 0).
        - Sorts deterministically by (dEven ASC, hEven ASC, nTran ASC).
        - Separates valid (canceled == 0) and canceled (canceled != 0) trades.
        """
        payload = (
            raw_payload
            if raw_payload is not None
            else self.storage.read_ticks_raw(ins_code, int(d_even))
        )
        parsed = TradeHistoryResponse.parse_obj(payload)
        injected_ins = str(ins_code)
        injected_date = int(d_even)

        all_ticks: List[Dict[str, Any]] = []
        for item in parsed.tradeHistory:
            h_val = int(item.hEven)
            n_val = int(item.nTran)
            ts_tehran, ts_utc, ts_epoch = parse_tsetmc_timestamp(injected_date, h_val)
            row = {
                "ins_code": injected_ins,
                "insCode": injected_ins,
                "d_even": injected_date,
                "dEven": injected_date,
                "n_tran": n_val,
                "nTran": n_val,
                "h_even": h_val,
                "hEven": h_val,
                "ts_tehran": ts_tehran,
                "ts_utc": ts_utc,
                "ts_epoch": ts_epoch,
                "p_tran": float(item.pTran),
                "pTran": float(item.pTran),
                "q_tit_tran": float(item.qTitTran),
                "qTitTran": float(item.qTitTran),
                "canceled": int(item.canceled),
                "q_tit_ng_j": int(item.qTitNgJ),
                "i_sens_var_p": str(item.iSensVarP),
                "p_ph_sea_cot_j": float(item.pPhSeaCotJ),
                "p_pb_sea_cot_j": float(item.pPbSeaCotJ),
                "i_anu_tran": int(item.iAnuTran),
                "xq_var_pj_dr_prf": float(item.xqVarPJDrPRf),
            }
            all_ticks.append(row)

        # Deterministic intra-second sorting: (dEven ASC, hEven ASC, nTran ASC)
        all_ticks.sort(key=lambda r: (r["d_even"], r["h_even"], r["n_tran"]))

        valid_ticks = [r for r in all_ticks if r["canceled"] == 0]
        canceled_ticks = [r for r in all_ticks if r["canceled"] != 0]

        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                "DELETE FROM clean_ticks WHERE ins_code = ? AND d_even = ?",
                (injected_ins, injected_date),
            )
            conn.execute(
                "DELETE FROM canceled_ticks WHERE ins_code = ? AND d_even = ?",
                (injected_ins, injected_date),
            )
            if all_ticks:
                conn.executemany(
                    """
                    INSERT INTO clean_ticks (
                        ins_code, d_even, n_tran, h_even, ts_tehran, ts_utc, ts_epoch,
                        p_tran, q_tit_tran, canceled, q_tit_ng_j, i_sens_var_p,
                        p_ph_sea_cot_j, p_pb_sea_cot_j, i_anu_tran, xq_var_pj_dr_prf
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r["ins_code"],
                            r["d_even"],
                            r["n_tran"],
                            r["h_even"],
                            r["ts_tehran"],
                            r["ts_utc"],
                            r["ts_epoch"],
                            r["p_tran"],
                            r["q_tit_tran"],
                            r["canceled"],
                            r["q_tit_ng_j"],
                            r["i_sens_var_p"],
                            r["p_ph_sea_cot_j"],
                            r["p_pb_sea_cot_j"],
                            r["i_anu_tran"],
                            r["xq_var_pj_dr_prf"],
                        )
                        for r in all_ticks
                    ],
                )
            if canceled_ticks:
                conn.executemany(
                    """
                    INSERT INTO canceled_ticks (
                        ins_code, d_even, n_tran, h_even, ts_tehran, ts_utc, ts_epoch,
                        p_tran, q_tit_tran, canceled, q_tit_ng_j, i_sens_var_p,
                        p_ph_sea_cot_j, p_pb_sea_cot_j, i_anu_tran, xq_var_pj_dr_prf
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r["ins_code"],
                            r["d_even"],
                            r["n_tran"],
                            r["h_even"],
                            r["ts_tehran"],
                            r["ts_utc"],
                            r["ts_epoch"],
                            r["p_tran"],
                            r["q_tit_tran"],
                            r["canceled"],
                            r["q_tit_ng_j"],
                            r["i_sens_var_p"],
                            r["p_ph_sea_cot_j"],
                            r["p_pb_sea_cot_j"],
                            r["i_anu_tran"],
                            r["xq_var_pj_dr_prf"],
                        )
                        for r in canceled_ticks
                    ],
                )
            conn.commit()

        return {
            "ins_code": injected_ins,
            "d_even": injected_date,
            "valid_ticks": valid_ticks,
            "canceled_ticks": canceled_ticks,
            "all_ticks": all_ticks,
        }

    def clean_all(self, ins_codes: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Clean all raw daily and tick files stored in RawStorageManager."""
        allowed_codes = {str(c) for c in ins_codes} if ins_codes is not None else None

        daily_manifests = self.storage.list_manifest(artifact_type="daily")
        tick_manifests = self.storage.list_manifest(artifact_type="ticks")

        daily_instruments_cleaned = 0
        daily_rows_cleaned = 0
        for entry in daily_manifests:
            code = entry["ins_code"]
            if allowed_codes is not None and code not in allowed_codes:
                continue
            if self.storage.daily_file_path(code).is_file():
                rows = self.clean_daily(code)
                daily_instruments_cleaned += 1
                daily_rows_cleaned += len(rows)

        tick_days_cleaned = 0
        valid_ticks_count = 0
        canceled_ticks_count = 0
        for entry in tick_manifests:
            code = entry["ins_code"]
            d_even = int(entry["d_even"])
            if allowed_codes is not None and code not in allowed_codes:
                continue
            if self.storage.ticks_file_path(code, d_even).is_file():
                res = self.clean_ticks_day(code, d_even)
                tick_days_cleaned += 1
                valid_ticks_count += len(res["valid_ticks"])
                canceled_ticks_count += len(res["canceled_ticks"])

        return {
            "daily_instruments_cleaned": daily_instruments_cleaned,
            "daily_rows_cleaned": daily_rows_cleaned,
            "tick_days_cleaned": tick_days_cleaned,
            "valid_ticks_count": valid_ticks_count,
            "canceled_ticks_count": canceled_ticks_count,
        }

    def get_clean_ticks(
        self,
        ins_code: str,
        d_even: Optional[int] = None,
        include_canceled: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch cleaned ticks ordered deterministically by (d_even ASC, h_even ASC, n_tran ASC)."""
        clauses = ["ins_code = ?"]
        params: List[Any] = [str(ins_code)]
        if d_even is not None:
            clauses.append("d_even = ?")
            params.append(int(d_even))
        if not include_canceled:
            clauses.append("canceled = 0")

        where_sql = " AND ".join(clauses)
        query = f"""
            SELECT ins_code, d_even, n_tran, h_even, ts_tehran, ts_utc, ts_epoch,
                   p_tran, q_tit_tran, canceled, q_tit_ng_j, i_sens_var_p,
                   p_ph_sea_cot_j, p_pb_sea_cot_j, i_anu_tran, xq_var_pj_dr_prf
            FROM clean_ticks
            WHERE {where_sql}
            ORDER BY d_even ASC, h_even ASC, n_tran ASC
        """
        with sqlite3.connect(self.settings.state_db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "ins_code": r[0],
                "insCode": r[0],
                "d_even": r[1],
                "dEven": r[1],
                "n_tran": r[2],
                "nTran": r[2],
                "h_even": r[3],
                "hEven": r[3],
                "ts_tehran": r[4],
                "ts_utc": r[5],
                "ts_epoch": r[6],
                "p_tran": r[7],
                "pTran": r[7],
                "q_tit_tran": r[8],
                "qTitTran": r[8],
                "canceled": r[9],
                "q_tit_ng_j": r[10],
                "i_sens_var_p": r[11],
                "p_ph_sea_cot_j": r[12],
                "p_pb_sea_cot_j": r[13],
                "i_anu_tran": r[14],
                "xq_var_pj_dr_prf": r[15],
            }
            for r in rows
        ]

    def get_canceled_ticks(
        self,
        ins_code: Optional[str] = None,
        d_even: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch canceled ticks from the audit table ordered by (d_even ASC, h_even ASC, n_tran ASC)."""
        clauses: List[str] = []
        params: List[Any] = []
        if ins_code is not None:
            clauses.append("ins_code = ?")
            params.append(str(ins_code))
        if d_even is not None:
            clauses.append("d_even = ?")
            params.append(int(d_even))

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT ins_code, d_even, n_tran, h_even, ts_tehran, ts_utc, ts_epoch,
                   p_tran, q_tit_tran, canceled
            FROM canceled_ticks
            {where_sql}
            ORDER BY d_even ASC, h_even ASC, n_tran ASC
        """
        with sqlite3.connect(self.settings.state_db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "ins_code": r[0],
                "insCode": r[0],
                "d_even": r[1],
                "dEven": r[1],
                "n_tran": r[2],
                "nTran": r[2],
                "h_even": r[3],
                "hEven": r[3],
                "ts_tehran": r[4],
                "ts_utc": r[5],
                "ts_epoch": r[6],
                "p_tran": r[7],
                "pTran": r[7],
                "q_tit_tran": r[8],
                "qTitTran": r[8],
                "canceled": r[9],
            }
            for r in rows
        ]


class ReconciliationEngine:
    """
    Stage 4 Data Quality & Reconciliation Engine:
    Compares each traded day (zTotTran > 0 and dEven >= 20230321) in `clean_daily`
    against valid ticks (canceled == 0) in `clean_ticks`, persists `reconciliation_report`,
    and verifies the >= 98% acceptance target.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._init_db()

    def _init_db(self) -> None:
        self.settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reconciliation_report (
                    ins_code TEXT NOT NULL,
                    d_even INTEGER NOT NULL,
                    daily_trade_count INTEGER NOT NULL,
                    tick_valid_count INTEGER NOT NULL,
                    tick_canceled_count INTEGER NOT NULL,
                    daily_volume REAL NOT NULL,
                    tick_valid_volume REAL NOT NULL,
                    volume_diff REAL NOT NULL,
                    trade_count_diff INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (ins_code, d_even)
                )
                """
            )
            conn.commit()

    def reconcile(self, start_date: Optional[int] = None) -> Dict[str, Any]:
        """
        Reconcile all traded days (z_tot_tran > 0 and d_even >= start_date) in `clean_daily`
        against `clean_ticks` and persist results to `reconciliation_report`.
        """
        min_date = int(start_date if start_date is not None else self.settings.tsetmc_start_date)

        with sqlite3.connect(self.settings.state_db_path) as conn:
            daily_rows = conn.execute(
                """
                SELECT ins_code, d_even, z_tot_tran, q_tot_tran5j
                FROM clean_daily
                WHERE d_even >= ? AND z_tot_tran > 0
                ORDER BY ins_code ASC, d_even ASC
                """,
                (min_date,),
            ).fetchall()

            tick_agg_rows = conn.execute(
                """
                SELECT
                    ins_code,
                    d_even,
                    SUM(CASE WHEN canceled = 0 THEN 1 ELSE 0 END) AS valid_count,
                    SUM(CASE WHEN canceled = 0 THEN q_tit_tran ELSE 0.0 END) AS valid_volume,
                    SUM(CASE WHEN canceled != 0 THEN 1 ELSE 0 END) AS canceled_count,
                    COUNT(*) AS total_rows
                FROM clean_ticks
                WHERE d_even >= ?
                GROUP BY ins_code, d_even
                """,
                (min_date,),
            ).fetchall()

        tick_map: Dict[Tuple[str, int], Tuple[int, float, int, int]] = {
            (str(r[0]), int(r[1])): (
                int(r[2] or 0),
                float(r[3] or 0.0),
                int(r[4] or 0),
                int(r[5] or 0),
            )
            for r in tick_agg_rows
        }

        report_rows: List[Dict[str, Any]] = []
        matched_days = 0
        mismatched_days = 0
        missing_days = 0

        for ins_code, d_even, z_tot_tran, q_tot_tran5j in daily_rows:
            code_str = str(ins_code)
            d_int = int(d_even)
            daily_trade_count = int(z_tot_tran)
            daily_volume = float(q_tot_tran5j)

            tick_stats = tick_map.get((code_str, d_int))
            if tick_stats is None or tick_stats[3] == 0:
                tick_valid_count = 0
                tick_valid_volume = 0.0
                tick_canceled_count = 0
                status = "MISSING_TICKS"
                missing_days += 1
            else:
                tick_valid_count, tick_valid_volume, tick_canceled_count, _ = tick_stats
                if (
                    daily_trade_count == tick_valid_count
                    and abs(daily_volume - tick_valid_volume) < 1e-3
                ):
                    status = "MATCH"
                    matched_days += 1
                else:
                    status = "MISMATCH"
                    mismatched_days += 1

            volume_diff = round(daily_volume - tick_valid_volume, 4)
            trade_count_diff = daily_trade_count - tick_valid_count

            report_rows.append(
                {
                    "ins_code": code_str,
                    "d_even": d_int,
                    "daily_trade_count": daily_trade_count,
                    "tick_valid_count": tick_valid_count,
                    "tick_canceled_count": tick_canceled_count,
                    "daily_volume": daily_volume,
                    "tick_valid_volume": tick_valid_volume,
                    "volume_diff": volume_diff,
                    "trade_count_diff": trade_count_diff,
                    "status": status,
                }
            )

        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute("DELETE FROM reconciliation_report WHERE d_even >= ?", (min_date,))
            if report_rows:
                conn.executemany(
                    """
                    INSERT INTO reconciliation_report (
                        ins_code, d_even, daily_trade_count, tick_valid_count,
                        tick_canceled_count, daily_volume, tick_valid_volume,
                        volume_diff, trade_count_diff, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r["ins_code"],
                            r["d_even"],
                            r["daily_trade_count"],
                            r["tick_valid_count"],
                            r["tick_canceled_count"],
                            r["daily_volume"],
                            r["tick_valid_volume"],
                            r["volume_diff"],
                            r["trade_count_diff"],
                            r["status"],
                        )
                        for r in report_rows
                    ],
                )
            conn.commit()

        total_traded_days = len(report_rows)
        match_rate_pct = (
            round((matched_days / total_traded_days) * 100.0, 2)
            if total_traded_days > 0
            else 100.0
        )
        meets_98_pct_target = bool(match_rate_pct >= 98.0)

        return {
            "total_traded_days": total_traded_days,
            "matched_days": matched_days,
            "mismatched_days": mismatched_days,
            "missing_days": missing_days,
            "match_rate_pct": match_rate_pct,
            "meets_98_pct_target": meets_98_pct_target,
            "rows": report_rows,
        }

    run_reconciliation = reconcile

