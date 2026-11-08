"""Deterministic TSETMC API fixture generator for all 25 underlying assets and option contracts."""
import json
from pathlib import Path
from typing import Any, Dict, List


UNDERLYING_ASSETS_25: List[Dict[str, Any]] = [
    {
        "insCode": "46348559193224090",
        "lVal18AFC": "فولاد",
        "lVal30": "فولاد مباركه اصفهان",
        "option_root": "فلا",
        "cIsin": "IRO1FOLD0009",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "35425587644337450",
        "lVal18AFC": "فملی",
        "lVal30": "ملي صنايع مس ايران",
        "option_root": "فمل",
        "cIsin": "IRO1MSMI0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "17914401175772326",
        "lVal18AFC": "اهرم",
        "lVal30": "صندوق سرمايه گذاري اهرمي كاريمان",
        "option_root": "اهرم",
        "cIsin": "IRT1AHRM0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "65883838195688438",
        "lVal18AFC": "خودرو",
        "lVal30": "ايران خودرو",
        "option_root": "خدر",
        "cIsin": "IRO1IKCO0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "2400322364771558",
        "lVal18AFC": "شستا",
        "lVal30": "سرمايه گذاري تامين اجتماعي",
        "option_root": "شست",
        "cIsin": "IRO1TAIR0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "44891482026867833",
        "lVal18AFC": "خساپا",
        "lVal30": "سايپا",
        "option_root": "خسا",
        "cIsin": "IRO1SIPA0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "778253364357513",
        "lVal18AFC": "وبملت",
        "lVal30": "بانك ملت",
        "option_root": "ملت",
        "cIsin": "IRO1BMLT0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "63917421733088077",
        "lVal18AFC": "وتجارت",
        "lVal30": "بانك تجارت",
        "option_root": "تجا",
        "cIsin": "IRO1BTJR0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "28320293733348826",
        "lVal18AFC": "وبصادر",
        "lVal30": "بانك صادرات ايران",
        "option_root": "صاد",
        "cIsin": "IRO1BSDR0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "7745894403636165",
        "lVal18AFC": "شپنا",
        "lVal30": "پالايش نفت اصفهان",
        "option_root": "شپن",
        "cIsin": "IRO1PNES0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "35366681030756042",
        "lVal18AFC": "شبندر",
        "lVal30": "پالايش نفت بندرعباس",
        "option_root": "شبن",
        "cIsin": "IRO1PNBA0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "35700344742885862",
        "lVal18AFC": "کگل",
        "lVal30": "معدني و صنعتي گل گهر",
        "option_root": "كگل",
        "cIsin": "IRO1GOLG0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "18027801615184692",
        "lVal18AFC": "کچاد",
        "lVal30": "معدني و صنعتي چادرملو",
        "option_root": "چاد",
        "cIsin": "IRO1CHML0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "62782983923309630",
        "lVal18AFC": "پالایش",
        "lVal30": "صندوق پالايشي يكم",
        "option_root": "پال",
        "cIsin": "IRT1PLYK0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "33878047680249697",
        "lVal18AFC": "دارا یکم",
        "lVal30": "صندوق واسطه گري مالي يكم",
        "option_root": "دارا",
        "cIsin": "IRT1DARA0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "55254206302462140",
        "lVal18AFC": "شتاب",
        "lVal30": "صندوق سرمايه گذاري اهرمي شتاب",
        "option_root": "شتاب",
        "cIsin": "IRT1SHTB0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "41927452991671109",
        "lVal18AFC": "سرو",
        "lVal30": "صندوق سرمايه گذاري سرو سودمند مدبران",
        "option_root": "سرو",
        "cIsin": "IRT1SARV0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "61433307985319904",
        "lVal18AFC": "موج",
        "lVal30": "صندوق سرمايه گذاري اهرمي موج",
        "option_root": "موج",
        "cIsin": "IRT1MOWJ0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "31800535589614501",
        "lVal18AFC": "آتیمس",
        "lVal30": "صندوق سرمايه گذاري آتيمس",
        "option_root": "آتيم",
        "cIsin": "IRT1ATMS0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "21508901342626983",
        "lVal18AFC": "توان",
        "lVal30": "صندوق سرمايه گذاري اهرمي توان",
        "option_root": "توان",
        "cIsin": "IRT1TAVN0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "49012384756192837",
        "lVal18AFC": "جهش",
        "lVal30": "صندوق سرمايه گذاري اهرمي جهش",
        "option_root": "جهش",
        "cIsin": "IRT1JHSH0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "68123490182736451",
        "lVal18AFC": "عیار",
        "lVal30": "صندوق سرمايه گذاري طلاي عيار",
        "option_root": "عيار",
        "cIsin": "IRT1AYAR0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "52918374650192834",
        "lVal18AFC": "کهربا",
        "lVal30": "صندوق سرمايه گذاري طلاي كهربا",
        "option_root": "كهرب",
        "cIsin": "IRT1KHRB0001",
        "yVal": "305",
        "cgrValCot": "I1",
    },
    {
        "insCode": "9211775239375291",
        "lVal18AFC": "ذوب",
        "lVal30": "ذوب آهن اصفهان",
        "option_root": "ذوب",
        "cIsin": "IRO1ZOBI0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
    {
        "insCode": "38729184750192837",
        "lVal18AFC": "غدیر",
        "lVal30": "سرمايه گذاري غدير",
        "option_root": "غدي",
        "cIsin": "IRO1GDIR0001",
        "yVal": "300",
        "cgrValCot": "N1",
    },
]


OPTION_CONTRACTS_FIXTURE: List[Dict[str, Any]] = [
    {
        "insCode": "90000000000000001",
        "lVal18AFC": "ضفلا1100",
        "lVal30": "اختيارخ فولاد-4500-20261221",
        "instrument_type": "call",
        "uaInsCode": "46348559193224090",
        "strikePrice": 4500.0,
        "endDate": 20261221,
        "contractSize": 1000,
        "is_expired": False,
        "yVal": "311",
        "cgrValCot": "O1",
    },
    {
        "insCode": "90000000000000002",
        "lVal18AFC": "طفلا1100",
        "lVal30": "اختيارف فولاد-4500-20261221",
        "instrument_type": "put",
        "uaInsCode": "46348559193224090",
        "strikePrice": 4500.0,
        "endDate": 20261221,
        "contractSize": 1000,
        "is_expired": False,
        "yVal": "312",
        "cgrValCot": "O1",
    },
    {
        "insCode": "90000000000000003",
        "lVal18AFC": "ضفمل1200",
        "lVal30": "اختيارخ فملی-6000-20261221",
        "instrument_type": "call",
        "uaInsCode": "35425587644337450",
        "strikePrice": 6000.0,
        "endDate": 20261221,
        "contractSize": 1000,
        "is_expired": False,
        "yVal": "311",
        "cgrValCot": "O1",
    },
    {
        "insCode": "90000000000000004",
        "lVal18AFC": "طفمل1200",
        "lVal30": "اختيارف فملی-6000-20261221",
        "instrument_type": "put",
        "uaInsCode": "35425587644337450",
        "strikePrice": 6000.0,
        "endDate": 20261221,
        "contractSize": 1000,
        "is_expired": False,
        "yVal": "312",
        "cgrValCot": "O1",
    },
    {
        "insCode": "90000000000000005",
        "lVal18AFC": "ضفلا0205",
        "lVal30": "اختيارخ فولاد-4000-20230809",
        "instrument_type": "call",
        "uaInsCode": "46348559193224090",
        "strikePrice": 4000.0,
        "endDate": 20230809,
        "contractSize": 1000,
        "is_expired": True,
        "yVal": "311",
        "cgrValCot": "O1",
    },
    {
        "insCode": "90000000000000006",
        "lVal18AFC": "طفلا0205",
        "lVal30": "اختيارف فولاد-4000-20230809",
        "instrument_type": "put",
        "uaInsCode": "46348559193224090",
        "strikePrice": 4000.0,
        "endDate": 20230809,
        "contractSize": 1000,
        "is_expired": True,
        "yVal": "312",
        "cgrValCot": "O1",
    },
]


def build_option_market_watch_fixture() -> Dict[str, Any]:
    """Generate /Instrument/GetInstrumentOptionMarketWatch/0 fixture."""
    return {
        "instrumentOptMarketWatch": [
            {
                "insCode_C": "90000000000000001",
                "insCode_P": "90000000000000002",
                "uaInsCode": "46348559193224090",
                "contractSize": 1000,
                "strikePrice": 4500.0,
                "endDate": 20261221,
                "remainedDay": 43,
                "pMeDem_C": 320.0,
                "pMeOf_C": 335.0,
                "pMeDem_P": 180.0,
                "pMeOf_P": 195.0,
                "lVal18AFC_C": "ضفلا1100",
                "lVal30_C": "اختيارخ فولاد-4500-20261221",
                "lVal18AFC_P": "طفلا1100",
                "lVal30_P": "اختيارف فولاد-4500-20261221",
            },
            {
                "insCode_C": "90000000000000003",
                "insCode_P": "90000000000000004",
                "uaInsCode": "35425587644337450",
                "contractSize": 1000,
                "strikePrice": 6000.0,
                "endDate": 20261221,
                "remainedDay": 43,
                "pMeDem_C": 410.0,
                "pMeOf_C": 425.0,
                "pMeDem_P": 220.0,
                "pMeOf_P": 240.0,
                "lVal18AFC_C": "ضفمل1200",
                "lVal30_C": "اختيارخ فملی-6000-20261221",
                "lVal18AFC_P": "طفمل1200",
                "lVal30_P": "اختيارف فملی-6000-20261221",
            },
        ]
    }


def build_instrument_search_fixture() -> Dict[str, Any]:
    """Generate /Instrument/GetInstrumentSearch/{query} fixture."""
    items: List[Dict[str, Any]] = []
    for ua in UNDERLYING_ASSETS_25:
        items.append(
            {
                "insCode": ua["insCode"],
                "lVal18AFC": ua["lVal18AFC"],
                "lVal30": ua["lVal30"],
                "lastDate": 20261107,
                "cgrValCot": ua["cgrValCot"],
                "yVal": ua["yVal"],
                "contractSize": 1,
            }
        )
    for opt in OPTION_CONTRACTS_FIXTURE:
        items.append(
            {
                "insCode": opt["insCode"],
                "lVal18AFC": opt["lVal18AFC"],
                "lVal30": opt["lVal30"],
                "lastDate": opt["endDate"],
                "cgrValCot": opt["cgrValCot"],
                "yVal": opt["yVal"],
                "contractSize": opt["contractSize"],
            }
        )
    return {"instrumentSearch": items}


def build_instrument_info_fixture() -> Dict[str, Any]:
    """Generate /Instrument/GetInstrumentInfo/{insCode} fixture keyed by insCode."""
    info_map: Dict[str, Any] = {}
    for ua in UNDERLYING_ASSETS_25:
        info_map[ua["insCode"]] = {
            "instrumentInfo": {
                "eps": {
                    "epsValue": None,
                    "estimatedEPS": "693",
                    "sectorPE": 11.87,
                    "psr": 2541.02,
                },
                "sector": {
                    "dEven": 0,
                    "cSecVal": "27 ",
                    "lSecVal": "فلزات اساسي",
                },
                "staticThreshold": {
                    "insCode": None,
                    "dEven": 0,
                    "hEven": 0,
                    "psGelStaMax": 4540.0,
                    "psGelStaMin": 4280.0,
                },
                "minWeek": 4140.0,
                "maxWeek": 4410.0,
                "minYear": 2182.0,
                "maxYear": 4540.0,
                "qTotTran5JAvg": 2654143382.0,
                "kAjCapValCpsIdx": "36",
                "dEven": 20261108,
                "topInst": 1,
                "faraDesc": "",
                "contractSize": 0,
                "nav": 0.0,
                "underSupervision": 0,
                "etfIssuedUnit": 0.0,
                "etfUnitDeven": 0,
                "cValMne": None,
                "lVal18": ua["lVal18AFC"],
                "cSocCSAC": None,
                "lSoc30": None,
                "yMarNSC": None,
                "yVal": ua["yVal"],
                "insCode": ua["insCode"],
                "lVal30": ua["lVal30"],
                "lVal18AFC": ua["lVal18AFC"],
                "flow": 1,
                "cIsin": ua["cIsin"],
                "zTitad": 1935000000000.0,
                "baseVol": 1,
                "instrumentID": ua["cIsin"],
                "cgrValCot": ua["cgrValCot"],
                "cComVal": "1",
                "lastDate": 0,
                "sourceID": 1,
                "flowTitle": "بازار بورس",
                "cgrValCotTitle": "بازار اول (تابلوی اصلی) بورس",
            }
        }

    for opt in OPTION_CONTRACTS_FIXTURE:
        info_map[opt["insCode"]] = {
            "instrumentInfo": {
                "eps": {
                    "epsValue": None,
                    "estimatedEPS": None,
                    "sectorPE": 0.0,
                    "psr": 0.0,
                },
                "sector": {
                    "dEven": 0,
                    "cSecVal": "27 ",
                    "lSecVal": "اختيار معامله",
                },
                "staticThreshold": {
                    "insCode": None,
                    "dEven": 0,
                    "hEven": 0,
                    "psGelStaMax": 10000.0,
                    "psGelStaMin": 1.0,
                },
                "minWeek": 100.0,
                "maxWeek": 500.0,
                "minYear": 50.0,
                "maxYear": 800.0,
                "qTotTran5JAvg": 50000.0,
                "kAjCapValCpsIdx": "0",
                "dEven": opt["endDate"],
                "topInst": 0,
                "faraDesc": "",
                "contractSize": opt["contractSize"],
                "nav": 0.0,
                "underSupervision": 0,
                "etfIssuedUnit": 0.0,
                "etfUnitDeven": 0,
                "cValMne": None,
                "lVal18": opt["lVal18AFC"],
                "cSocCSAC": None,
                "lSoc30": None,
                "yMarNSC": None,
                "yVal": opt["yVal"],
                "insCode": opt["insCode"],
                "lVal30": opt["lVal30"],
                "lVal18AFC": opt["lVal18AFC"],
                "flow": 1,
                "cIsin": f"IRO9OPT{opt['insCode'][-4:]}",
                "zTitad": 100000.0,
                "baseVol": 1,
                "instrumentID": f"IRO9OPT{opt['insCode'][-4:]}",
                "cgrValCot": opt["cgrValCot"],
                "cComVal": "1",
                "lastDate": opt["endDate"],
                "sourceID": 1,
                "flowTitle": "بازار مشتقه",
                "cgrValCotTitle": "بازار اختيار معامله",
            }
        }
    return info_map


def _make_daily_row(
    ins_code: str,
    d_even: int,
    h_even: int,
    price_first: float,
    price_max: float,
    price_min: float,
    p_closing: float,
    p_dr_cot_val: float,
    price_yesterday: float,
    z_tot_tran: float,
    q_tot_tran: float,
    q_tot_cap: float,
) -> Dict[str, Any]:
    return {
        "priceChange": round(p_dr_cot_val - price_yesterday, 2),
        "priceMin": price_min,
        "priceMax": price_max,
        "priceYesterday": price_yesterday,
        "priceFirst": price_first,
        "last": False,
        "id": 0,
        "insCode": ins_code,
        "dEven": d_even,
        "hEven": h_even,
        "pClosing": p_closing,
        "iClose": False,
        "yClose": True,
        "pDrCotVal": p_dr_cot_val,
        "zTotTran": z_tot_tran,
        "qTotTran5J": q_tot_tran,
        "qTotCap": q_tot_cap,
    }


def _make_tick(
    n_tran: int,
    h_even: int,
    q_tit_tran: float,
    p_tran: float,
    canceled: int = 0,
) -> Dict[str, Any]:
    """Build raw TSETMC tradeHistory item where insCode is null and dEven is 0."""
    return {
        "insCode": None,
        "dEven": 0,
        "nTran": n_tran,
        "hEven": h_even,
        "qTitTran": q_tit_tran,
        "pTran": p_tran,
        "qTitNgJ": 0,
        "iSensVarP": "\u0000",
        "pPhSeaCotJ": 0.0,
        "pPbSeaCotJ": 0.0,
        "iAnuTran": 0,
        "xqVarPJDrPRf": 0.0,
        "canceled": canceled,
    }


def build_closing_price_daily_and_trades() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build synchronized closing_price_daily.json and trade_history.json fixtures.
    Guarantees:
    - Raw ticks have insCode=None and dEven=0.
    - Multiple trades within the same second (hEven) with different nTran.
    - Includes canceled=1 trades that are excluded when reconciling against zTotTran & qTotTran5J.
    - Includes days with zTotTran == 0 and pre-1402 days (20230315) to test Stage 2 filtering.
    - Underlying trades occur prior to / alongside option trades on each day for Stage 5 ASOF JOIN.
    """
    daily_map: Dict[str, Any] = {}
    trades_map: Dict[str, Any] = {}

    folad = "46348559193224090"
    femeli = "35425587644337450"
    opt_c_folad = "90000000000000001"
    opt_p_folad = "90000000000000002"
    opt_c_femeli = "90000000000000003"
    opt_p_femeli = "90000000000000004"
    opt_exp_c = "90000000000000005"
    opt_exp_p = "90000000000000006"

    # 1. فولاد (46348559193224090)
    # Traded on 20230524, 20261104, 20261107; zero-trade day 20261105; pre-1402 day 20230315
    trades_map[f"{folad}_20230524"] = {
        "tradeHistory": [
            _make_tick(2, 90005, 1500, 4120.0, 0),
            _make_tick(1, 90005, 1000, 4100.0, 0),
            _make_tick(3, 91520, 2500, 4150.0, 0),
            _make_tick(4, 103000, 500, 4160.0, 1),  # canceled trade
        ]
    }
    trades_map[f"{folad}_20261104"] = {
        "tradeHistory": [
            _make_tick(1, 90001, 2000, 4280.0, 0),
            _make_tick(2, 90001, 3000, 4290.0, 0),
            _make_tick(3, 101500, 5000, 4310.0, 0),
        ]
    }
    trades_map[f"{folad}_20261107"] = {
        "tradeHistory": [
            _make_tick(1, 90002, 1200, 4390.0, 0),
            _make_tick(3, 90010, 1800, 4410.0, 0),
            _make_tick(2, 90010, 1000, 4400.0, 0),
            _make_tick(4, 93045, 2000, 4420.0, 0),
            _make_tick(5, 110000, 900, 4450.0, 1),  # canceled
            _make_tick(6, 122952, 1700, 4410.0, 0),
        ]
    }
    daily_map[folad] = {
        "closingPriceDaily": [
            _make_daily_row(folad, 20261107, 122952, 4390.0, 4420.0, 4390.0, 4410.0, 4410.0, 4290.0, 5.0, 7700.0, 33915000.0),
            _make_daily_row(folad, 20261105, 0, 0.0, 0.0, 0.0, 4290.0, 4290.0, 4290.0, 0.0, 0.0, 0.0),
            _make_daily_row(folad, 20261104, 101500, 4280.0, 4310.0, 4280.0, 4290.0, 4310.0, 4250.0, 3.0, 10000.0, 42980000.0),
            _make_daily_row(folad, 20230524, 91520, 4100.0, 4150.0, 4100.0, 4135.0, 4150.0, 4080.0, 3.0, 5000.0, 20655000.0),
            _make_daily_row(folad, 20230315, 120000, 4000.0, 4050.0, 3990.0, 4020.0, 4020.0, 3980.0, 10.0, 15000.0, 60300000.0),
        ]
    }

    # 2. فملی (35425587644337450)
    trades_map[f"{femeli}_20261104"] = {
        "tradeHistory": [
            _make_tick(1, 90003, 1500, 5920.0, 0),
            _make_tick(2, 94500, 2500, 5980.0, 0),
        ]
    }
    trades_map[f"{femeli}_20261107"] = {
        "tradeHistory": [
            _make_tick(1, 90004, 2000, 6010.0, 0),
            _make_tick(2, 90004, 1000, 6030.0, 0),
            _make_tick(3, 104045, 3000, 6080.0, 0),
            _make_tick(4, 111000, 500, 6100.0, 1),  # canceled
        ]
    }
    daily_map[femeli] = {
        "closingPriceDaily": [
            _make_daily_row(femeli, 20261107, 104045, 6010.0, 6080.0, 6010.0, 6050.0, 6080.0, 5960.0, 3.0, 6000.0, 36290000.0),
            _make_daily_row(femeli, 20261104, 94500, 5920.0, 5980.0, 5920.0, 5960.0, 5980.0, 5900.0, 2.0, 4000.0, 23830000.0),
        ]
    }

    # 3. ضفلا1100 (90000000000000001) - Active Call on فولاد
    trades_map[f"{opt_c_folad}_20261104"] = {
        "tradeHistory": [
            _make_tick(1, 90015, 10, 290.0, 0),
            _make_tick(2, 102000, 15, 305.0, 0),
        ]
    }
    trades_map[f"{opt_c_folad}_20261107"] = {
        "tradeHistory": [
            _make_tick(2, 90020, 20, 325.0, 0),
            _make_tick(1, 90020, 10, 320.0, 0),
            _make_tick(3, 93500, 30, 335.0, 0),
            _make_tick(4, 95000, 5, 340.0, 1),  # canceled
            _make_tick(5, 122955, 25, 330.0, 0),
        ]
    }
    daily_map[opt_c_folad] = {
        "closingPriceDaily": [
            _make_daily_row(opt_c_folad, 20261107, 122955, 320.0, 335.0, 320.0, 329.0, 330.0, 300.0, 4.0, 85.0, 28000000.0),
            _make_daily_row(opt_c_folad, 20261105, 0, 0.0, 0.0, 0.0, 300.0, 305.0, 300.0, 0.0, 0.0, 0.0),
            _make_daily_row(opt_c_folad, 20261104, 102000, 290.0, 305.0, 290.0, 300.0, 305.0, 280.0, 2.0, 25.0, 7475000.0),
        ]
    }

    # 4. طفلا1100 (90000000000000002) - Active Put on فولاد
    trades_map[f"{opt_p_folad}_20261107"] = {
        "tradeHistory": [
            _make_tick(1, 90100, 12, 190.0, 0),
            _make_tick(2, 100500, 8, 185.0, 0),
        ]
    }
    daily_map[opt_p_folad] = {
        "closingPriceDaily": [
            _make_daily_row(opt_p_folad, 20261107, 100500, 190.0, 190.0, 185.0, 188.0, 185.0, 200.0, 2.0, 20.0, 3760000.0),
        ]
    }

    # 5. ضفمل1200 (90000000000000003) - Active Call on فملی
    trades_map[f"{opt_c_femeli}_20261107"] = {
        "tradeHistory": [
            _make_tick(1, 90200, 15, 415.0, 0),
            _make_tick(2, 104500, 25, 425.0, 0),
        ]
    }
    daily_map[opt_c_femeli] = {
        "closingPriceDaily": [
            _make_daily_row(opt_c_femeli, 20261107, 104500, 415.0, 425.0, 415.0, 421.0, 425.0, 400.0, 2.0, 40.0, 16850000.0),
        ]
    }

    # 6. طفمل1200 (90000000000000004) - Active Put on فملی
    trades_map[f"{opt_p_femeli}_20261107"] = {
        "tradeHistory": [
            _make_tick(1, 90300, 10, 230.0, 0),
            _make_tick(2, 105000, 10, 225.0, 0),
        ]
    }
    daily_map[opt_p_femeli] = {
        "closingPriceDaily": [
            _make_daily_row(opt_p_femeli, 20261107, 105000, 230.0, 230.0, 225.0, 227.5, 225.0, 240.0, 2.0, 20.0, 4550000.0),
        ]
    }

    # 7. ضفلا0205 (90000000000000005) - Expired 1402 Call on فولاد
    trades_map[f"{opt_exp_c}_20230524"] = {
        "tradeHistory": [
            _make_tick(1, 90010, 20, 250.0, 0),
            _make_tick(2, 91600, 30, 265.0, 0),
            _make_tick(3, 92000, 10, 270.0, 1),  # canceled
        ]
    }
    daily_map[opt_exp_c] = {
        "closingPriceDaily": [
            _make_daily_row(opt_exp_c, 20230524, 91600, 250.0, 265.0, 250.0, 259.0, 265.0, 240.0, 2.0, 50.0, 12950000.0),
        ]
    }

    # 8. طفلا0205 (90000000000000006) - Expired 1402 Put on فولاد
    trades_map[f"{opt_exp_p}_20230524"] = {
        "tradeHistory": [
            _make_tick(1, 90012, 15, 140.0, 0),
            _make_tick(2, 91700, 15, 135.0, 0),
        ]
    }
    daily_map[opt_exp_p] = {
        "closingPriceDaily": [
            _make_daily_row(opt_exp_p, 20230524, 91700, 140.0, 140.0, 135.0, 137.5, 135.0, 150.0, 2.0, 30.0, 4125000.0),
        ]
    }

    # Remaining 23 underlyings have empty or zero-trade daily lists in the compact fixture
    for ua in UNDERLYING_ASSETS_25:
        code = ua["insCode"]
        if code not in daily_map:
            daily_map[code] = {
                "closingPriceDaily": [
                    _make_daily_row(code, 20261107, 0, 0.0, 0.0, 0.0, 1000.0, 1000.0, 1000.0, 0.0, 0.0, 0.0)
                ]
            }

    return daily_map, trades_map


def generate_fixtures(fixtures_dir: Path) -> Dict[str, Path]:
    """Write all 5 deterministic JSON fixture files to fixtures_dir."""
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    daily_map, trades_map = build_closing_price_daily_and_trades()

    payloads = {
        "option_market_watch.json": build_option_market_watch_fixture(),
        "instrument_search.json": build_instrument_search_fixture(),
        "instrument_info.json": build_instrument_info_fixture(),
        "closing_price_daily.json": daily_map,
        "trade_history.json": trades_map,
    }

    written: Dict[str, Path] = {}
    for filename, content in payloads.items():
        target = fixtures_dir / filename
        target.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        written[filename] = target
    return written


if __name__ == "__main__":
    from src.config import get_settings

    settings = get_settings()
    generate_fixtures(settings.fixtures_dir)
