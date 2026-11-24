import { useMemo, useState } from 'react'
import TradeTable from './TradeTable'

export default function HistoryPage({ trades }) {
  const [q, setQ] = useState('')
  const [type, setType] = useState('all')
  const [result, setResult] = useState('all')
  const [sort, setSort] = useState('date')
  const filtered = useMemo(() => {
    const matching = trades.filter((trade) => {
      const tickerMatch = !q || (trade.ticker_symbol || '').toLowerCase().includes(q.toLowerCase())
      const typeMatch = type === 'all' || (trade.option_type || '').toLowerCase() === type
      const resultMatch = result === 'all' || (result === 'win' ? trade.pnl > 0 : trade.pnl < 0)
      return tickerMatch && typeMatch && resultMatch
    })
    return matching.sort((a, b) => sort === 'pnl'
      ? b.pnl - a.pnl
      : sort === 'duration'
        ? b.duration - a.duration
        : new Date(b.created_at) - new Date(a.created_at))
  }, [trades, q, type, result, sort])

  return <section className="page"><div className="page-heading"><div><span className="eyebrow">EXECUTION LOG</span><h1>Trade history</h1></div><p>{filtered.length} of {trades.length} recorded trades</p></div><div className="filters"><input aria-label="Search ticker" placeholder="Search ticker…" value={q} onChange={e => setQ(e.target.value)} /><select value={type} onChange={e => setType(e.target.value)}><option value="all">All types</option><option value="call">Calls</option><option value="put">Puts</option></select><select value={result} onChange={e => setResult(e.target.value)}><option value="all">All results</option><option value="win">Winners</option><option value="loss">Losers</option></select><select value={sort} onChange={e => setSort(e.target.value)}><option value="date">Newest</option><option value="pnl">P&amp;L</option><option value="duration">Duration</option></select></div><TradeTable trades={filtered} /></section>
}
