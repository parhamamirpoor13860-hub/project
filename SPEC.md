# Role & Objective
You are a Senior Data Engineer and Full-Stack Developer. Your task is to design and implement **Phase 1 of the "Trading Algorithms" course project**: a fully Dockerized **TSETMC Options Market Tick-Data Platform** (from 1402 SH / March 21, 2023 to the present).

The platform must discover all active and expired option contracts and their underlying assets on the Tehran Stock Exchange (TSETMC), crawl their historical daily and intraday tick-by-tick trades, store immutable raw responses, clean/validate the data, build continuous time-series/OHLCV candles, and serve them via a Backend API and Frontend Web UI.

---

# 1. Data Scope, Domain & Tech Stack
- **Target Market:** Iran Stock Market (TSETMC - `https://cdn.tsetmc.com`) Options Market (بازار اختیار معامله) and their Underlying Assets (دارایی‌های پایه).
- **Coverage:**
  - All **25 underlying assets** (دارایی پایه) in the options market (e.g., اهرم، خودرو، فملی، شستا, etc.) AND all their Call (اختیار خرید - `ض...`) and Put (اختیار فروش - `ط...`) contracts.
  - **CRITICAL:** You must crawl daily and intraday tick data for **both the option contracts AND the 25 underlying assets** so that option trades can be matched with simultaneous underlying prices in Stage 5.
  - Timeframe: **From start of 1402 SH (March 21, 2023 / `20230321`) up to today**.
  - Must include **both currently active contracts (~1,584+) AND expired (منقضی‌شده) contracts** from 1402, 1403, and 1404.
- **Data Types per Instrument (`insCode`):**
  1. Instrument Registry & Metadata (Strike price, expiration date, contract size / `cSize`, Call/Put type, underlying asset `insCode`, symbol `lVal18AFC`, full name `lVal30`).
  2. Daily History (تاریخچه روزانه - open, high, low, close `pClosing`, last price `pDrCotVal`, volume `qTotTran5J`, value `qTotCap`, trade count `zTotTran` per day).
  3. Intraday Tick Data (داده تیک - every individual trade with exact timestamp, sequence number, price, volume, and cancellation status for every trading day).
- **Fixed Tech Stack:**
  - **Backend & Pipeline:** Python 3.11+, `FastAPI`, `httpx` / `aiohttp` (async crawler), `DuckDB` + `Parquet` (or `PostgreSQL` / `SQLite` for metadata & state management), `Pydantic`, `pytest`.
  - **Frontend:** React (TypeScript + Vite), Tailwind CSS, and **TradingView Lightweight Charts (`lightweight-charts`)** for interactive financial candlestick and line charts.
  - **Infrastructure:** Docker & Docker Compose (`docker compose up --build`).

---

# 2. TSETMC CDN API Technical Reference (MANDATORY FILE READ)
- The complete, production-verified technical documentation and JSON response schemas for `https://cdn.tsetmc.com/api` are stored in the repository at:
  **`docs/TSETMC_API.md`**
- **CRITICAL RULE:** Before writing any HTTP client, Pydantic model, fixture generator, or parser in Stages 1, 2, 3, and 4, you **MUST read `docs/TSETMC_API.md` in full**. Do NOT guess or hallucinate TSETMC endpoint URLs or JSON field names.
- **Key Edge Cases Verified in `docs/TSETMC_API.md` (Must Handle in Code):**
  1. In `/Trade/GetTradeHistory/{insCode}/{YYYYMMDD}/false`, every item inside `"tradeHistory"` returns `"insCode": null` and `"dEven": 0`. You MUST inject `insCode` and `dEven` from the request parameters / file path.
  2. Filter out canceled trades (`canceled != 0`) when reconciling against `closingPriceDaily.zTotTran` and `qTotTran5J` (e.g., on `20261107` for `فولاد`, raw ticks = `7491`, canceled = `4`, valid trades = `7487` matching `zTotTran`).
  3. In `/Instrument/GetInstrumentOptionMarketWatch/0`, each row pairs both Call (`insCode_C`, `pMeDem_C`, `pMeOf_C`) and Put (`insCode_P`, `pMeDem_P`, `pMeOf_P`) alongside the underlying asset (`uaInsCode`).
---

# 3. Six-Stage Pipeline Architecture (Phase 1)

**CRITICAL RULE:** Every stage must first be developed and tested against a **small local fixture (sample data of 1–2 underlying assets and 2–3 option contracts over a few days)** before running on the full dataset.

### Stage 1: Discovery & Instrument Registry (کشف و رجیستری ابزارها)
- **Challenge:** Expired options no longer appear on the active Options Watchlist.
- **Solution:** Combine multiple discovery strategies to guarantee 100% coverage of active and expired contracts from `1402/01/01` (`20230321`) to today:
  1. Query historical traded instruments across trading days (~700–800 trading days from 1402/01/01 to today) and/or systematically query `GetInstrumentSearch` across option naming prefixes (`ض...` and `ط...`) for all 25 underlying assets.
  2. Combine with active Option Watchlist endpoints.
  3. Filter for option contracts (by instrument type / `cgrValCot` / `yVal`, naming pattern `ض`/`ط`, and contract size), collect all unique `insCode`s, and enrich their metadata via `GetInstrumentInfo/{insCode}` (parsing strike price, maturity/expiration date, contract size, Call/Put type, and underlying asset link).

### Stage 2: Fault-Tolerant Crawler (خزش)
- Fetch `GetClosingPriceDailyList/{insCode}/0` first for every discovered instrument (underlying + options).
- **Optimization:** Only request intraday tick data (`GetTradeHistory/{insCode}/{YYYYMMDD}/false`) for `(insCode, YYYYMMDD)` pairs where `YYYYMMDD >= 20230321` AND the Daily History indicates that trades actually occurred (`zTotTran > 0`).
- Must send standard browser headers (`User-Agent`, `Accept: application/json`, `Accept-Encoding: gzip, deflate`) with a sensible timeout (e.g., 20s).
- **Politeness & Reliability Requirements:**
  - Strict Rate Limiting (e.g., max 2 requests/second, configurable concurrency/sleep between requests).
  - Exponential backoff retry logic on HTTP 429/5xx or network timeouts.
  - **Resumability (Checkpointing):** Track crawled `(insCode, date)` pairs in a manifest/state table (SQLite/DuckDB) so the crawler can stop and resume seamlessly without re-downloading.
  - **Time-Window Guard:** Heavy crawling must be configurable to pause or throttle during Tehran market trading hours (09:00 to 12:30 `Asia/Tehran`, Sat–Wed). Stop immediately and log if blocked/banned (HTTP 403).

### Stage 3: Immutable Raw Storage (ذخیره خام)
- Save every raw API response **without modification** before parsing.
- Format: Discrete compressed files (`gzip`), **one file per instrument per trading day** (`data/raw/ticks/{insCode}/{YYYYMMDD}.json.gz` and `data/raw/daily/{insCode}.json.gz`), accompanied by an index/manifest record logging download timestamp, HTTP status, compressed byte size, and raw record count.

### Stage 4: Cleaning, Parsing & Quality Validation (تمیزکاری و اعتبارسنجی)
- **Filtering & Exact Chronological Sorting:**
  - Read raw files and preserve all fields.
  - Filter out canceled trades (`canceled != 0`) when computing valid trade counts/volumes (keep a flag or separate log of canceled trades for auditing).
  - **CRITICAL:** Multiple trades frequently occur within the exact same second on TSETMC. Sort trades chronologically using `(dEven ASC, hEven ASC, nTran ASC)` so intra-second trade ordering is 100% deterministic.
- **Timestamp Standardization (No-DST Rule):**
  - Convert `dEven` (e.g., `20230524`) and integer `hEven` (zero-pad 5-digit numbers like `90005` -> `09:00:05`, 6-digit `104045` -> `10:40:45`).
  - **Iran Timezone Note:** Iran permanently abolished Daylight Saving Time (DST) in 1402 SH (March 2023). Ensure all timestamps from 1402 onwards use a **fixed `+03:30` offset** (`2023-05-24T09:00:05+03:30`) and convert accurately to `ts_utc` (`2023-05-24T05:30:05Z`). Do NOT let legacy `tzdata` apply `+04:30` summer offsets.
- **Data Quality & Reconciliation Report:**
  - Compare the number of valid tick trades (`count`) and total volume (`sum(qTitTran)`) on each day against `zTotTran` and `qTotTran5J` in the official Daily History row for that instrument.
  - Generate an automated **Data Quality Report** showing match rates, missing days, anomalies, and data gaps.
  - **Acceptance Target:** Tick trade counts/volumes must reconcile with daily history on **at least 98% of traded days**.

### Stage 5: Unified Sequences & Continuous Series (دنباله یکپارچه)
- Transform discrete irregular tick trades into continuous, analysis-ready structures (stored in Parquet/DuckDB):
  1. **Clean Tick Stream with Underlying Price (`ASOF JOIN`):** Chronological option tick trades linked with the exact last-traded price of the underlying asset at or immediately prior to each option trade (`ts_option >= ts_underlying`).
  2. **Intraday Candles (OHLCV):** Resample ticks into **1m, 5m, 15m, and 1h candles** (plus 1d candles). Handle sparse/illiquid intervals (where no trade happens for minutes) by tracking both actual traded OHLCV and forward-filled reference price (`close_ffill`), volume=0 markers, and historical adjustments.
  3. **Option Chain View:** Group contracts by underlying asset, expiration date (and Days to Expiration `DTE`), Strike price, Call/Put, and dynamic ITM/ATM/OTM moneyness status relative to the underlying asset's price.

### Stage 6: Web Application (Backend API + Frontend UI + Docker)
- **Backend API (FastAPI):**
  - Endpoints to list the 25 underlying assets, search/filter option contracts (active & expired), view historical/current option chains, fetch clean tick streams (with matched underlying prices), fetch resampled candles (`1m`, `5m`, `15m`, `1h`, `1d`), and view the Data Quality/Reconciliation Report.
- **Frontend UI (React + TypeScript + Tailwind + TradingView Lightweight Charts):**
  - Interactive dashboard to search and switch between underlying assets and option contracts across any historical date.
  - Synchronized interactive financial charts (Candlestick/Line charts for option premium and underlying price, volume histogram bars) and Option Chain tables showing Call/Put sides around the Strike prices.
  - Dedicated Data Quality & Reconciliation status dashboard.
- **Dockerization & Reproducibility:**
  - The entire stack (Backend, Frontend, Database/Storage, Seeder) must boot cleanly on a fresh machine using a single command:
    `docker compose up --build`
  - Include a **seed/fixture dataset** committed to the repo so the web app works out-of-the-box with real charts, option chains, and quality reports immediately after `docker compose up --build` without waiting days for a full crawl.
  - Lock all dependency versions (`requirements.txt` / `poetry.lock` and `package-lock.json`).
  - Keep all configs in `.env.example` (no hardcoded secrets in Git).
  - Document architecture, data schema, CLI commands, and AI tool usage clearly in `README.md`.

---

# 4. GitHub Repository Workflow & Network Fallback Policy (MANDATORY)
- **Existing GitHub Repo Check:**
  - The project is already connected to a GitHub repository. Start by inspecting `git status`, `git branch -a`, and `git remote -v`. Do NOT re-run `git init` if `.git` already exists.
  - Ensure `git config user.name` and `git config user.email` are configured locally before making the first commit so `git commit` never fails.
- **Branching, Merging & Pushing Strategy:**
  - Never commit directly to `main`.
  - Create a feature branch for each milestone (`feat/project-setup`, `feat/stage1-discovery`, `feat/stage2-3-crawler-storage`, `feat/stage4-5-cleaning-candles`, `feat/stage6-webapp-docker`).
  - After completing, testing (`pytest`), and committing on a feature branch:
    1. Push the feature branch to GitHub (`git push -u origin <branch-name>`).
    2. Merge it into `main` (`git checkout main && git merge --no-ff <branch-name>`) and push `main` (`git push origin main`). *(If `main` is branch-protected on GitHub and rejects pushes, keep building sequentially on the feature branches and open Pull Requests via `gh pr create` instead).*
- **TSETMC Network / Geo-IP Fallback (CRITICAL FOR CLOUD AGENTS):**
  - `cdn.tsetmc.com` may block or timeout requests coming from non-Iranian cloud/datacenter IPs.
  - Probe connectivity to `https://cdn.tsetmc.com` first with a 10-second timeout. If live requests fail or timeout due to geo-blocking, **do NOT get stuck**: build realistic local JSON fixtures (`data/fixtures/`) that strictly match the exact TSETMC JSON schemas (`closingPriceDaily`, `tradeHistory`, `instrumentInfo`) and run all unit tests, pipeline stages, and the seed database against those fixtures while keeping the live HTTP crawler ready for execution on an Iranian network.
- **Ignore Large Data & Secrets:** Commit `.gitignore` first so `.env`, `venv/`, `node_modules/`, and large `data/raw/` or `data/processed/` directories are never pushed to GitHub, while explicitly tracking `data/fixtures/` (seed data).

---

# 5. Your Immediate Execution Plan
Work incrementally through these 5 milestones, running `pytest` and pushing to GitHub after each milestone:
1. **Milestone 1 (`feat/project-setup`):** Inspect existing repo, configure `.gitignore`, `.env.example`, Python/Node project files, and base `docker-compose.yml` -> **Test, Commit & Push #1**.
2. **Milestone 2 (`feat/stage1-discovery`):** Implement **Stage 1 (Discovery & Instrument Registry)** + realistic TSETMC fixture test -> **Test, Commit & Push #2**.
3. **Milestone 3 (`feat/stage2-3-crawler-storage`):** Implement **Stage 2 & 3 (Fault-Tolerant Resumable Crawler & Immutable `.json.gz` Raw Storage)** + fixture test -> **Test, Commit & Push #3**.
4. **Milestone 4 (`feat/stage4-5-cleaning-candles`):** Implement **Stage 4 & 5 (Cleaning, `+03:30` Timestamp Standardization, Reconciliation Report, `ASOF JOIN` Tick Stream & OHLCV/Option Chain Builder)** + fixture test -> **Test, Commit & Push #4**.
5. **Milestone 5 (`feat/stage6-webapp-docker`):** Implement **Stage 6 (FastAPI Backend, React + Lightweight Charts Frontend, Seed Data Loader & Full Dockerization)** -> **Test, Commit & Push #5**.