export type EquityMarketCoverage = {
  candidate_instruments: number;
  stocks: number;
  etfs: number;
  with_any_ohlcv: number;
  with_min_bars: number;
  with_recent_bar: number;
  undated_inventory_count: number;
  missing_ohlcv_count: number;
  insufficient_history_count: number;
  stale_ohlcv_count: number;
};

export type EquityCoverageReport = {
  status: 'unavailable' | 'unverified' | 'stale';
  reason: string;
  as_of_utc_date: string | null;
  markets: Partial<Record<'tr' | 'us' | 'de' | 'hk', EquityMarketCoverage>>;
  total_candidate_instruments: number | null;
  source_kind: 'operator_local_report';
  listing_completeness_verified: false;
  licensed_ohlcv_verified: false;
  paper_trading_enabled: false;
  live_trading_enabled: false;
};
