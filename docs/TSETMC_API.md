# TSETMC API Technical Documentation – CDN Version

## Objective

Use the following APIs to retrieve Iranian capital market data from the TSETMC system. These APIs have been practically tested via HTTP requests and return valid JSON responses.

**Base URL:**
`[https://cdn.tsetmc.com/api](https://cdn.tsetmc.com/api)`

**General Request Specifications:**

* **Method:** GET
* **Accept:** application/json
* **User-Agent:** Mozilla/5.0
* **Encoding:** UTF-8

---

## 1. Symbol and Trading Instrument Search 🛠️

**Endpoint:**
`GET /Instrument/GetInstrumentSearch/{searchQuery}`

**Example:**
`GET [https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/فولاد](https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/فولاد)`

**Output Structure:**

```json
{
  "instrumentSearch": [
    {
      "insCode": "46348559193224090",
      "lVal18AFC": "فولاد",
      "lVal30": "فولاد مباركه اصفهان",
      "lastDate": 1
    }
  ]
}

```

**Key Fields:**

| Field | Description |
| --- | --- |
| **insCode** | Unique trading instrument ID |
| **lVal18AFC** | Trading symbol (Ticker) |
| **lVal30** | Full name of the company or instrument |
| **lastDate** | Field present in output; its exact meaning requires independent verification |

**Usage:** Searching for a symbol and extracting `insCode` for use in other endpoints.
**Note:** The actual output may contain additional fields, and the search may return multiple instruments with similar names, preemptive rights, funds, or debt securities. Match both the symbol and the full name to select the target instrument.

---

## 2. Options Market Watch 📊

**Endpoint:**
`GET /Instrument/GetInstrumentOptionMarketWatch/0`

**Full Example:**
`GET [https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0](https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0)`

**Sample Output Structure:**

```json
{
  "instrumentOptMarketWatch": [
    {
      "insCode_P": "...",
      "insCode_C": "...",
      "uaInsCode": "...",
      "contractSize": 1000,
      "strikePrice": 5000,
      "endDate": 20261221,
      "remainedDay": 40,
      "pMeDem_P": 100,
      "pMeOf_P": 110,
      "pMeDem_C": 200,
      "pMeOf_C": 210
    }
  ]
}

```

**Key Fields:**

| Field | Description |
| --- | --- |
| **insCode_P** | Call option instrument ID |
| **insCode_C** | Put option instrument ID |
| **uaInsCode** | Underlying asset ID |
| **contractSize** | Contract size |
| **strikePrice** | Strike price |
| **endDate** | Expiration (maturity) date |
| **remainedDay** | Remaining days until expiration |
| **pMeDem_P** | Best bid price for Call option |
| **pMeOf_P** | Best ask price for Call option |
| **pMeDem_C** | Best bid price for Put option |
| **pMeOf_C** | Best ask price for Put option |

**Usage:** Retrieving information on option contracts, underlying assets, strike prices, expiration dates, and top order book entries.
**Note:** This JSON represents a summarized structure of the observed fields; the actual response includes more fields.

---

## 3. General Market Watch 🌐

**Endpoint:**
`GET /ClosingPrice/GetMarketWatch`

**Example:**
`GET [https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=0&paperType=0&symbol=0](https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=0&paperType=0&symbol=0)`

**Sample Output Structure:**

```json
{
  "marketwatch": [
    {
      "insID": "...",
      "insCode": "46348559193224090",
      "lva": "...",
      "lvc": "...",
      "blDs": "...",
      "pClosing": 4410,
      "pDrCotVal": 4410,
      "zTotTran": 7487,
      "qTotTran5J": 860303768
    }
  ]
}

```

**Observed Key Fields:**

| Field | Description |
| --- | --- |
| **insID** | Instrument ID |
| **insCode** | Trading instrument code |
| **lva** | Text field present in market data |
| **lvc** | Text field present in market data |
| **blDs** | Text field present in market data |
| **pClosing** | Closing price |
| **pDrCotVal** | Last trade price |
| **zTotTran** | Number of trades |
| **qTotTran5J** | Trading volume |

**Usage:** Retrieving general market overview and market watch data for trading instruments.
**Note:** The exact meaning of all proprietary fields, particularly `lva`, `lvc`, and `blDs`, should be determined by inspecting the complete dataset and comparing it with the TSETMC user interface.

---

## 4. Basic Instrument Information and Specifications 🏢

**Endpoint:**
`GET /Instrument/GetInstrumentInfo/{insCode}`

**Example:**
`GET [https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/46348559193224090](https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/46348559193224090)`

**Observed Actual Output Structure:**

```json
{
  "instrumentInfo": {
    "eps": {
      "epsValue": null,
      "estimatedEPS": "693",
      "sectorPE": 11.87,
      "psr": 2541.02
    },
    "sector": {
      "dEven": 0,
      "cSecVal": "27 ",
      "lSecVal": "فلزات اساسي"
    },
    "staticThreshold": {
      "insCode": null,
      "dEven": 0,
      "hEven": 0,
      "psGelStaMax": 4540.0,
      "psGelStaMin": 4280.0
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
    "cValMne": null,
    "lVal18": "S*Mobarakeh Steel",
    "cSocCSAC": null,
    "lSoc30": null,
    "yMarNSC": null,
    "yVal": "300",
    "insCode": "46348559193224090",
    "lVal30": "فولاد مباركه اصفهان",
    "lVal18AFC": "فولاد",
    "flow": 1,
    "cIsin": "IRO1FOLD0009",
    "zTitad": 1935000000000.0,
    "baseVol": 1,
    "instrumentID": "IRO1FOLD0001",
    "cgrValCot": "N1",
    "cComVal": "1",
    "lastDate": 0,
    "sourceID": 1,
    "flowTitle": "بازار بورس",
    "cgrValCotTitle": "بازار اول (تابلوی اصلی) بورس"
  }
}

```

**Key Fields:**

| Field | Description |
| --- | --- |
| **insCode** | Instrument ID |
| **lVal18AFC** | Trading symbol (Ticker) |
| **lVal30** | Full instrument name |
| **cIsin** | ISIN code |
| **instrumentID** | Alternative instrument ID format |
| **flow** | Market flow code |
| **flowTitle** | Market title |
| **cgrValCotTitle** | Trading board title |
| **eps.estimatedEPS** | Estimated EPS |
| **eps.sectorPE** | Sector P/E ratio |
| **eps.psr** | PSR ratio |
| **sector.lSecVal** | Sector (Industry) name |
| **minWeek** | Weekly low price |
| **maxWeek** | Weekly high price |
| **minYear** | Annual low price |
| **maxYear** | Annual high price |
| **staticThreshold.psGelStaMax** | Upper static price threshold |
| **staticThreshold.psGelStaMin** | Lower static price threshold |
| **baseVol** | Base volume |
| **zTitad** | Total number of shares |
| **underSupervision** | Supervision status |
| **dEven** | Date recorded in the response |

**Usage:** Retrieving basic symbol specifications, industry sector, EPS, price thresholds, and market information.

---

## 5. Daily Price History 📈

**Endpoint:**
`GET /ClosingPrice/GetClosingPriceDailyList/{insCode}/0`

**Example:**
`GET [https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/46348559193224090/0](https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/46348559193224090/0)`

**Observed Actual Output Structure:**

```json
{
  "closingPriceDaily": [
    {
      "priceChange": 120.0,
      "priceMin": 4410.0,
      "priceMax": 4410.0,
      "priceYesterday": 4290.0,
      "priceFirst": 4410.0,
      "last": false,
      "id": 0,
      "insCode": "46348559193224090",
      "dEven": 20261107,
      "hEven": 122952,
      "pClosing": 4410.0,
      "iClose": false,
      "yClose": true,
      "pDrCotVal": 4410.0,
      "zTotTran": 7487.0,
      "qTotTran5J": 860303768.0,
      "qTotCap": 3793939616880.0
    }
  ]
}

```

**Key Fields:**

| Field | Description |
| --- | --- |
| **insCode** | Instrument ID |
| **dEven** | Trading date |
| **hEven** | Recorded time (HHMMSS) |
| **priceChange** | Price change compared to the previous day |
| **priceMin** | Daily low price |
| **priceMax** | Daily high price |
| **priceYesterday** | Previous day's price |
| **priceFirst** | Opening (first trade) price |
| **pClosing** | Closing price |
| **pDrCotVal** | Last trade price |
| **zTotTran** | Number of trades |
| **qTotTran5J** | Trading volume |
| **qTotCap** | Trading value |
| **last** | Record status field |
| **iClose** | Record status field |
| **yClose** | Record status field |

**Test Result:** 4,677 records were retrieved for the symbol "فولاد" (`insCode=46348559193224090`).
**Usage:** Retrieving historical price, volume, value, and trade count data for technical analysis and market trend evaluation.

---

## 6. Intraday Trade History ⏱️

**Endpoint:**
`GET /Trade/GetTradeHistory/{insCode}/{YYYYMMDD}/false`

**Example:**
`GET [https://cdn.tsetmc.com/api/Trade/GetTradeHistory/46348559193224090/20261107/false](https://cdn.tsetmc.com/api/Trade/GetTradeHistory/46348559193224090/20261107/false)`

**Observed Actual Output Structure:**

```json
{
  "tradeHistory": [
    {
      "insCode": null,
      "dEven": 0,
      "nTran": 7487,
      "hEven": 122952,
      "qTitTran": 1700,
      "pTran": 4410.0,
      "qTitNgJ": 0,
      "iSensVarP": "\u0000",
      "pPhSeaCotJ": 0.0,
      "pPbSeaCotJ": 0.0,
      "iAnuTran": 0,
      "xqVarPJDrPRf": 0.0,
      "canceled": 0
    }
  ]
}

```

**Key Fields:**

| Field | Description |
| --- | --- |
| **nTran** | Trade number |
| **hEven** | Trade execution time (HHMMSS) |
| **qTitTran** | Number of shares traded |
| **pTran** | Trade price |
| **qTitNgJ** | Quantity field in trade structure |
| **canceled** | Trade cancellation status |
| **insCode** | Returned `null` in the sample response |
| **dEven** | Returned `0` in the sample response |
| **iSensVarP** | Status/variation type field |
| **pPhSeaCotJ** | Price field |
| **pPbSeaCotJ** | Price field |
| **iAnuTran** | Status field |
| **xqVarPJDrPRf** | Numeric variation field |

**Test Result:** 7,491 records were retrieved for the symbol "فولاد" on date `20261107`.
**Usage:** Retrieving tick-by-tick daily trade details to analyze trading behavior, individual trade volume, price, and execution time.
**Note:** The exact meaning of some less frequently used fields and the `false` parameter still requires independent verification. In the sample output, `insCode` was `null` and `dEven` was `0`; the date and instrument ID are specified via the URL path.