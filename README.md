# StockPilot AI

StockPilot AI is my project for exploring portfolio holdings, checking available stock quotes, researching market news, and trying financial calculations. It runs locally with a Next.js frontend, a FastAPI backend, and SQLite storage.

## Project presentation

[Open the project presentation and demo guide](docs/Zerodha-AI-Intelligence-Project-Presentation-Demo-Guide.pdf).

## Features

### Portfolio overview

- Starts with an empty portfolio; it does not add sample holdings.
- Shows current value, invested amount, returns, number of positions, and sector allocation based on saved prices.
- Highlights the largest position, sector, and return contributor.
- Search holdings by ticker, name, or sector.
- Shows that the overview is a current snapshot. Historical prices are not stored.

### Import and review

- Import CSV files up to 5 MB or PNG, JPEG, and WebP screenshots up to 10 MB.
- CSV files are parsed locally by the backend.
- Screenshot extraction uses Groq Vision and sends the selected image to Groq.
- Review imported or extracted values before confirming and saving them.
- Required values are symbol, quantity, average price, and current price. Sector and name are optional.

### Portfolio and risk

- Explore saved holdings, returns, and sector exposure.
- Review concentration using the HHI index, largest holding, top three positions, largest sector, and saved daily price moves.
- Annualized volatility, maximum drawdown, Sharpe ratio, beta, correlation, and benchmark comparisons need dated price history. The app does not store that history, so it does not estimate these metrics.

### Market Data

- Request the latest available Alpha Vantage quote for one ticker at a time or for a portfolio holding.
- View the provider date, price, daily change, previous close, high, low, and volume when available.
- Quotes are requested on demand, cached, and limited by the configured provider quota.
- A quote for a portfolio holding can update its saved current price.

This is not a streaming feed. Alpha Vantage global quotes may be end-of-day unless the account has an applicable real-time or delayed-data entitlement. Symbol availability and suffixes vary. Bare symbols in this project are mapped to `.BSE`; check the provider's supported symbol and the quote date.

### News and AI Analyst

- Search for market news and context using Groq's web-search-capable model.
- Ask questions about the confirmed portfolio.
- Show source citations when the provider returns them.
- Portfolio questions can use a local rule-based response if Groq is not configured. Live news and market search require a working Groq key and available model access.

Answers may not include citations if the search response does not provide sources. Check any cited material yourself.

### Watchlist

- Add and remove symbols from a watchlist stored in the local database.
- Request quotes for individual watchlist symbols when needed.
- Watchlist quote requests use the same cache and provider limits as Market Data.

### Financial calculators

The calculators cover:

- SIP and step-up SIP
- SWP
- Loan EMI
- CAGR
- Inflation-adjusted cost
- Retirement savings
- Goal planning
- Fixed deposits and recurring deposits
- XIRR using editable, dated cash flows

Calculations update when assumptions change. They are estimates, not guaranteed returns, and may exclude taxes, fees, product rules, and market changes.

## Technology

- **Frontend:** Next.js App Router, React, TypeScript, Recharts, and Lucide icons
- **Backend:** FastAPI
- **Storage:** SQLite
- **Market quotes:** Alpha Vantage
- **AI answers, news research, and screenshot extraction:** Groq

## Requirements

- Windows, macOS, or Linux
- Node.js 20 or newer and npm
- Python 3.11 or newer
- Alpha Vantage API key for quotes (optional until using quote features)
- Groq API key for AI answers, news research, and screenshot extraction (optional until using those features)

## Run on Windows

Start the backend and frontend in separate PowerShell terminals from the project folder.

### 1. Start the backend

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

Add the provider keys you need to `backend/.env`. Keep this terminal open.

### 2. Start the frontend

Open another PowerShell terminal at the project root:

```powershell
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The backend health check is [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health). Interactive API documentation is available at [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) while the backend is running.

If PowerShell blocks virtual-environment activation, run this in the backend terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run on macOS or Linux

### 1. Start the backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and add the provider keys you need, then start FastAPI:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Start the frontend

Open a second terminal at the project root:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Configuration and API keys

Copy `backend/.env.example` to `backend/.env`. Provider keys belong in the backend environment, not in frontend code or the root `.env.local`.

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Runtime mode. Use `development` for local work. |
| `DATABASE_URL` | SQLite database path. The default is `sqlite:///./zerodha-demo.db` relative to the backend working directory. |
| `GROQ_API_KEY` | Groq key for AI answers, news search, and screenshot extraction. |
| `GROQ_MODEL` | Text model for portfolio questions. |
| `GROQ_SEARCH_MODEL` | Model for market and news search. |
| `GROQ_VISION_MODEL` | Vision model for screenshot extraction. |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage key for quote lookups. |
| `ALPHA_VANTAGE_BASE_URL` | Alpha Vantage query endpoint. |
| `ALPHA_VANTAGE_CACHE_SECONDS` | Quote cache duration; default is 900 seconds. |
| `ALPHA_VANTAGE_DAILY_LIMIT` | Local daily quote request cap; default is 25. Set this according to your provider plan. |
| `ALPHA_VANTAGE_MIN_INTERVAL_SECONDS` | Minimum time between provider requests; default is 12.1 seconds. |

Get keys from [Alpha Vantage](https://www.alphavantage.co/support/#api-key) and [Groq Console](https://console.groq.com/keys). Provider access and limits depend on your account.

The frontend `.env.example` is for the optional `API_ORIGIN` proxy setting. A root `.env.local` is not required for the default local setup. If you change `API_ORIGIN`, restart Next.js.

## CSV import format

Use a UTF-8 comma-separated file with a header row and one row per holding. Common field names include `symbol` or `ticker`, `quantity` or `qty`, `average_price` or `avg_price`, and `current_price` or `ltp`.

```csv
symbol,quantity,average_price,current_price,sector,name
INFY,10,1450.00,1600.00,IT,Infosys
TCS,5,3600.00,3900.00,IT,Tata Consultancy Services
```

Quantity and prices must be valid numbers. Sector and name are optional. Imported values are only saved after you review and confirm them.

## Data and privacy

Portfolio holdings, watchlist symbols, cached quotes, and the local Alpha Vantage usage counter are stored in SQLite. The default database file is `backend/zerodha-demo.db`. There is one local workspace and no login or multi-user access control.

CSV files are processed by the local backend. Selected screenshots and AI questions are sent to Groq. Quote symbols are sent to Alpha Vantage. Avoid uploading sensitive account documents, and review each provider's terms before using its services.

Real `.env` files, the database, dependency folders, and build output should stay out of Git. The example environment files contain blank credentials. Never commit real API keys.

## API endpoints

FastAPI provides these local endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend health check. |
| `GET` | `/api/v1/portfolio/holdings` | Read saved holdings. |
| `PUT` | `/api/v1/portfolio/holdings` | Save confirmed holdings. |
| `POST` | `/api/v1/portfolio/preview-csv` | Parse and preview a CSV. |
| `POST` | `/api/v1/portfolio/preview-image` | Extract and preview holdings from an image. |
| `POST` | `/api/v1/portfolio/analyze` | Analyze portfolio holdings. |
| `GET` and `PUT` | `/api/v1/watchlist` | Read or save watchlist symbols. |
| `GET` | `/api/v1/market/quotes?symbol=INFY` | Request a ticker quote. |
| `POST` | `/api/v1/ai/answer` | Ask a portfolio or market question. |

## Development commands

Run these commands from the project root:

```powershell
npm run lint
npm run build
```

Backend dependencies are listed in `backend/requirements.txt`. Development tools are listed in `backend/requirements-dev.txt`.

## Troubleshooting

- **The app cannot reach the backend:** Keep FastAPI running on port 8000, check [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health), then refresh the frontend.
- **A request returns a 404 or HTML page:** Open the frontend at port 3000 and confirm the backend is running at port 8000.
- **Quote lookup fails:** Check `ALPHA_VANTAGE_API_KEY`, the ticker format, provider quota, and quote date.
- **Screenshot import fails:** Use a clear image showing symbol, quantity, average price, and current price. Check the Groq key, model access, and provider limits. Review the extracted preview before saving.
- **News search returns no answer or sources:** Check Groq key and model access. Sources depend on what the search response returns.
- **Frontend install or build fails:** Confirm Node.js 20 or newer, run `npm install` from the project root, then retry.
