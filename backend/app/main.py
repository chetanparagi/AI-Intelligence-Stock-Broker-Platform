from __future__ import annotations

import csv
import asyncio
import base64
import io
import json
import os
import re
import time
from datetime import datetime, timezone, date
from typing import Any

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


def _validate_runtime_config() -> None:
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("This is a local demo without authentication or production security. Do not run it in production.")


_validate_runtime_config()

from app.demo_store import alpha_usage, load_portfolio, load_quote, load_watchlist, require_user, record_alpha_request, save_portfolio, save_quote, save_watchlist

production = os.getenv("APP_ENV", "development").lower() == "production"
app = FastAPI(title="Zerodha AI Intelligence API", version="1.0.0", docs_url=None if production else "/api/docs", openapi_url=None if production else "/api/openapi.json")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])
_alpha_quote_lock = asyncio.Lock()
GROQ_API_BASE = "https://api.groq.com/openai/v1/chat/completions"
# Fallbacks tried if the configured model is unavailable for this key (retired id, no access, etc).
_GROQ_TEXT_FALLBACKS = ["llama-3.1-8b-instant"]
_GROQ_SEARCH_FALLBACKS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
_GROQ_BROWSER_SEARCH_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}


class Holding(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    quantity: float = Field(gt=0)
    average_price: float = Field(gt=0)
    current_price: float = Field(gt=0)
    sector: str = "Unclassified"
    # Optional display fields. These were previously accepted by the frontend but silently
    # dropped on save because they were not declared here, which reset the display name and
    # today's % change to their defaults every time the portfolio was reloaded.
    name: str | None = Field(default=None, max_length=80)
    day_change_percent: float = Field(default=0.0, ge=-100, le=1000)


class AnalyzeRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1, max_length=1000)


class PortfolioSaveRequest(BaseModel):
    holdings: list[Holding] = Field(max_length=1000)


class WatchlistSaveRequest(BaseModel):
    symbols: list[str] = Field(max_length=200)


class AnalystRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)
    holdings: list[Holding] = Field(default_factory=list, max_length=1000)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "zerodha-ai-demo-api", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/market/quotes")
async def market_quote(symbol: str = Query(min_length=1, max_length=32)) -> dict[str, Any]:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Set ALPHA_VANTAGE_API_KEY in backend/.env to enable market quotes.")
    original = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]{1,32}", original):
        raise HTTPException(status_code=422, detail="Enter one ticker symbol, such as INFY or IBM.")
    # Bare symbols in this India-focused demo map to Alpha Vantage's documented BSE suffix.
    av_symbol = original if "." in original else f"{original}.BSE"
    cache_seconds = max(60, int(os.getenv("ALPHA_VANTAGE_CACHE_SECONDS", "900")))
    cached = load_quote(av_symbol, cache_seconds)
    if cached:
        return {"quote": {**cached, "symbol": original}, "provider_symbol": av_symbol, "source": "Alpha Vantage", "freshness": "cached quote"}
    today = date.today().isoformat()
    async with _alpha_quote_lock:
        # Recheck after acquiring the lock to avoid duplicate calls from overlapping tabs.
        cached = load_quote(av_symbol, cache_seconds)
        if cached:
            return {"quote": {**cached, "symbol": original}, "provider_symbol": av_symbol, "source": "Alpha Vantage", "freshness": "cached quote"}
        count, last_request = alpha_usage(today)
        if count >= int(os.getenv("ALPHA_VANTAGE_DAILY_LIMIT", "25")):
            raise HTTPException(status_code=429, detail="Alpha Vantage's configured daily request budget is used up. Cached quotes remain available; try again tomorrow or adjust your provider plan and local limit.")
        min_interval = max(0.0, float(os.getenv("ALPHA_VANTAGE_MIN_INTERVAL_SECONDS", "12.1")))
        wait = min_interval - (time.time() - last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        record_alpha_request(today, time.time())
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(os.getenv("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query"), params={"function": "GLOBAL_QUOTE", "symbol": av_symbol, "apikey": api_key})
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Alpha Vantage quote request failed. Check connectivity and the API key.") from exc
        if data.get("Note") or data.get("Information"):
            raise HTTPException(status_code=429, detail="Alpha Vantage rate limit or plan limit reached. Wait before requesting another quote.")
        if data.get("Error Message"):
            raise HTTPException(status_code=422, detail="Alpha Vantage does not recognize this ticker. Try its exchange suffix, for example RELIANCE.BSE.")
        raw = data.get("Global Quote") or {}
        if not raw.get("05. price"):
            raise HTTPException(status_code=404, detail="Alpha Vantage returned no quote for this symbol. Check its exchange suffix and data entitlement.")
        try:
            last = float(raw["05. price"])
            previous = float(raw.get("08. previous close") or 0)
            quote = {"symbol": original, "last_price": last, "previous_close": previous, "change_percent": float(str(raw.get("10. change percent", "0%")).replace("%", "") or 0), "volume": int(raw.get("06. volume") or 0), "high": float(raw.get("03. high") or 0), "low": float(raw.get("04. low") or 0), "timestamp": raw.get("07. latest trading day"), "retrieved_at": time.time(), "cached": False}
        except (TypeError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=502, detail="Alpha Vantage returned an unexpected quote format.") from exc
        save_quote(av_symbol, quote)
    return {"quote": quote, "provider_symbol": av_symbol, "source": "Alpha Vantage", "freshness": "latest available; global quotes default to end-of-day outside entitled US realtime/delayed data"}


@app.post("/api/v1/portfolio/analyze")
def analyze(payload: AnalyzeRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    rows = []
    for h in payload.holdings:
        invested = h.quantity * h.average_price
        value = h.quantity * h.current_price
        rows.append({"symbol": h.symbol.upper(), "sector": h.sector or "Unclassified", "quantity": h.quantity, "invested_value": round(invested, 2), "market_value": round(value, 2), "pnl": round(value - invested, 2), "pnl_percent": round((value / invested - 1) * 100, 2)})
    invested_total = sum(r["invested_value"] for r in rows)
    value_total = sum(r["market_value"] for r in rows)
    pnl = value_total - invested_total
    sector_totals: dict[str, float] = {}
    for row in rows:
        sector_totals[row["sector"]] = sector_totals.get(row["sector"], 0) + row["market_value"]
    concentration = sum((r["market_value"] / value_total) ** 2 for r in rows) if value_total else None
    return {"summary": {"invested_value": round(invested_total, 2), "market_value": round(value_total, 2), "pnl": round(pnl, 2), "pnl_percent": round(pnl / invested_total * 100, 2) if invested_total else None, "holding_count": len(rows), "hhi": round(concentration, 4) if concentration is not None else None}, "holdings": rows, "sector_allocation": [{"sector": k, "value": round(v, 2), "weight_percent": round(v / value_total * 100, 2) if value_total else None} for k, v in sorted(sector_totals.items(), key=lambda x: x[1], reverse=True)], "data_quality": {"source": "user-provided portfolio", "retrieved_at": datetime.now(timezone.utc).isoformat(), "freshness": "unknown", "status": "partial", "warnings": ["Prices are supplied by the user; no market provider is connected."]}}


@app.get("/api/v1/portfolio/holdings")
def get_portfolio_holdings(user: str = Depends(require_user)) -> dict[str, Any]:
    return {"holdings": load_portfolio(user), "source": "local demo portfolio; uploaded prices or Alpha Vantage quote updates"}


@app.put("/api/v1/portfolio/holdings")
def put_portfolio_holdings(payload: PortfolioSaveRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    rows = [holding.model_dump() for holding in payload.holdings]
    save_portfolio(user, rows)
    return {"holdings": rows, "count": len(rows), "message": "Portfolio saved to your account."}


@app.get("/api/v1/watchlist")
def get_watchlist(user: str = Depends(require_user)) -> dict[str, Any]:
    return {"symbols": load_watchlist(user)}


@app.put("/api/v1/watchlist")
def put_watchlist(payload: WatchlistSaveRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in payload.symbols if symbol.strip()))
    if any(not re.fullmatch(r"[A-Z0-9.&_-]{1,24}", symbol) for symbol in symbols):
        raise HTTPException(status_code=422, detail="Watchlist symbols must be 1–24 letters, numbers or . & _ - characters.")
    save_watchlist(user, symbols)
    return {"symbols": symbols}


@app.post("/api/v1/portfolio/preview-csv")
async def preview_csv(file: UploadFile = File(...), user: str = Depends(require_user)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a CSV file")
    raw = await file.read(5_000_001)
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds 5 MB")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        aliases = {"symbol": ("symbol", "ticker", "stock"), "quantity": ("quantity", "qty", "shares"), "average_price": ("average price", "avg price", "avg_price", "average_price", "buy price"), "current_price": ("current price", "ltp", "market price", "price"), "sector": ("sector",)}
        mapping = {target: next((col for col in reader.fieldnames if any(alias in col.lower().strip() for alias in names)), None) for target, names in aliases.items()}
        missing = [key for key in ("symbol", "quantity", "average_price", "current_price") if not mapping[key]]
        if missing:
            raise ValueError("Could not identify required columns: " + ", ".join(missing))
        rows = []
        for source in reader:
            try:
                rows.append(Holding(symbol=str(source[mapping["symbol"]]).strip(), quantity=float(str(source[mapping["quantity"]]).replace(",", "")), average_price=float(str(source[mapping["average_price"]]).replace(",", "").replace("₹", "")), current_price=float(str(source[mapping["current_price"]]).replace(",", "").replace("₹", "")), sector=str(source.get(mapping["sector"], "Unclassified") or "Unclassified").strip()))
            except (ValueError, TypeError):
                continue
        if not rows:
            raise ValueError("No valid holding rows found")
        return {"holdings": [h.model_dump() for h in rows], "count": len(rows), "column_mapping": mapping, "requires_user_confirmation": True, "warnings": ["Review all extracted quantities and prices before analysis."]}
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/portfolio/preview-image")
async def preview_image(file: UploadFile = File(...), user: str = Depends(require_user)) -> dict[str, Any]:
    """Extract a reviewable holdings preview from a screenshot using Groq Vision."""
    allowed_types = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, or WebP portfolio screenshot.")
    raw = await file.read(10_000_001)
    if len(raw) > 10_000_000:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB.")
    if not raw:
        raise HTTPException(status_code=422, detail="The selected image is empty.")
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Image import needs GROQ_API_KEY in backend/.env. CSV import works without it.")

    image_url = f"data:{file.content_type};base64,{base64.b64encode(raw).decode('ascii')}"
    prompt = (
        "Extract portfolio holdings from this broker-app screenshot. Return one JSON object with a holdings array. "
        "For every fully visible holding, return symbol, quantity, average_price, current_price, sector, and name. "
        "The screen may lay a holding out across several lines: one line can show Qty and Avg, another the ticker, "
        "and another Invested and LTP. Pair lines only within the same visually separated holding card/row. "
        "Map Qty to quantity, Avg to average_price, and LTP to current_price. Keep ticker spelling exactly, including "
        "dots or hyphens. Use Unclassified for sector when absent and the ticker for name when no company name is "
        "shown. Values must be JSON numbers. Do not use total portfolio values, P&L, daily returns, or percent "
        "changes as prices. Do not infer or calculate missing values. Omit cropped or incomplete holdings and any "
        "row where symbol, quantity, average price, or LTP is not clearly readable. Ignore tabs, totals, and headings."
    )
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                GROQ_API_BASE,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip(),
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]}],
                    "temperature": 0,
                    "max_completion_tokens": 4096,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        extracted = json.loads(content)
        raw_rows = extracted.get("holdings", [])
        if not isinstance(raw_rows, list):
            raise ValueError("Vision response did not contain a holdings list")
        rows = []
        for source in raw_rows:
            if not isinstance(source, dict):
                continue
            try:
                rows.append(Holding(
                    symbol=str(source.get("symbol", "")).strip(),
                    quantity=float(source["quantity"]),
                    average_price=float(source["average_price"]),
                    current_price=float(source["current_price"]),
                    sector=str(source.get("sector") or "Unclassified").strip(),
                    name=str(source.get("name") or source.get("symbol") or "").strip() or None,
                ))
            except (KeyError, TypeError, ValueError):
                continue
        if not rows:
            raise HTTPException(status_code=422, detail="No complete holdings were readable. Use a clear screenshot showing symbol, quantity, average cost, and current price, or import a CSV.")
        return {
            "holdings": [holding.model_dump() for holding in rows],
            "count": len(rows),
            "requires_user_confirmation": True,
            "warnings": ["AI extracted values may be wrong. Verify every row before confirming; the image was processed by Groq Vision."],
        }
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        provider_message = ""
        try:
            provider_error = exc.response.json().get("error", {})
            provider_message = provider_error.get("message", "") if isinstance(provider_error, dict) else str(provider_error)
        except (ValueError, AttributeError):
            pass
        provider_message = re.sub(r"\s+", " ", str(provider_message)).strip()[:240]
        if exc.response.status_code in (401, 403):
            raise HTTPException(status_code=503, detail="Groq Vision could not authorize the request. Check the backend GROQ_API_KEY and model access.") from exc
        if status == 404:
            raise HTTPException(status_code=503, detail=f"Groq Vision model '{os.getenv('GROQ_VISION_MODEL', 'qwen/qwen3.8-27b').strip()}' was not found or is unavailable to this key. Check GROQ_VISION_MODEL in backend/.env.") from exc
        if status == 413:
            raise HTTPException(status_code=413, detail="Groq rejected the image as too large. Use a smaller screenshot.") from exc
        if status == 429:
            raise HTTPException(status_code=429, detail="Groq Vision rate limit or quota reached. Wait or check the Groq account limit.") from exc
        detail = f"Groq Vision rejected the image (HTTP {status})."
        if provider_message:
            detail += f" {provider_message}"
        raise HTTPException(status_code=502, detail=detail) from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Could not extract holdings from this image. Try a clearer screenshot or import a CSV.") from exc


def _is_market_query(question: str) -> bool:
    return bool(re.search(r"\b(market|news|latest|sector outlook)\b|current\s+(market|price|news)|\b(stock|share)\s+price\b|\blive\s+(market|price|news)\b", question, re.I))


def _local_portfolio_answer(question: str, analysis: dict[str, Any]) -> str:
    summary = analysis["summary"]
    holdings = analysis["holdings"]
    winners = sorted(holdings, key=lambda h: h["pnl"], reverse=True)
    sectors = analysis["sector_allocation"]
    if not holdings:
        return "There are no confirmed holdings in this session yet. Import a CSV and confirm the rows before asking portfolio questions."
    if re.search(r"full review|complete review|all available|all aspects", question, re.I):
        top_position = max(holdings, key=lambda h: h["market_value"])
        best = sorted(holdings, key=lambda h: h["pnl"], reverse=True)[:3]
        worst = sorted(holdings, key=lambda h: h["pnl"])[:3]
        sector_text = "; ".join(f"{s['sector']} {s['weight_percent']:.1f}%" for s in sectors) or "Unavailable"
        return (f"PORTFOLIO SNAPSHOT: {summary['holding_count']} holdings; market value {summary['market_value']:,.0f} INR; invested {summary['invested_value']:,.0f} INR; "
                f"unrealized P&L {summary['pnl']:+,.0f} INR ({summary['pnl_percent']:+.2f}%).\n\n"
                f"CONCENTRATION: HHI {summary['hhi']:.3f}; largest position {top_position['symbol']} at {top_position['market_value']/summary['market_value']*100:.1f}% of value.\n\n"
                f"SECTORS: {sector_text}.\n\n"
                f"TOP UNREALIZED CONTRIBUTORS: " + "; ".join(f"{h['symbol']} {h['pnl']:+,.0f} INR ({h['pnl_percent']:+.2f}%)" for h in best) + ".\n\n"
                f"LOWEST UNREALIZED P&L: " + "; ".join(f"{h['symbol']} {h['pnl']:+,.0f} INR ({h['pnl_percent']:+.2f}%)" for h in worst) + ".\n\n"
                "LIMITS: Prices are user supplied and not verified live. There is no dated return history, so daily attribution, volatility, maximum drawdown, Sharpe, beta, correlation, benchmark comparison, taxes and dividends cannot be calculated from this snapshot.")
    if re.search(r"risk|concentrat|diversif|exposure", question, re.I):
        top = winners[0] if winners else None
        top_market = max(holdings, key=lambda h: h["market_value"])
        sector = sectors[0] if sectors else None
        return (f"From the confirmed snapshot: HHI concentration is {summary['hhi']:.3f} (higher values mean more weight in fewer names). "
                f"{top_market['symbol']} is the largest position at {top_market['market_value']/summary['market_value']*100:.1f}% of current value. "
                f"{sector['sector']} is the largest sector at {sector['weight_percent']:.1f}%. "
                "Historical volatility, drawdown, beta and correlation need dated price history and are not inferred from this snapshot.")
    if re.search(r"winner|best|gain|contribut", question, re.I):
        chosen = winners[:3]
        return "Largest unrealized P&L contributors in this snapshot: " + "; ".join(f"{h['symbol']} {h['pnl']:+,.0f} INR ({h['pnl_percent']:+.2f}%)" for h in chosen) + ". These use the imported average cost and price, before fees, taxes and dividends."
    if re.search(r"loser|losing|worst|losses|underperform|\bdown\b", question, re.I):
        chosen = sorted(holdings, key=lambda h: h["pnl"])[:3]
        return "Lowest unrealized P&L positions in this snapshot: " + "; ".join(f"{h['symbol']} {h['pnl']:+,.0f} INR ({h['pnl_percent']:+.2f}%)" for h in chosen) + ". This identifies snapshot performance; it does not explain causation."
    if re.search(r"sector|allocation", question, re.I):
        return "Sector weights by current value: " + "; ".join(f"{x['sector']} {x['weight_percent']:.1f}%" for x in sectors) + ". Sector labels come from your uploaded file or Unclassified defaults."
    if re.search(r"nifty|sensex|benchmark|compare", question, re.I):
        return "A portfolio-versus-index comparison is unavailable because this session has no dated portfolio history or verified benchmark series. I won't infer relative performance from one snapshot."
    if re.search(r"why|today|changed|cause|fell|drop|movement", question, re.I):
        return (f"The snapshot shows {summary['pnl']:+,.0f} INR unrealized P&L overall, but it does not contain verified dated prices or market events. "
                "I can't attribute a daily move or explain its cause without time-stamped portfolio history and sourced market data.")
    return (f"Confirmed portfolio snapshot: market value {summary['market_value']:,.0f} INR; invested value {summary['invested_value']:,.0f} INR; "
            f"unrealized P&L {summary['pnl']:+,.0f} INR ({summary['pnl_percent']:+.2f}%); {summary['holding_count']} holdings. "
            "I can break down sector weights, concentration, largest winners or lowest P&L positions. Prices are user-supplied and not live quotes.")


def _extract_groq_citations(message: dict[str, Any]) -> list[dict[str, str]]:
    """Pull source links out of a Groq compound response.

    Groq exposes sources in two possible places depending on model/version: OpenAI-style
    ``annotations`` (url_citation) on the message, and/or ``search_results`` on each entry of
    ``executed_tools``. We check both defensively and de-duplicate by URL.
    """
    citations: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(url: str | None, title: str | None) -> None:
        if url and url not in seen:
            seen.add(url)
            citations.append({"title": title or "Source", "url": url})

    for annotation in message.get("annotations") or []:
        url_citation = annotation.get("url_citation") or {}
        _add(url_citation.get("url") or annotation.get("url"), url_citation.get("title") or annotation.get("title"))

    for tool in message.get("executed_tools") or []:
        results = tool.get("search_results") or []
        if isinstance(results, dict):
            results = results.get("results", [])
        for result in results or []:
            if isinstance(result, dict):
                _add(result.get("url") or result.get("link"), result.get("title") or result.get("name"))

    return citations


@app.post("/api/v1/ai/answer")
async def answer(payload: AnalystRequest, user: str = Depends(require_user)) -> dict[str, Any]:
    question = payload.question.strip()
    market_query = _is_market_query(question)
    if payload.holdings:
        analysis = analyze(AnalyzeRequest(holdings=payload.holdings), user=user)
    else:
        analysis = {"summary": {"market_value": 0, "invested_value": 0, "pnl": 0, "pnl_percent": 0, "holding_count": 0, "hhi": 0}, "holdings": [], "sector_allocation": []}
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        if market_query:
            return {"answer": "Live market and news search is unavailable because GROQ_API_KEY is not configured. Portfolio questions can still be answered from your confirmed holdings.", "mode": "market_unavailable", "citations": [], "evidence": [], "limitations": ["Current news search needs a Groq API key; check Alpha Vantage separately for quote availability."]}
        return {"answer": _local_portfolio_answer(question, analysis), "mode": "evidence_fallback", "citations": [], "evidence": analysis["summary"], "limitations": ["Rule-based answer; configure GROQ_API_KEY for AI explanations.", "Portfolio prices can be CSV-supplied or updated with an Alpha Vantage quote; check its data date."]}

    # Portfolio-only questions use a fast plain-text model (no web access needed). Market/news
    # questions use a Groq Compound model, which can call Groq's built-in web search tool and
    # returns citations automatically.
    if market_query:
        configured_model = (os.getenv("GROQ_SEARCH_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b").strip()
        fallbacks = _GROQ_SEARCH_FALLBACKS
    else:
        configured_model = (os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile").strip()
        fallbacks = _GROQ_TEXT_FALLBACKS
    models_to_try = [configured_model] + [m for m in fallbacks if m != configured_model]
    if market_query:
        # Current Groq web search is exposed as the browser_search built-in tool
        # for GPT-OSS models. Skip configured models that cannot run that tool.
        models_to_try = [model for model in models_to_try if model in _GROQ_BROWSER_SEARCH_MODELS]

    system_prompt = (
        "You are a careful Indian-market portfolio analyst. Explain, do not instruct trades or guarantee returns. "
        "All calculations in the supplied portfolio context are deterministic. Never invent a holding, price, metric, news item, or source. "
        "For portfolio statements cite the exact supplied evidence and note limitations. For current market/news questions use your web search tool and cite sources. "
        "If data is unavailable say so. Give a direct, plain-English answer and distinguish facts from interpretation."
    )
    context = {"question": question}
    if not market_query:
        context.update({"portfolio_analytics": analysis, "portfolio_data_quality": {"prices": "user supplied, not verified live", "history": "unavailable"}})
    request_body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "temperature": 0.2,
    }

    used_model = models_to_try[0]
    error_detail: str | None = None
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response: httpx.Response | None = None
            for candidate_model in models_to_try:
                body = {**request_body, "model": candidate_model}
                if market_query:
                    body.update({
                        "tools": [{"type": "browser_search"}],
                        "tool_choice": "required",
                        "reasoning_effort": "low",
                        "max_completion_tokens": 4096,
                        "stream": False,
                    })
                response = await client.post(GROQ_API_BASE, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=body)
                used_model = candidate_model
                if market_query and response.status_code == 400:
                    try:
                        msg = response.json().get("error", {}).get("message", "")
                    except (ValueError, AttributeError):
                        msg = ""
                    error_detail = f"Groq browser search rejected model '{candidate_model}': {msg or response.status_code}."
                    continue
                if response.status_code in (404, 400):
                    # Bad/unavailable model id for this key; try the next candidate.
                    try:
                        msg = response.json().get("error", {}).get("message", "")
                    except ValueError:
                        msg = ""
                    if response.status_code == 404 or "model" in msg.lower():
                        error_detail = f"Groq model '{candidate_model}' was rejected: {msg or response.status_code}."
                        continue
                break
            assert response is not None
            if response.status_code >= 400:
                try:
                    error_detail = response.json().get("error", {}).get("message") or error_detail
                except ValueError:
                    error_detail = response.text[:300] or error_detail
            response.raise_for_status()
        data = response.json()
        message = (data.get("choices") or [{}])[0].get("message", {})
        text = (message.get("content") or "").strip()
        citations = _extract_groq_citations(message) if market_query else []
        finish_reason = (data.get("choices") or [{}])[0].get("finish_reason")
        if not text and finish_reason and finish_reason != "stop":
            error_detail = f"Groq stopped early ({finish_reason}) and returned no text; try rephrasing the question."
        if market_query and not text:
            return {"answer": "Groq browser search returned no answer. Check the backend log and Groq account limits, then try again.", "mode": "market_unavailable", "citations": [], "evidence": [], "limitations": [error_detail or "The search response contained no answer."]}
        if market_query and not citations:
            return {"answer": "The search did not return verifiable source links, so no news summary is shown. Try again in a moment.", "mode": "market_unavailable", "citations": [], "evidence": [], "limitations": [error_detail or "Groq browser search returned no source links."]}
        response_mode = "groq_grounded" if market_query and citations else "groq_no_sources" if market_query else "groq_portfolio"
        response_limitations = [] if citations else ["No web citations were returned; verify current-market statements independently."] if market_query else ["Portfolio prices are user-supplied and have not been verified against a market provider."]
        if used_model != configured_model:
            response_limitations.append(f"Configured Groq model '{configured_model}' was unavailable; used '{used_model}' instead. Update GROQ_MODEL/GROQ_SEARCH_MODEL in backend/.env once you confirm the right model id for your key.")
        return {"answer": text or "The model returned no answer. Please try again.", "mode": response_mode, "citations": citations, "evidence": analysis["summary"], "limitations": response_limitations}
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        detail = error_detail or type(exc).__name__
        if market_query:
            return {"answer": "I couldn't retrieve grounded market or news information just now. Please try again later.", "mode": "market_unavailable", "citations": [], "evidence": [], "limitations": [detail]}
        return {"answer": _local_portfolio_answer(question, analysis), "mode": "evidence_fallback", "citations": [], "evidence": analysis["summary"], "limitations": ["Groq was unavailable; this answer uses deterministic portfolio evidence only.", detail]}
