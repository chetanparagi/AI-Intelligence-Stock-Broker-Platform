"""Single-user SQLite storage for the local demonstration app."""
from __future__ import annotations
import json
import os
import sqlite3
import time
from pathlib import Path

def _path() -> str:
    url=os.getenv("DATABASE_URL", "sqlite:///./zerodha-demo.db")
    return url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else url

def _db():
    db=sqlite3.connect(_path(), timeout=10)
    db.row_factory=sqlite3.Row
    return db

def _init() -> None:
    Path(_path()).parent.mkdir(parents=True, exist_ok=True)
    with _db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS portfolio_holdings (demo_user TEXT PRIMARY KEY, holdings_json TEXT NOT NULL, updated_at REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS watchlists (demo_user TEXT PRIMARY KEY, symbols_json TEXT NOT NULL, updated_at REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS market_quote_cache (symbol TEXT PRIMARY KEY, payload_json TEXT NOT NULL, retrieved_at REAL NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS alpha_vantage_usage (usage_day TEXT PRIMARY KEY, request_count INTEGER NOT NULL, last_request_at REAL NOT NULL)")

_init()

def load_portfolio(_user: str) -> list[dict]:
    with _db() as db:
        row=db.execute("SELECT holdings_json FROM portfolio_holdings WHERE demo_user = 'local' ").fetchone()
    return json.loads(row["holdings_json"]) if row else []

def save_portfolio(_user: str, holdings: list[dict]) -> None:
    with _db() as db:
        db.execute("INSERT INTO portfolio_holdings(demo_user,holdings_json,updated_at) VALUES('local',?,?) ON CONFLICT(demo_user) DO UPDATE SET holdings_json=excluded.holdings_json,updated_at=excluded.updated_at", (json.dumps(holdings,separators=(",",":")),time.time()))

def load_watchlist(_user: str) -> list[str]:
    with _db() as db:
        row=db.execute("SELECT symbols_json FROM watchlists WHERE demo_user = 'local'").fetchone()
    return json.loads(row["symbols_json"]) if row else []

def save_watchlist(_user: str, symbols: list[str]) -> None:
    with _db() as db:
        db.execute("INSERT INTO watchlists(demo_user,symbols_json,updated_at) VALUES('local',?,?) ON CONFLICT(demo_user) DO UPDATE SET symbols_json=excluded.symbols_json,updated_at=excluded.updated_at", (json.dumps(symbols,separators=(",",":")),time.time()))

def require_user() -> str:
    return "local-demo-user"


def load_quote(symbol: str, max_age: int) -> dict | None:
    with _db() as db:
        row=db.execute("SELECT payload_json,retrieved_at FROM market_quote_cache WHERE symbol=?",(symbol,)).fetchone()
    if not row or time.time()-row["retrieved_at"]>max_age: return None
    quote=json.loads(row["payload_json"]); quote["retrieved_at"]=row["retrieved_at"]; quote["cached"]=True
    return quote

def save_quote(symbol: str, quote: dict) -> None:
    with _db() as db:
        db.execute("INSERT INTO market_quote_cache(symbol,payload_json,retrieved_at) VALUES(?,?,?) ON CONFLICT(symbol) DO UPDATE SET payload_json=excluded.payload_json,retrieved_at=excluded.retrieved_at",(symbol,json.dumps(quote,separators=(",",":")),time.time()))

def alpha_usage(day: str) -> tuple[int,float]:
    with _db() as db:
        row=db.execute("SELECT request_count,last_request_at FROM alpha_vantage_usage WHERE usage_day=?",(day,)).fetchone()
    return (row["request_count"],row["last_request_at"]) if row else (0,0.0)

def record_alpha_request(day: str, now: float) -> None:
    with _db() as db:
        db.execute("INSERT INTO alpha_vantage_usage(usage_day,request_count,last_request_at) VALUES(?,1,?) ON CONFLICT(usage_day) DO UPDATE SET request_count=alpha_vantage_usage.request_count+1,last_request_at=excluded.last_request_at",(day,now))
