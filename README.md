# Zerodha AI Intelligence

A local portfolio and market research dashboard built with Next.js, React, TypeScript, FastAPI, SQLite, Groq, and Alpha Vantage. Review a portfolio you provide, explore its allocation and concentration, look up quotes on demand, research market news with citations, and model financial scenarios.

> **Unofficial educational demo.** This project is not affiliated with or endorsed by Zerodha. It is not a broker, does not connect to a Zerodha account, and does not place trades. It has no login or multi-user access control and has not had a production security review. Run it locally; do not expose it to the public internet or use its outputs as investment advice.

## Project submission materials

- **Project presentation and demo guide:** [Download the PDF](docs/Zerodha-AI-Intelligence-Project-Presentation-Demo-Guide.pdf).

## Features

### Portfolio overview

- Starts empty. The app does not invent sample positions or seed fake holdings.
- Calculates current value, invested value, unrealized return, position count, and sector allocation from the prices saved in your portfolio.
- Shows concentration observations and the largest position, sector, and return contributor.
- Search holdings by ticker, name, or sector.
- Shows that the portfolio snapshot is based on saved prices; it does not store historical prices or generate a historical performance chart.

### Import and review

- Import CSV files (up to 5 MB) or PNG, JPEG, and WebP holdings screenshots (up to 10 MB).
- CSV parsing happens locally in the backend. Screenshot extraction uses Groq Vision; the chosen image is sent to Groq for processing.
- Review the extracted rows and values before confirming and saving them.
- CSV rows need a symbol, quantity, average price, and current price. Use a header row; see [CSV format](#csv-import-format).
- Treat extracted data as a draft and verify ticker, quantity, average cost, and current price before confirming.

### Portfolio explorer and risk

- Explore saved holdings, returns, and sector exposure.
- Risk view reports value concentration (HHI), largest holding, top-three weight, largest sector, and cross-sectional dispersion of saved daily moves.
- Annualized volatility, maximum drawdown, Sharpe ratio, beta/correlation, and benchmark comparison are intentionally not fabricated: they require dated price or return history that this demo does not keep.

### Market Data

- Look up one ticker at a time or select a holding to request its latest available Alpha Vantage `GLOBAL_QUOTE`.
- Displays provider date, price, daily change, previous close, high, low, and volume when returned by the provider.
- Requests happen only when you click to fetch a quote. Results are cached and requests are throttled and capped using the configured API plan limits.
- A fetched quote for a portfolio holding can update its saved current price.

**This is not a streaming feed.** Alpha Vantage global-market data is generally end-of-day unless your account has an applicable realtime/delayed entitlement. Symbol availability and suffixes vary. Bare symbols are mapped to `.BSE` by this India-focused demo; confirm the provider's supported ticker format and quote date before relying on a value. A quote may consume provider quota unless it is served from cache.

### News and AI Analyst

- News search uses Groq's web-search-capable model and displays citations/sources when the provider returns them.
- The AI Analyst can answer questions using the confirmed portfolio and can search current market context for market/news questions.
- Portfolio-only answers can fall back to a local rule-based response when a Groq key is not configured; live web research requires a working Groq key, model access, network access, and provider availability.
- Answers may return without citations if the model/provider supplies no sources. Always open and review source links yourself.

### Watchlist

- Add and remove symbols, saved in the local database.
- Request a quote for an individual watchlist ticker on demand. Watchlist quotes use the same Alpha Vantage cache and quota controls as Market Data.

### Financial calculators

Interactive estimates for:

- SIP and step-up SIP corpus
- SWP sustainability
- Loan EMI
- CAGR
- Inflation-adjusted future cost
- Retirement savings projection
- Goal planning
- Fixed deposit and recurring deposit maturity estimates
- XIRR from editable, dated positive and negative cash flows

Calculators update as assumptions change. Their results are mathematical scenarios, not forecasts or guaranteed returns; taxes, fees, product terms, and market variability may not be included.

## Architecture

- **Frontend:** Next.js App Router, React, TypeScript, Recharts, Lucide icons.
- **Backend:** FastAPI service for portfolio persistence, imports, quotes, watchlist, portfolio analysis, and AI responses.
- **Storage:** SQLite, defaulting to `backend/zerodha-demo.db`.
- **Providers:** Alpha Vantage for quote lookup; Groq for vision extraction, AI answers, and grounded web/news research.
- **Local API routing:** Next.js rewrites `/api/*` to FastAPI at `http://127.0.0.1:8000` in development. A root `.env.local` is not required. Set `API_ORIGIN` there only if the backend is hosted at a different local address, then restart Next.js.

## Requirements

- Windows, macOS, or Linux
- Node.js 20 or later and npm
- Python 3.11 or later
- Alpha Vantage API key for market quotes (optional until you use quote features)
- Groq API key for screenshot extraction, AI explanations, and live news/market search (optional; features that need it will show a setup message)

## Quick start on Windows

From the project root, double-click `start-all.bat`. On first run it sets up dependencies and starts the backend and frontend. Then open [http://localhost:3000](http://localhost:3000).

If you prefer to start the services manually, use two PowerShell terminals from the project root.

**Terminal 1 â€” backend:**

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In `backend/.env`, set the provider keys you need (see [Configuration](#configuration)). Keep this terminal running.

**Terminal 2 â€” frontend:**

```powershell
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The backend API health endpoint is [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health).

> If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again.

## Quick start on macOS/Linux

**Terminal 1 â€” backend:**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
# Edit backend/.env and add the keys you need.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 â€” frontend** (project root):

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Configuration and API keys

Copy `backend/.env.example` to `backend/.env` and edit that local file. Do not place provider keys in frontend code, `.env.local`, README, screenshots, or Git commits.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Runtime mode; local setup uses `development`. |
| `DATABASE_URL` | SQLite database path; default is `sqlite:///./zerodha-demo.db` relative to the backend working directory. |
| `GROQ_API_KEY` | Groq key for screenshot extraction and AI responses. Leave blank to disable Groq-powered features. |
| `GROQ_MODEL` | Text model used for portfolio-focused questions. |
| `GROQ_SEARCH_MODEL` | Web-search-capable model used for market/news questions. |
| `GROQ_VISION_MODEL` | Vision model used to extract holdings from screenshots. |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage key for quote lookups. |
| `ALPHA_VANTAGE_BASE_URL` | Alpha Vantage query endpoint; normally leave at its example value. |
| `ALPHA_VANTAGE_CACHE_SECONDS` | How long quote responses are cached per ticker (default 900 seconds). |
| `ALPHA_VANTAGE_DAILY_LIMIT` | Local daily request cap (default 25; match your provider plan). |
| `ALPHA_VANTAGE_MIN_INTERVAL_SECONDS` | Minimum interval between provider requests (default 12.1 seconds). |

Get keys from [Alpha Vantage](https://www.alphavantage.co/support/#api-key) and [Groq Console](https://console.groq.com/keys). Their availability, model access, and usage limits are controlled by those providers. The frontend `.env.example` contains only the optional `API_ORIGIN` proxy setting; provider secrets belong in the backend environment only.

## CSV import format

Use a comma-separated UTF-8 file with a header row and one row per position. The importer accepts common aliases for the required fields, such as `symbol`/`ticker`, `quantity`/`qty`, `average_price`/`avg_price`, and `current_price`/`ltp`.

```csv
symbol,quantity,average_price,current_price,sector,name
INFY,10,1450.00,1600.00,IT,Infosys
TCS,5,3600.00,3900.00,IT,Tata Consultancy Services
```

Quantity and prices must be valid numbers. Sector and name are optional; missing values are shown as unclassified or use the ticker. The preview is not saved until you confirm it in the app. Do not include account numbers, client identifiers, or other personal information in an import file.

## Local data and privacy

The backend stores the portfolio, watchlist, quote cache, and local Alpha Vantage usage counter in SQLite. There is one shared local workspace and no user login boundary. CSV contents are processed by the local backend. Selected portfolio screenshots are transmitted to Groq Vision for extraction. AI and news questions are transmitted to Groq; quote symbols are sent to Alpha Vantage. Review each provider's terms and privacy policy before using these features. Do not upload sensitive account documents or expose the local service to a public network.

Real `.env` and `.env.local` files, the SQLite database, dependency folders, and build output are ignored by Git and excluded from the release package. `.env.example` files contain placeholders only. **Never commit real API keys.** If a key has been shared or exposed, revoke/rotate it with its provider.

## API endpoints

FastAPI exposes these local endpoints under `/api`:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend health check. |
| `GET` | `/v1/portfolio/holdings` | Read saved holdings. |
| `PUT` | `/v1/portfolio/holdings` | Save confirmed holdings. |
| `POST` | `/v1/portfolio/preview-csv` | Parse and preview a CSV import. |
| `POST` | `/v1/portfolio/preview-image` | Extract and preview holdings from an image. |
| `POST` | `/v1/portfolio/analyze` | Calculate portfolio analysis. |
| `GET` / `PUT` | `/v1/watchlist` | Read or save watchlist symbols. |
| `GET` | `/v1/market/quotes?symbol=INFY` | Request a single ticker quote. |
| `POST` | `/v1/ai/answer` | Ask a portfolio or market/news question. |

Interactive API documentation is available at [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) while the backend is running.

## Development checks

Run from the project root:

```bash
npm run lint
npm run build
```

Backend package dependencies are listed in `backend/requirements.txt`. `backend/requirements-dev.txt` contains development tools.

## Troubleshooting

- **The UI reports it cannot reach the service:** keep the FastAPI terminal running on port 8000; check `/api/health`, then refresh the frontend.
- **An API request shows HTML or a 404:** confirm you opened the Next.js app at port 3000 and that the backend is running at port 8000. The frontend proxy forwards `/api/*` requests.
- **Quote setup/quota/provider errors:** verify `ALPHA_VANTAGE_API_KEY`, ticker support, provider limits, and the response date. Cached responses may be served without a new provider request.
- **Screenshot import fails:** use a clear, small screenshot that visibly includes symbol, quantity, average price, and current price; check `GROQ_API_KEY`, vision model access, and provider limits. Review the preview before saving.
- **News search has no sources or returns no answer:** verify Groq key/model access and network/provider availability. Citations depend on the response from the search model; retry or inspect the source links returned when present.
- **Frontend dependency install/build issue:** use Node.js 20+, run `npm install` at the project root, then retry the relevant command.

## License

No license file is currently included. Unless a license is added, standard copyright applies and reuse or redistribution is not automatically granted.

