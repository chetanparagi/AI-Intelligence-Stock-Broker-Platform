export type Holding = { symbol: string; name: string; sector: string; qty: number; avg: number; ltp: number; day: number };

export const inr = (n: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number.isFinite(n) ? n : 0);

export const getHoldingStats = (holdings: Holding[]) => {
  const rows = holdings.map(h => ({ ...h, invested: h.qty * h.avg, value: h.qty * h.ltp, pnl: h.qty * (h.ltp - h.avg), pnlPct: h.avg ? (h.ltp / h.avg - 1) * 100 : 0 }));
  const invested = rows.reduce((s, h) => s + h.invested, 0);
  const value = rows.reduce((s, h) => s + h.value, 0);
  const pnl = value - invested;
  const sectors = Object.entries(rows.reduce((map, h) => { map[h.sector] = (map[h.sector] || 0) + h.value; return map; }, {} as Record<string, number>)).map(([sector, amount]) => ({ sector, amount, weight: value ? amount / value : 0 })).sort((a, b) => b.amount - a.amount);
  const sorted = [...rows].sort((a, b) => b.pnl - a.pnl);
  const weights = rows.map(h => value ? h.value / value : 0);
  return { rows, invested, value, pnl, pnlPct: invested ? pnl / invested * 100 : 0, sectors, sorted, hhi: weights.reduce((s, w) => s + w * w, 0), topHoldingWeight: Math.max(0, ...weights) };
};
