import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = url && key ? createClient(url, key) : null

export async function fetchTrades({ from = 0, to = 999 } = {}) {
  if (!supabase) throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY.')
  const { data, error } = await supabase
    .from('trades')
    .select('id,stock_entry,option_entry,stock_exit,option_exit,created_at,ticker_symbol,option_type,exit_timer_started_at,option_entry_typed_at,option_exit_typed_at,length_of_trade_seconds,premarket_high,premarket_low,regular_session_open,previous_day_open,previous_day_high,previous_day_low')
    .order('created_at', { ascending: false })
    .range(from, to)
  if (error) throw error
  return data ?? []
}
