"""Stage 6: FastAPI Backend API & Zero-Dependency ASGI Test Client."""
import asyncio
import json
import sqlite3
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.config import Settings, get_settings
from src.seed import ensure_seeded
from src.stage1_discovery import OptionDiscoveryService, normalize_persian
from src.stage4_cleaning import ReconciliationEngine, TickCleaner
from src.stage5_series import (
    SUPPORTED_TIMEFRAMES,
    build_matched_option_ticks,
    build_ohlcv_candles,
    build_option_chain,
)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>TSETMC Options Market Tick-Data Platform</title>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
    .badge { background: #059669; color: #fff; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 12px; }
    th, td { border-bottom: 1px solid #334155; padding: 8px; text-align: center; }
    th { background: #0f172a; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1 style="margin:0;font-size:22px;">سامانه جامع داده‌های تیک بازار اختیار معامله بورس تهران (TSETMC)</h1>
      <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">Stage 1–6 Pipeline • ASOF JOIN Tick Stream • Multi-Timeframe OHLCV • Quality Reconciliation</p>
    </div>
    <span class="badge">Reconciliation Target ≥ 98%</span>
  </div>
  <div class="grid">
    <div class="card"><h3>API Endpoints</h3><p><a style="color:#38bdf8" href="/api/health">/api/health</a> • <a style="color:#38bdf8" href="/api/underlyings">/api/underlyings</a> • <a style="color:#38bdf8" href="/api/option-chain?ua_ins_code=46348559193224090">/api/option-chain</a> • <a style="color:#38bdf8" href="/api/quality-report">/api/quality-report</a></p></div>
  </div>
</body>
</html>
"""


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cfg = settings or get_settings()

    application = FastAPI(
        title="TSETMC Options Market Tick-Data Platform API",
        version="1.0.0",
        description="Historical & Intraday Tick Data, ASOF JOIN Streams, OHLCV Candles, Option Chains, and Reconciliation API",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    def _on_startup() -> None:
        ensure_seeded(cfg)

    def _ensure_ready() -> None:
        ensure_seeded(cfg)

    @application.get("/", response_class=HTMLResponse)
    def root_dashboard() -> HTMLResponse:
        _ensure_ready()
        return HTMLResponse(content=DASHBOARD_HTML, status_code=200)

    @application.get("/api/health")
    def get_health() -> Dict[str, Any]:
        _ensure_ready()
        with sqlite3.connect(cfg.state_db_path) as conn:
            ua_count = conn.execute(
                "SELECT COUNT(*) FROM instruments WHERE instrument_type = 'underlying'"
            ).fetchone()[0]
            opt_count = conn.execute(
                "SELECT COUNT(*) FROM instruments WHERE instrument_type IN ('call', 'put')"
            ).fetchone()[0]
            total_days = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_report"
            ).fetchone()[0]
            matched_days = conn.execute(
                "SELECT COUNT(*) FROM reconciliation_report WHERE status = 'MATCH'"
            ).fetchone()[0]

        match_rate = round((matched_days / total_days) * 100.0, 2) if total_days > 0 else 100.0
        return {
            "status": "ok",
            "underlyings_count": int(ua_count),
            "options_count": int(opt_count),
            "reconciliation_match_rate": match_rate,
            "meets_98_pct_target": bool(match_rate >= 98.0),
        }

    @application.get("/api/underlyings")
    def list_underlyings() -> Dict[str, Any]:
        _ensure_ready()
        svc = OptionDiscoveryService(cfg)
        underlyings = svc.list_instruments(instrument_type="underlying")

        with sqlite3.connect(cfg.state_db_path) as conn:
            latest_rows = conn.execute(
                """
                SELECT cd.ins_code, cd.d_even, cd.p_closing, cd.p_dr_cot_val
                FROM clean_daily cd
                INNER JOIN (
                    SELECT ins_code, MAX(d_even) AS max_d
                    FROM clean_daily
                    GROUP BY ins_code
                ) m ON cd.ins_code = m.ins_code AND cd.d_even = m.max_d
                """
            ).fetchall()
            opt_counts = conn.execute(
                """
                SELECT ua_ins_code,
                       SUM(CASE WHEN is_expired = 0 THEN 1 ELSE 0 END) AS active_cnt,
                       SUM(CASE WHEN is_expired != 0 THEN 1 ELSE 0 END) AS expired_cnt
                FROM instruments
                WHERE instrument_type IN ('call', 'put') AND ua_ins_code IS NOT NULL
                GROUP BY ua_ins_code
                """
            ).fetchall()

        price_map = {
            str(r[0]): (int(r[1]), float(r[3]) if float(r[3]) > 0 else float(r[2]))
            for r in latest_rows
        }
        opt_map = {str(r[0]): (int(r[1] or 0), int(r[2] or 0)) for r in opt_counts}

        items: List[Dict[str, Any]] = []
        for u in underlyings:
            latest_date, latest_price = price_map.get(u.ins_code, (None, None))
            active_cnt, expired_cnt = opt_map.get(u.ins_code, (0, 0))
            items.append(
                {
                    "ins_code": u.ins_code,
                    "symbol": u.symbol,
                    "full_name": u.full_name,
                    "latest_date": latest_date,
                    "latest_price": latest_price,
                    "active_options_count": active_cnt,
                    "expired_options_count": expired_cnt,
                    "y_val": u.y_val,
                    "cgr_val_cot": u.cgr_val_cot,
                }
            )
        return {"count": len(items), "underlyings": items}

    @application.get("/api/options")
    def list_options(
        ua_ins_code: Optional[str] = Query(default=None),
        option_type: Optional[str] = Query(default=None),
        include_expired: bool = Query(default=True),
        q: Optional[str] = Query(default=None),
    ) -> Dict[str, Any]:
        _ensure_ready()
        svc = OptionDiscoveryService(cfg)
        all_inst = svc.list_instruments()
        options = [r for r in all_inst if r.instrument_type in ("call", "put")]

        if ua_ins_code:
            options = [r for r in options if r.ua_ins_code == str(ua_ins_code)]
        if option_type:
            opt_t = option_type.lower().strip()
            options = [r for r in options if r.instrument_type == opt_t]
        if not include_expired:
            options = [r for r in options if not r.is_expired]
        if q:
            q_norm = normalize_persian(q)
            options = [
                r
                for r in options
                if q_norm in normalize_persian(r.symbol)
                or q_norm in normalize_persian(r.full_name)
                or q_norm in r.ins_code
            ]

        return {
            "count": len(options),
            "options": [r.dict() for r in options],
        }

    @application.get("/api/option-chain")
    def get_option_chain(
        ua_ins_code: str = Query(..., description="Underlying asset insCode"),
        d_even: Optional[int] = Query(default=None, description="Trading date YYYYMMDD"),
        include_expired: bool = Query(default=True),
    ) -> Dict[str, Any]:
        _ensure_ready()
        svc = OptionDiscoveryService(cfg)
        ua_inst = svc.get_instrument(ua_ins_code)
        if ua_inst is None:
            raise HTTPException(status_code=404, detail=f"Underlying instrument {ua_ins_code} not found")

        with sqlite3.connect(cfg.state_db_path) as conn:
            date_rows = conn.execute(
                """
                SELECT DISTINCT d_even
                FROM clean_daily
                WHERE ins_code = ? AND z_tot_tran > 0 AND d_even >= ?
                ORDER BY d_even DESC
                """,
                (ua_ins_code, cfg.tsetmc_start_date),
            ).fetchall()
        available_dates = [int(r[0]) for r in date_rows]

        chain_rows = build_option_chain(
            ua_ins_code=ua_ins_code,
            d_even=d_even,
            settings=cfg,
            include_expired=include_expired,
        )
        effective_date = (
            chain_rows[0]["d_even"]
            if chain_rows
            else (d_even or (available_dates[0] if available_dates else 20261107))
        )
        underlying_price = chain_rows[0]["underlying_price"] if chain_rows else 0.0

        return {
            "ua_ins_code": ua_ins.ins_code if (ua_ins := ua_inst) else ua_ins_code,
            "symbol": ua_inst.symbol,
            "full_name": ua_inst.full_name,
            "d_even": int(effective_date),
            "underlying_price": float(underlying_price),
            "available_dates": available_dates,
            "count": len(chain_rows),
            "chain": chain_rows,
        }

    @application.get("/api/ticks")
    def get_ticks(
        ins_code: str = Query(..., description="Instrument insCode"),
        d_even: Optional[int] = Query(default=None, description="Trading date YYYYMMDD"),
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> Dict[str, Any]:
        _ensure_ready()
        svc = OptionDiscoveryService(cfg)
        inst = svc.get_instrument(ins_code)

        if inst and inst.instrument_type in ("call", "put"):
            clauses = ["ins_code = ?"]
            params: List[Any] = [str(ins_code)]
            if d_even is not None:
                clauses.append("d_even = ?")
                params.append(int(d_even))
            params.append(int(limit))

            with sqlite3.connect(cfg.state_db_path) as conn:
                rows = conn.execute(
                    f"""
                    SELECT ins_code, symbol, ua_ins_code, d_even, h_even, n_tran,
                           ts_tehran, ts_utc, ts_epoch, price, volume,
                           underlying_price, underlying_ts_utc, underlying_ts_epoch,
                           underlying_n_tran, moneyness_status
                    FROM option_ticks_matched
                    WHERE {' AND '.join(clauses)}
                    ORDER BY d_even ASC, h_even ASC, n_tran ASC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()

            if not rows:
                built = build_matched_option_ticks(settings=cfg, ins_code=ins_code, d_even=d_even)
                ticks = built[:limit]
            else:
                ticks = [
                    {
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
                    for r in rows
                ]
            return {
                "ins_code": ins_code,
                "instrument_type": inst.instrument_type,
                "count": len(ticks),
                "ticks": ticks,
            }

        cleaner = TickCleaner(settings=cfg)
        raw_ticks = cleaner.get_clean_ticks(ins_code=ins_code, d_even=d_even, include_canceled=False)[
            :limit
        ]
        normalized = [
            {
                "ins_code": t["ins_code"],
                "symbol": inst.symbol if inst else ins_code,
                "ua_ins_code": None,
                "d_even": t["d_even"],
                "h_even": t["h_even"],
                "n_tran": t["n_tran"],
                "ts_tehran": t["ts_tehran"],
                "ts_utc": t["ts_utc"],
                "ts_epoch": t["ts_epoch"],
                "price": t["p_tran"],
                "volume": t["q_tit_tran"],
                "underlying_price": t["p_tran"],
                "underlying_ts_utc": t["ts_utc"],
                "underlying_ts_epoch": t["ts_epoch"],
                "underlying_n_tran": t["n_tran"],
                "moneyness_status": None,
            }
            for t in raw_ticks
        ]
        return {
            "ins_code": ins_code,
            "instrument_type": inst.instrument_type if inst else "underlying",
            "count": len(normalized),
            "ticks": normalized,
        }

    @application.get("/api/candles")
    def get_candles(
        ins_code: str = Query(..., description="Instrument insCode"),
        timeframe: str = Query(default="1m", description="Candle timeframe: 1m, 5m, 15m, 1h, 1d"),
        d_even: Optional[int] = Query(default=None, description="Optional trading date YYYYMMDD"),
    ) -> Dict[str, Any]:
        _ensure_ready()
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported timeframe '{timeframe}'. Supported: {SUPPORTED_TIMEFRAMES}",
            )

        clauses = ["ins_code = ?", "timeframe = ?"]
        params: List[Any] = [str(ins_code), str(timeframe)]
        if d_even is not None:
            clauses.append("d_even = ?")
            params.append(int(d_even))

        with sqlite3.connect(cfg.state_db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT ins_code, timeframe, d_even, bucket_epoch,
                       bucket_ts_tehran, bucket_ts_utc,
                       open, high, low, close, last_price, close_ffill,
                       volume, value, trade_count, is_sparse
                FROM ohlcv_candles
                WHERE {' AND '.join(clauses)}
                ORDER BY bucket_epoch ASC
                """,
                params,
            ).fetchall()

        if not rows:
            built = build_ohlcv_candles(
                settings=cfg, timeframe=timeframe, ins_code=ins_code, d_even=d_even
            )
            candles = built.get(timeframe, [])
        else:
            candles = [
                {
                    "ins_code": r[0],
                    "timeframe": r[1],
                    "d_even": r[2],
                    "bucket_epoch": r[3],
                    "bucket_ts_tehran": r[4],
                    "bucket_ts_utc": r[5],
                    "open": r[6],
                    "high": r[7],
                    "low": r[8],
                    "close": r[9],
                    "last_price": r[10],
                    "close_ffill": r[11],
                    "volume": r[12],
                    "value": r[13],
                    "trade_count": r[14],
                    "is_sparse": r[15],
                }
                for r in rows
            ]

        return {
            "ins_code": ins_code,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles,
        }

    @application.get("/api/quality-report")
    def get_quality_report() -> Dict[str, Any]:
        _ensure_ready()
        engine = ReconciliationEngine(settings=cfg)
        report = engine.reconcile()

        with sqlite3.connect(cfg.state_db_path) as conn:
            sym_rows = conn.execute("SELECT ins_code, symbol, instrument_type FROM instruments").fetchall()
            canceled_cnt = conn.execute("SELECT COUNT(*) FROM canceled_ticks").fetchone()[0]

        sym_map = {str(r[0]): (str(r[1]), str(r[2])) for r in sym_rows}
        enriched_rows: List[Dict[str, Any]] = []
        for row in report["rows"]:
            sym, inst_type = sym_map.get(row["ins_code"], (row["ins_code"], "unknown"))
            enriched_rows.append(
                {
                    **row,
                    "symbol": sym,
                    "instrument_type": inst_type,
                }
            )

        return {
            "total_traded_days": report["total_traded_days"],
            "matched_days": report["matched_days"],
            "mismatched_days": report["mismatched_days"],
            "missing_days": report["missing_days"],
            "match_rate_pct": report["match_rate_pct"],
            "meets_98_pct_target": report["meets_98_pct_target"],
            "canceled_trades_count": int(canceled_cnt),
            "rows": enriched_rows,
        }

    return application


class AsgiResponse:
    """Lightweight response wrapper for AsgiTestClient."""

    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes) -> None:
        self.status_code = status_code
        self.headers = headers
        self.body = body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text)


class AsgiTestClient:
    """Zero-dependency ASGI test client calling FastAPI app directly via asyncio.run."""

    def __init__(self, app_instance: FastAPI) -> None:
        self.app = app_instance

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> AsgiResponse:
        parsed = urllib.parse.urlsplit(path)
        query_str = parsed.query
        if params:
            clean_params = {k: str(v) for k, v in params.items() if v is not None}
            extra_q = urllib.parse.urlencode(clean_params)
            query_str = f"{query_str}&{extra_q}".strip("&")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": parsed.path or "/",
            "raw_path": (parsed.path or "/").encode("utf-8"),
            "query_string": query_str.encode("utf-8"),
            "headers": [(b"host", b"testserver"), (b"accept", b"application/json")],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }

        status_code = 500
        resp_headers: Dict[str, str] = {}
        body_chunks: List[bytes] = []

        async def receive() -> Dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: Dict[str, Any]) -> None:
            nonlocal status_code, resp_headers
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                resp_headers = {
                    k.decode("latin1").lower(): v.decode("latin1")
                    for k, v in message.get("headers", [])
                }
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        asyncio.run(self.app(scope, receive, send))
        return AsgiResponse(status_code=status_code, headers=resp_headers, body=b"".join(body_chunks))


app = create_app()
