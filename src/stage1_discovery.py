"""Stage 1: Option & Underlying Asset Discovery and SQLite Instrument Registry."""
import gzip
import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import Settings, get_settings
from src.fixtures import UNDERLYING_ASSETS_25, generate_fixtures
from src.models import (
    InstrumentInfoResponse,
    InstrumentRecord,
    InstrumentSearchItem,
    InstrumentSearchResponse,
    OptionMarketWatchResponse,
    OptionMarketWatchRow,
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}


def normalize_persian(text: str) -> str:
    """Normalize Arabic Yeh/Kaf and whitespace for reliable symbol matching."""
    if not text:
        return ""
    return (
        text.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .strip()
    )


def parse_option_lval30(
    lval30: str, lval18: str = ""
) -> Tuple[Optional[str], Optional[str], Optional[float], Optional[int]]:
    """
    Parse TSETMC option full name such as 'اختيارخ فولاد-4500-20261221'
    into (instrument_type, ua_symbol_hint, strike_price, end_date).
    """
    norm_30 = normalize_persian(lval30)
    norm_18 = normalize_persian(lval18)

    inst_type: Optional[str] = None
    if norm_18.startswith("ض") or "اختیارخ" in norm_30 or "اختیار خرید" in norm_30:
        inst_type = "call"
    elif norm_18.startswith("ط") or "اختیارف" in norm_30 or "اختیار فروش" in norm_30:
        inst_type = "put"

    ua_hint: Optional[str] = None
    strike_price: Optional[float] = None
    end_date: Optional[int] = None

    parts = [p.strip() for p in norm_30.split("-") if p.strip()]
    if parts:
        head = parts[0]
        for prefix in ("اختیار خرید", "اختیار فروش", "اختیارخ", "اختیارف"):
            if head.startswith(prefix):
                candidate = head[len(prefix) :].strip()
                if candidate:
                    ua_hint = candidate
                break

    if len(parts) >= 3:
        try:
            strike_price = float(parts[1].replace(",", ""))
        except ValueError:
            strike_price = None

        date_raw = re.sub(r"[^0-9]", "", parts[2])
        if len(date_raw) == 8:
            try:
                val = int(date_raw)
                if val >= 19900101:
                    end_date = val
            except ValueError:
                end_date = None

    return inst_type, ua_hint, strike_price, end_date


class OptionDiscoveryService:
    """
    Discovers all 25 TSETMC underlying assets plus active and expired Call/Put options
    from 1402 SH (20230321) onwards, enriches metadata, and persists to SQLite.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._use_fixtures: Optional[bool] = (
            True if self.settings.tsetmc_use_fixtures else None
        )
        self._fixture_cache: Dict[str, Any] = {}
        self._init_db()

    def _init_db(self) -> None:
        self.settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS instruments (
                    ins_code TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    instrument_type TEXT NOT NULL,
                    ua_ins_code TEXT,
                    strike_price REAL,
                    end_date INTEGER,
                    contract_size INTEGER NOT NULL DEFAULT 1,
                    is_expired INTEGER NOT NULL DEFAULT 0,
                    y_val TEXT,
                    cgr_val_cot TEXT
                )
                """
            )
            conn.commit()

    def _ensure_fixtures_loaded(self) -> None:
        if self._fixture_cache:
            return
        req_files = [
            "option_market_watch.json",
            "instrument_search.json",
            "instrument_info.json",
        ]
        if not all((self.settings.fixtures_dir / f).is_file() for f in req_files):
            generate_fixtures(self.settings.fixtures_dir)
        for fname in req_files:
            fpath = self.settings.fixtures_dir / fname
            self._fixture_cache[fname] = json.loads(fpath.read_text(encoding="utf-8"))

    def probe_live_api(self, timeout: float = 10.0) -> bool:
        """Probe TSETMC CDN connectivity with a 10-second timeout; fallback to fixtures if blocked."""
        if self.settings.tsetmc_use_fixtures:
            self._use_fixtures = True
            return False
        url = f"{self.settings.tsetmc_base_url.rstrip('/')}/Instrument/GetInstrumentOptionMarketWatch/0"
        req = urllib.request.Request(url, headers=BROWSER_HEADERS, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    self._use_fixtures = False
                    return True
        except Exception:
            pass
        self._use_fixtures = True
        return False

    def _http_get_json(self, path: str) -> Any:
        url = f"{self.settings.tsetmc_base_url.rstrip('/')}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers=BROWSER_HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=self.settings.tsetmc_timeout_seconds) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))

    @property
    def using_fixtures(self) -> bool:
        if self._use_fixtures is None:
            self.probe_live_api(timeout=min(10.0, self.settings.tsetmc_timeout_seconds))
        return bool(self._use_fixtures)

    def fetch_option_market_watch(self) -> List[OptionMarketWatchRow]:
        """Fetch active option pairs from /Instrument/GetInstrumentOptionMarketWatch/0."""
        if not self.using_fixtures:
            try:
                data = self._http_get_json("/Instrument/GetInstrumentOptionMarketWatch/0")
                return OptionMarketWatchResponse.parse_obj(data).instrumentOptMarketWatch
            except Exception:
                self._use_fixtures = True

        self._ensure_fixtures_loaded()
        data = self._fixture_cache["option_market_watch.json"]
        return OptionMarketWatchResponse.parse_obj(data).instrumentOptMarketWatch

    def fetch_instrument_search(self, query: str) -> List[InstrumentSearchItem]:
        """Search instruments via /Instrument/GetInstrumentSearch/{query}."""
        if not self.using_fixtures:
            try:
                encoded = urllib.parse.quote(query)
                data = self._http_get_json(f"/Instrument/GetInstrumentSearch/{encoded}")
                return InstrumentSearchResponse.parse_obj(data).instrumentSearch
            except Exception:
                self._use_fixtures = True

        self._ensure_fixtures_loaded()
        all_items = InstrumentSearchResponse.parse_obj(
            self._fixture_cache["instrument_search.json"]
        ).instrumentSearch
        q_norm = normalize_persian(query)
        return [
            item
            for item in all_items
            if q_norm in normalize_persian(item.lVal18AFC)
            or q_norm in normalize_persian(item.lVal30)
        ]

    def fetch_instrument_info(self, ins_code: str) -> Optional[InstrumentInfoResponse]:
        """Fetch detailed instrument metadata via /Instrument/GetInstrumentInfo/{insCode}."""
        if not self.using_fixtures:
            try:
                data = self._http_get_json(f"/Instrument/GetInstrumentInfo/{ins_code}")
                return InstrumentInfoResponse.parse_obj(data)
            except Exception:
                self._use_fixtures = True

        self._ensure_fixtures_loaded()
        info_map = self._fixture_cache["instrument_info.json"]
        if ins_code in info_map:
            return InstrumentInfoResponse.parse_obj(info_map[ins_code])
        return None

    def _resolve_ua_ins_code(
        self, symbol: str, full_name: str, explicit_ua: Optional[str] = None
    ) -> Optional[str]:
        if explicit_ua:
            return explicit_ua

        _, ua_hint, _, _ = parse_option_lval30(full_name, symbol)
        norm_hint = normalize_persian(ua_hint or "")
        norm_sym = normalize_persian(symbol)

        if norm_hint:
            for ua in UNDERLYING_ASSETS_25:
                if norm_hint == normalize_persian(ua["lVal18AFC"]) or norm_hint in normalize_persian(
                    ua["lVal30"]
                ):
                    return ua["insCode"]

        if len(norm_sym) > 1 and norm_sym[0] in ("ض", "ط"):
            body = norm_sym[1:]
            for ua in UNDERLYING_ASSETS_25:
                root = normalize_persian(ua["option_root"])
                if body.startswith(root):
                    return ua["insCode"]

        return None

    def discover_all(self, reference_date: int = 20261108) -> List[InstrumentRecord]:
        """
        Execute multi-strategy discovery:
        1. Canonical 25 underlying assets (verified via search + info).
        2. Active Option Market Watch (/Instrument/GetInstrumentOptionMarketWatch/0).
        3. Systematic prefix search (ض... and ط...) across all 25 underlying assets for active & expired options.
        4. Enrich with /Instrument/GetInstrumentInfo/{insCode} and persist to SQLite.
        """
        registry: Dict[str, InstrumentRecord] = {}

        # Step 1: Register all 25 underlying assets
        for ua in UNDERLYING_ASSETS_25:
            ins_code = ua["insCode"]
            info_resp = self.fetch_instrument_info(ins_code)
            symbol = ua["lVal18AFC"]
            full_name = ua["lVal30"]
            y_val = ua.get("yVal")
            cgr_val_cot = ua.get("cgrValCot")
            if info_resp:
                info = info_resp.instrumentInfo
                symbol = info.lVal18AFC or symbol
                full_name = info.lVal30 or full_name
                y_val = info.yVal or y_val
                cgr_val_cot = info.cgrValCot or cgr_val_cot

            registry[ins_code] = InstrumentRecord(
                ins_code=ins_code,
                symbol=symbol,
                full_name=full_name,
                instrument_type="underlying",
                ua_ins_code=None,
                strike_price=None,
                end_date=None,
                contract_size=1,
                is_expired=False,
                y_val=y_val,
                cgr_val_cot=cgr_val_cot,
            )

        # Step 2: Active Option Market Watch
        watchlist_rows = self.fetch_option_market_watch()
        watchlist_meta: Dict[str, Dict[str, Any]] = {}
        for row in watchlist_rows:
            if row.insCode_C:
                watchlist_meta[row.insCode_C] = {
                    "instrument_type": "call",
                    "ua_ins_code": row.uaInsCode,
                    "strike_price": row.strikePrice,
                    "end_date": row.endDate,
                    "contract_size": row.contractSize or 1000,
                    "symbol": row.lVal18AFC_C,
                    "full_name": row.lVal30_C,
                }
            if row.insCode_P:
                watchlist_meta[row.insCode_P] = {
                    "instrument_type": "put",
                    "ua_ins_code": row.uaInsCode,
                    "strike_price": row.strikePrice,
                    "end_date": row.endDate,
                    "contract_size": row.contractSize or 1000,
                    "symbol": row.lVal18AFC_P,
                    "full_name": row.lVal30_P,
                }

        # Step 3: Systematic prefix search across all 25 underlying assets (ض + root, ط + root)
        discovered_search_items: Dict[str, InstrumentSearchItem] = {}
        search_queries: List[str] = ["ض", "ط"]
        for ua in UNDERLYING_ASSETS_25:
            root = ua["option_root"]
            search_queries.append(f"ض{root}")
            search_queries.append(f"ط{root}")

        for q in search_queries:
            for item in self.fetch_instrument_search(q):
                if item.insCode not in registry:
                    discovered_search_items[item.insCode] = item

        # Merge all candidate option insCodes from watchlist + search
        candidate_option_codes = list(
            dict.fromkeys(list(watchlist_meta.keys()) + list(discovered_search_items.keys()))
        )

        # Step 4: Enrich and normalize every option contract
        for ins_code in candidate_option_codes:
            if ins_code in registry:
                continue

            w_meta = watchlist_meta.get(ins_code, {})
            s_item = discovered_search_items.get(ins_code)
            info_resp = self.fetch_instrument_info(ins_code)
            info = info_resp.instrumentInfo if info_resp else None

            symbol = (
                (info.lVal18AFC if info else None)
                or (s_item.lVal18AFC if s_item else None)
                or w_meta.get("symbol")
                or ""
            )
            full_name = (
                (info.lVal30 if info else None)
                or (s_item.lVal30 if s_item else None)
                or w_meta.get("full_name")
                or ""
            )

            parsed_type, _, parsed_strike, parsed_end = parse_option_lval30(full_name, symbol)
            inst_type = w_meta.get("instrument_type") or parsed_type
            if inst_type not in ("call", "put"):
                continue

            strike_price = (
                w_meta.get("strike_price")
                if w_meta.get("strike_price") is not None
                else parsed_strike
            )
            end_date = (
                w_meta.get("end_date")
                if w_meta.get("end_date") is not None
                else parsed_end
            )
            if end_date is None and s_item and s_item.lastDate >= 19900101:
                end_date = s_item.lastDate

            # Filter out options that expired before 1402/01/01 (20230321)
            if end_date is not None and end_date < self.settings.tsetmc_start_date:
                continue

            contract_size = (
                w_meta.get("contract_size")
                or (info.contractSize if info and info.contractSize > 0 else None)
                or (s_item.contractSize if s_item and s_item.contractSize else None)
                or 1000
            )
            ua_ins_code = self._resolve_ua_ins_code(
                symbol, full_name, explicit_ua=w_meta.get("ua_ins_code")
            )
            is_expired = bool(end_date is not None and end_date < reference_date)

            y_val = (info.yVal if info else None) or (s_item.yVal if s_item else None)
            cgr_val_cot = (info.cgrValCot if info else None) or (
                s_item.cgrValCot if s_item else None
            )

            registry[ins_code] = InstrumentRecord(
                ins_code=ins_code,
                symbol=symbol,
                full_name=full_name,
                instrument_type=inst_type,
                ua_ins_code=ua_ins_code,
                strike_price=strike_price,
                end_date=end_date,
                contract_size=int(contract_size),
                is_expired=is_expired,
                y_val=y_val,
                cgr_val_cot=cgr_val_cot,
            )

        records = list(registry.values())
        self.save_to_registry(records)
        return records

    def save_to_registry(self, records: List[InstrumentRecord]) -> int:
        """Upsert discovered InstrumentRecord items into SQLite instruments table."""
        with sqlite3.connect(self.settings.state_db_path) as conn:
            conn.executemany(
                """
                INSERT INTO instruments (
                    ins_code, symbol, full_name, instrument_type,
                    ua_ins_code, strike_price, end_date, contract_size,
                    is_expired, y_val, cgr_val_cot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ins_code) DO UPDATE SET
                    symbol = excluded.symbol,
                    full_name = excluded.full_name,
                    instrument_type = excluded.instrument_type,
                    ua_ins_code = excluded.ua_ins_code,
                    strike_price = excluded.strike_price,
                    end_date = excluded.end_date,
                    contract_size = excluded.contract_size,
                    is_expired = excluded.is_expired,
                    y_val = excluded.y_val,
                    cgr_val_cot = excluded.cgr_val_cot
                """,
                [
                    (
                        r.ins_code,
                        r.symbol,
                        r.full_name,
                        r.instrument_type,
                        r.ua_ins_code,
                        r.strike_price,
                        r.end_date,
                        r.contract_size,
                        1 if r.is_expired else 0,
                        r.y_val,
                        r.cgr_val_cot,
                    )
                    for r in records
                ],
            )
            conn.commit()
        return len(records)

    def list_instruments(
        self,
        instrument_type: Optional[str] = None,
        ua_ins_code: Optional[str] = None,
        is_expired: Optional[bool] = None,
    ) -> List[InstrumentRecord]:
        """Query instruments from the SQLite registry with optional filters."""
        clauses: List[str] = []
        params: List[Any] = []
        if instrument_type is not None:
            clauses.append("instrument_type = ?")
            params.append(instrument_type)
        if ua_ins_code is not None:
            clauses.append("ua_ins_code = ?")
            params.append(ua_ins_code)
        if is_expired is not None:
            clauses.append("is_expired = ?")
            params.append(1 if is_expired else 0)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT ins_code, symbol, full_name, instrument_type,
                   ua_ins_code, strike_price, end_date, contract_size,
                   is_expired, y_val, cgr_val_cot
            FROM instruments
            {where_sql}
            ORDER BY ins_code ASC
        """
        with sqlite3.connect(self.settings.state_db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            InstrumentRecord(
                ins_code=row[0],
                symbol=row[1],
                full_name=row[2],
                instrument_type=row[3],
                ua_ins_code=row[4],
                strike_price=row[5],
                end_date=row[6],
                contract_size=row[7],
                is_expired=bool(row[8]),
                y_val=row[9],
                cgr_val_cot=row[10],
            )
            for row in rows
        ]

    def get_instrument(self, ins_code: str) -> Optional[InstrumentRecord]:
        """Fetch a single InstrumentRecord by ins_code from SQLite."""
        with sqlite3.connect(self.settings.state_db_path) as conn:
            row = conn.execute(
                """
                SELECT ins_code, symbol, full_name, instrument_type,
                       ua_ins_code, strike_price, end_date, contract_size,
                       is_expired, y_val, cgr_val_cot
                FROM instruments
                WHERE ins_code = ?
                """,
                (ins_code,),
            ).fetchone()
        if not row:
            return None
        return InstrumentRecord(
            ins_code=row[0],
            symbol=row[1],
            full_name=row[2],
            instrument_type=row[3],
            ua_ins_code=row[4],
            strike_price=row[5],
            end_date=row[6],
            contract_size=row[7],
            is_expired=bool(row[8]),
            y_val=row[9],
            cgr_val_cot=row[10],
        )
