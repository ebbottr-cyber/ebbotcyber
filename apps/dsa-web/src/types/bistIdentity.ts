export type BistIdentityCounts = {
  kap_candidate_count: number;
  exchange_reference_count: number;
  exchange_active_count: number;
  exchange_halted_or_delisted_count: number;
  matched_kap_exchange_count: number;
  matched_active_kap_exchange_count: number;
  kap_not_in_exchange_count: number;
  exchange_not_in_kap_count: number;
  active_without_declared_provider_mapping_count: number;
  active_with_ohlcv_in_supplied_file_count: number | null;
  active_without_ohlcv_in_supplied_file_count: number | null;
  stale_kap_reference_rows: number;
  stale_exchange_reference_rows: number;
  stale_provider_mapping_rows: number;
};

export type BistIdentitySummary = {
  status: 'unavailable' | 'unverified' | 'stale';
  reason: string;
  as_of_utc_date: string | null;
  counts: BistIdentityCounts | null;
  prices_file_supplied: boolean;
  provider_mapping_file_supplied: boolean;
  source_kind: 'operator_local_bist_identity_report';
  independent_listing_verified: false;
  licensed_prices_verified: false;
  paper_trading_enabled: false;
  live_trading_enabled: false;
};
