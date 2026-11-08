export interface UnderlyingAsset {
  ins_code: string;
  symbol: string;
  full_name: string;
  latest_date: number | null;
  latest_price: number | null;
  active_options_count: number;
  expired_options_count: number;
  y_val?: string | null;
  cgr_val_cot?: string | null;
}

export interface OptionContract {
  ins_code: string;
  symbol: string;
  full_name: string;
  instrument_type: "call" | "put";
  ua_ins_code: string | null;
  strike_price: number | null;
  end_date: number | null;
  contract_size: number;
  is_expired: boolean;
  y_val?: string | null;
  cgr_val_cot?: string | null;
}

export interface OptionChainRow {
  ua_ins_code: string;
  d_even: number;
  end_date: number;
  dte: number;
  strike_price: number;
  contract_size: number;
  underlying_price: number;
  call_ins_code: string | null;
  call_symbol: string | null;
  call_close: number;
  call_last: number;
  call_volume: number;
  call_trades: number;
  call_bid: number;
  call_ask: number;
  call_moneyness: "ITM" | "ATM" | "OTM" | null;
  put_ins_code: string | null;
  put_symbol: string | null;
  put_close: number;
  put_last: number;
  put_volume: number;
  put_trades: number;
  put_bid: number;
  put_ask: number;
  put_moneyness: "ITM" | "ATM" | "OTM" | null;
}

export interface OptionChainResponse {
  ua_ins_code: string;
  symbol: string;
  full_name: string;
  d_even: number;
  underlying_price: number;
  available_dates: number[];
  count: number;
  chain: OptionChainRow[];
}

export interface MatchedTick {
  ins_code: string;
  symbol: string;
  ua_ins_code: string | null;
  d_even: number;
  h_even: number;
  n_tran: number;
  ts_tehran: string;
  ts_utc: string;
  ts_epoch: number;
  price: number;
  volume: number;
  underlying_price: number | null;
  underlying_ts_utc: string | null;
  underlying_ts_epoch: number | null;
  underlying_n_tran: number | null;
  moneyness_status: "ITM" | "ATM" | "OTM" | null;
}

export interface OhlcvCandle {
  ins_code: string;
  timeframe: "1m" | "5m" | "15m" | "1h" | "1d";
  d_even: number;
  bucket_epoch: number;
  bucket_ts_tehran: string;
  bucket_ts_utc: string;
  open: number;
  high: number;
  low: number;
  close: number;
  last_price: number;
  close_ffill: number;
  volume: number;
  value: number;
  trade_count: number;
  is_sparse: number;
}

export interface QualityReconciliationRow {
  ins_code: string;
  symbol: string;
  instrument_type: string;
  d_even: number;
  daily_trade_count: number;
  tick_valid_count: number;
  tick_canceled_count: number;
  daily_volume: number;
  tick_valid_volume: number;
  volume_diff: number;
  trade_count_diff: number;
  status: "MATCH" | "MISMATCH" | "MISSING_TICKS";
}

export interface QualityReport {
  total_traded_days: number;
  matched_days: number;
  mismatched_days: number;
  missing_days: number;
  match_rate_pct: number;
  meets_98_pct_target: boolean;
  canceled_trades_count: number;
  rows: QualityReconciliationRow[];
}
