'use client';

import { FormEvent, useState } from 'react';
import { Activity, ArrowDownRight, ArrowUpRight, BarChart3, RefreshCw, Search } from 'lucide-react';
import { Holding, inr } from '../lib/types';
import { readApiJson } from '../lib/api';

const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
const suggestions = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'ITC'];
type Quote = {
  symbol: string;
  last_price: number;
  previous_close: number;
  change_percent: number;
  volume?: number;
  high?: number;
  low?: number;
  timestamp?: string;
  cached?: boolean;
};

export default function MarketCenter({ holdings, onQuote }: {
  holdings: Holding[];
  onQuote: (symbol: string, quote: Quote) => void;
}) {
  const [symbol, setSymbol] = useState('');
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [selected, setSelected] = useState<Quote | null>(null);
  const [updated, setUpdated] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState('');

  async function fetchQuote(value: string) {
    const normalized = value.trim().toUpperCase().replace(/^NSE:/, '');
    if (!/^[A-Z0-9][A-Z0-9._-]{0,31}$/.test(normalized)) {
      setMessage('Enter a ticker such as INFY or a provider symbol such as IBM.US.');
      return;
    }
    if (loading) return;
    setLoading(normalized);
    setMessage('');
    try {
      const response = await fetch(`${API}/api/v1/market/quotes?symbol=${encodeURIComponent(normalized)}`);
      const data = await readApiJson<{ quote: Quote; detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || 'The quote could not be loaded.');
      const quote: Quote = data.quote;
      setQuotes(current => ({ ...current, [normalized]: quote }));
      setSelected(quote);
      setUpdated(new Date().toLocaleTimeString());
      setSymbol(normalized);
      onQuote(normalized, quote);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'The quote could not be loaded.');
    } finally {
      setLoading('');
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void fetchQuote(symbol);
  }

  return <div className="feature-page">
    <div className="feature-intro">
      <span className="feature-icon"><BarChart3 size={18}/></span>
      <div><h2>Stock quote lookup</h2><p>Look up the latest available quote for a stock and review its source date.</p></div>
      <span className="offline-label">ON-DEMAND QUOTES</span>
    </div>

    <section className="feature-card market-lookup">
      <div><h3>Find a stock quote</h3><p>Enter a ticker to request its latest available market quote.</p></div>
      <form className="market-search" onSubmit={submit}>
        <Search size={17}/>
        <input value={symbol} onChange={event => setSymbol(event.target.value)} placeholder="Try INFY, RELIANCE or TCS" aria-label="Stock ticker" maxLength={32}/>
        <button className="confirm-button" disabled={!!loading}><RefreshCw size={14}/>{loading ? 'Loading…' : 'Get latest quote'}</button>
      </form>
      <div className="market-suggestions"><span>Popular Indian stocks</span>{suggestions.map(item => <button key={item} disabled={!!loading} onClick={() => void fetchQuote(item)}>{item}</button>)}</div>
      {message && <p className="watch-note" role="alert">{message}</p>}
    </section>

    {selected ? <section className="feature-card market-quote-card" aria-live="polite">
      <div className="section-heading"><div><span className="eyebrow"><Activity size={12}/> LATEST AVAILABLE QUOTE</span><h3>{selected.symbol}</h3><p>Provider date: {selected.timestamp || 'Not supplied'}</p></div><span className="offline-label">{selected.cached ? 'CACHED' : 'ALPHA VANTAGE'}</span></div>
      <div className="market-price"><strong>{inr(selected.last_price)}</strong><span className={selected.change_percent >= 0 ? 'positive' : 'negative'}>{selected.change_percent >= 0 ? <ArrowUpRight size={16}/> : <ArrowDownRight size={16}/>} {selected.change_percent >= 0 ? '+' : ''}{selected.change_percent.toFixed(2)}%</span></div>
      <div className="market-quote-details"><div><span>Previous close</span><strong>{selected.previous_close ? inr(selected.previous_close) : '—'}</strong></div><div><span>Day high</span><strong>{selected.high ? inr(selected.high) : '—'}</strong></div><div><span>Day low</span><strong>{selected.low ? inr(selected.low) : '—'}</strong></div><div><span>Volume</span><strong>{selected.volume?.toLocaleString('en-IN') ?? '—'}</strong></div></div>
      <p className="data-note">Fetched at {updated}. Alpha Vantage global quotes for Indian stocks are generally end-of-day; this page is not a real-time or tick-by-tick feed. Check the provider date before relying on a quote.</p>
    </section> : <section className="feature-card market-empty"><span className="feature-icon"><BarChart3 size={18}/></span><div><h3>Your quote will appear here</h3><p>Choose a popular stock or search for a ticker. Quotes are requested only when you ask, to respect provider rate limits.</p></div></section>}

    {holdings.length > 0 && <section className="feature-card market-holdings">
      <div className="section-heading"><div><h3>Your portfolio symbols</h3><p>Get a provider quote for an individual holding.</p></div></div>
      <div className="responsive-table"><table><thead><tr><th>SYMBOL</th><th>LAST QUOTE</th><th>CHANGE</th><th>QUOTE DATE</th><th/></tr></thead><tbody>{holdings.map(holding => {
        const quote = quotes[holding.symbol];
        return <tr key={holding.symbol}><td><strong>{holding.symbol}</strong><small>{holding.name}</small></td><td>{quote ? inr(quote.last_price) : 'Not requested'}</td><td className={quote ? quote.change_percent >= 0 ? 'positive' : 'negative' : ''}>{quote ? `${quote.change_percent >= 0 ? '+' : ''}${quote.change_percent.toFixed(2)}%` : '—'}</td><td>{quote?.timestamp || '—'}</td><td><button className="quiet-button" disabled={!!loading} onClick={() => void fetchQuote(holding.symbol)}><RefreshCw size={13}/>{loading === holding.symbol ? 'Loading…' : 'Get quote'}</button></td></tr>;
      })}</tbody></table></div>
    </section>}

    <p className="data-note wide-note">Quotes are supplied by Alpha Vantage. New provider requests may be throttled or unavailable for some symbols; cached quotes remain visible when available. This demo does not stream prices or place trades.</p>
  </div>;
}
