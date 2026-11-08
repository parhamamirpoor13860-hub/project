"""Pydantic v1 models matching TSETMC CDN API schemas and internal registry records."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InstrumentSearchItem(BaseModel):
    """Item in /Instrument/GetInstrumentSearch/{searchQuery} -> instrumentSearch."""

    insCode: str
    lVal18AFC: str
    lVal30: str
    lastDate: int = 0
    cgrValCot: Optional[str] = None
    yVal: Optional[str] = None
    contractSize: Optional[int] = None

    class Config:
        extra = "ignore"


class OptionMarketWatchRow(BaseModel):
    """Item in /Instrument/GetInstrumentOptionMarketWatch/0 -> instrumentOptMarketWatch."""

    insCode_C: str
    insCode_P: str
    uaInsCode: str
    contractSize: int = 1000
    strikePrice: float
    endDate: int
    remainedDay: int = 0
    pMeDem_C: float = 0.0
    pMeOf_C: float = 0.0
    pMeDem_P: float = 0.0
    pMeOf_P: float = 0.0
    lVal18AFC_C: Optional[str] = None
    lVal30_C: Optional[str] = None
    lVal18AFC_P: Optional[str] = None
    lVal30_P: Optional[str] = None

    class Config:
        extra = "ignore"


class InstrumentInfoItem(BaseModel):
    """Inner object in /Instrument/GetInstrumentInfo/{insCode} -> instrumentInfo."""

    insCode: str
    lVal18AFC: str
    lVal30: str
    contractSize: int = 0
    yVal: Optional[str] = None
    cgrValCot: Optional[str] = None
    dEven: int = 0
    cIsin: Optional[str] = None
    instrumentID: Optional[str] = None
    flow: Optional[int] = None
    zTitad: Optional[float] = None
    baseVol: Optional[int] = None
    eps: Optional[Dict[str, Any]] = None
    sector: Optional[Dict[str, Any]] = None
    staticThreshold: Optional[Dict[str, Any]] = None

    class Config:
        extra = "ignore"


class InstrumentInfoResponse(BaseModel):
    """Wrapper for /Instrument/GetInstrumentInfo/{insCode} response."""

    instrumentInfo: InstrumentInfoItem

    class Config:
        extra = "ignore"


class InstrumentRecord(BaseModel):
    """Normalized instrument registry record stored in SQLite/DuckDB."""

    ins_code: str
    symbol: str = Field(..., description="Trading symbol (lVal18AFC)")
    full_name: str = Field(..., description="Full instrument name (lVal30)")
    instrument_type: str = Field(..., description="'underlying', 'call', or 'put'")
    ua_ins_code: Optional[str] = None
    strike_price: Optional[float] = None
    end_date: Optional[int] = None
    contract_size: int = 1
    is_expired: bool = False
    y_val: Optional[str] = None
    cgr_val_cot: Optional[str] = None

    class Config:
        extra = "ignore"


class ClosingPriceDailyItem(BaseModel):
    """Item in /ClosingPrice/GetClosingPriceDailyList/{insCode}/0 -> closingPriceDaily."""

    insCode: str
    dEven: int
    hEven: int = 0
    priceFirst: float = 0.0
    priceMax: float = 0.0
    priceMin: float = 0.0
    pClosing: float = 0.0
    pDrCotVal: float = 0.0
    priceYesterday: float = 0.0
    priceChange: float = 0.0
    zTotTran: float = 0.0
    qTotTran5J: float = 0.0
    qTotCap: float = 0.0
    last: bool = False
    id: int = 0
    iClose: bool = False
    yClose: bool = True

    class Config:
        extra = "ignore"


class TradeHistoryItem(BaseModel):
    """Item in /Trade/GetTradeHistory/{insCode}/{YYYYMMDD}/false -> tradeHistory."""

    insCode: Optional[str] = None
    dEven: int = 0
    nTran: int
    hEven: int
    qTitTran: float
    pTran: float
    canceled: int = 0
    qTitNgJ: int = 0
    iSensVarP: str = "\u0000"
    pPhSeaCotJ: float = 0.0
    pPbSeaCotJ: float = 0.0
    iAnuTran: int = 0
    xqVarPJDrPRf: float = 0.0

    class Config:
        extra = "ignore"


class InstrumentSearchResponse(BaseModel):
    """Wrapper for /Instrument/GetInstrumentSearch/{searchQuery}."""

    instrumentSearch: List[InstrumentSearchItem] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class OptionMarketWatchResponse(BaseModel):
    """Wrapper for /Instrument/GetInstrumentOptionMarketWatch/0."""

    instrumentOptMarketWatch: List[OptionMarketWatchRow] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class ClosingPriceDailyResponse(BaseModel):
    """Wrapper for /ClosingPrice/GetClosingPriceDailyList/{insCode}/0."""

    closingPriceDaily: List[ClosingPriceDailyItem] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class TradeHistoryResponse(BaseModel):
    """Wrapper for /Trade/GetTradeHistory/{insCode}/{YYYYMMDD}/false."""

    tradeHistory: List[TradeHistoryItem] = Field(default_factory=list)

    class Config:
        extra = "ignore"
