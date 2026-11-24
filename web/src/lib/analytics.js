export const n = (value) => Number.isFinite(Number(value)) ? Number(value) : null

export function enrichTrade(row) {
  const entry = n(row.option_entry)
  const exit = n(row.option_exit)
  const pnl = entry !== null && exit !== null ? (exit - entry) * 100 : null
  const returnPct = entry ? ((exit - entry) / entry) * 100 : null
  const start = row.option_entry_typed_at || row.created_at
  const end = row.option_exit_typed_at || row.exit_timer_started_at
  const duration = n(row.length_of_trade_seconds) ?? (start && end ? (new Date(end) - new Date(start)) / 1000 : null)
  return { ...row, pnl, returnPct, duration }
}

export function summarize(input) {
  const trades = input.map(enrichTrade).filter((trade) => trade.pnl !== null)
  const wins = trades.filter((t) => t.pnl > 0)
  const losses = trades.filter((t) => t.pnl < 0)
  const grossWins = wins.reduce((sum, t) => sum + t.pnl, 0)
  const grossLosses = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0))
  const chronological = [...trades].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  let equity = 0; let peak = 0; let maxDrawdown = 0
  const curve = chronological.map((t) => { equity += t.pnl; peak = Math.max(peak, equity); maxDrawdown = Math.max(maxDrawdown, peak - equity); return { ...t, equity } })
  return { trades, wins, losses, grossWins, grossLosses, curve, maxDrawdown,
    totalPnl: trades.reduce((sum, t) => sum + t.pnl, 0),
    winRate: trades.length ? wins.length / trades.length * 100 : 0,
    profitFactor: grossLosses ? grossWins / grossLosses : (grossWins ? Infinity : 0),
    avgWin: wins.length ? grossWins / wins.length : 0,
    avgLoss: losses.length ? losses.reduce((s, t) => s + t.pnl, 0) / losses.length : 0,
    expectancy: trades.length ? trades.reduce((s, t) => s + t.pnl, 0) / trades.length : 0,
  }
}

export function groupPnl(trades, keyFn) {
  const groups = new Map()
  trades.forEach((t) => { const key = keyFn(t); if (key) groups.set(key, (groups.get(key) || 0) + t.pnl) })
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
}

export function dailyPnl(trades) { return groupPnl(trades, (t) => new Date(t.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' })) }
export const money = (v) => `${v < 0 ? '-' : ''}$${Math.abs(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
export const pct = (v) => `${(v || 0).toFixed(1)}%`
export const duration = (seconds) => { if (seconds == null) return '—'; const m = Math.floor(seconds / 60); return `${m}m ${Math.round(seconds % 60)}s` }
