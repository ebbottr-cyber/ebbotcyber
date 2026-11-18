import apiClient from './index';
import { toCamelCase } from './utils';

export type MemeCoinStrategyId = 'new_launch' | 'momentum' | 'robinhood_chain';
export type SolanaMemeCoinStrategyId = Exclude<MemeCoinStrategyId, 'robinhood_chain'>;

export type MemeCoinStrategy = {
  id: MemeCoinStrategyId;
  name: string;
  market: 'solana' | 'robinhood_chain';
  dataSources: string[];
  status: 'not_connected';
  engineConnected: boolean;
  paperTradingEnabled: boolean;
  liveTradingEnabled: boolean;
  riskChecks: string[];
  agentModules?: Array<{ id: string; name: string; status: 'not_connected' }>;
  metrics: {
    trades: number | null;
    netPnlUsd: number | null;
    winRatePct: number | null;
  };
};

export type MemeCoinOverview = {
  market: 'multi_chain';
  mode: 'paper_planned';
  liveTradingEnabled: boolean;
  sharedRiskEngineConnected: boolean;
  lastMarketEventAt: string | null;
  strategies: MemeCoinStrategy[];
};

export type RobinhoodRpcStatus = {
  network: 'testnet' | 'mainnet' | 'unknown';
  chainIdExpected: number | null;
  chainIdSeen: number | null;
  blockNumber: number | null;
  status: 'disabled' | 'ok' | 'unavailable' | 'mismatch';
  checkedAt: string | null;
  error: string | null;
  tradingEnabled: false;
};

export type MemeCoinCandidate = {
  strategy: SolanaMemeCoinStrategyId;
  symbol: string;
  tokenAddress: string;
  poolAddress: string;
  liquidityUsd: number;
  volume5mUsd: number;
  change5mPct: number;
  ageMinutes: number;
  buys5m: number;
  sells5m: number;
  researchScore: number;
  riskStatus: 'unverified';
  tradable: false;
  source: 'geckoterminal';
};

export type MemeCoinDiscoveryResponse = {
  strategy: SolanaMemeCoinStrategyId;
  status: 'disabled' | 'ok' | 'unavailable';
  source: 'geckoterminal';
  observedAt: string | null;
  candidates: MemeCoinCandidate[];
  error: string | null;
};

export type SolanaMintReview = {
  mint: string;
  network: 'solana-mainnet';
  status: 'disabled' | 'screened' | 'unavailable' | 'unsupported';
  verdict: 'blocked' | 'review_only' | 'unknown';
  slot: number | null;
  checkedAt: string | null;
  tokenProgram: string | null;
  mintAuthorityRevoked: boolean | null;
  freezeAuthorityRevoked: boolean | null;
  decimals: number | null;
  supplyBaseUnits: string | null;
  blockingReasons: string[];
  remainingUnverified: string[];
  fullSafetyVerified: false;
  tradable: false;
};

export type SolanaImpactEstimate = {
  model: 'hypothetical_cpmm_50_50';
  liquidityUsd: number;
  orderUsd: number;
  feeBps: number;
  adverseSlippageBps: number;
  modeledFeeUsd: number;
  modeledOutputValueUsd: number;
  modeledMinOutputValueUsd: number;
  modeledPriceImpactPct: number;
  modeledTotalCostPct: number;
  orderVsLiquidityPct: number;
  flags: string[];
  paperReviewStatus: 'blocked' | 'research_only';
  realQuoteAvailable: false;
  tradable: false;
};

export type SolanaConcentrationReview = {
  mint: string;
  network: 'solana-mainnet';
  status: 'disabled' | 'screened' | 'unavailable';
  verdict: 'unknown' | 'review_only' | 'concentration_signal';
  checkedAt: string | null;
  supplySlot: number | null;
  accountsSlot: number | null;
  supplyBaseUnits: string | null;
  observedAccounts: number;
  topAccountPct: number | null;
  topTenAccountsPct: number | null;
  observedTopTwentyPct: number | null;
  warningFlags: string[];
  interpretation: 'token_accounts_not_wallets';
  ownerIdentityVerified: false;
  poolVaultsClassified: false;
  fullSafetyVerified: false;
  tradable: false;
};

export type SolanaPoolReview = {
  mint: string;
  pool: string;
  network: 'solana';
  status: 'disabled' | 'screened' | 'unavailable';
  verdict: 'unknown' | 'blocked' | 'review_only';
  checkedAt: string | null;
  geckoterminalUsd: number | null;
  dexscreenerUsd: number | null;
  differencePct: number | null;
  dexId: string | null;
  onchainAccountFound: boolean | null;
  onchainOwnerProgram: string | null;
  onchainSlot: number | null;
  flags: string[];
  onchainReservesVerified: false;
  liquidityLockVerified: false;
  lpOwnerVerified: false;
  poolAuthenticityVerified: false;
  sellabilityVerified: false;
  tradable: false;
};

export type SolanaOwnerGroupReview = {
  mint: string;
  network: 'solana-mainnet';
  status: 'disabled' | 'screened' | 'unavailable';
  verdict: 'unknown' | 'review_only' | 'concentration_signal';
  checkedAt: string | null;
  observedTopTokenAccounts: number;
  observedOwnerGroups: number;
  largestObservedOwnerSharePct: number | null;
  ownerGroups: Array<{
    ownerAddress: string;
    sampledTokenAccounts: number;
    shareOfTotalSupplyPct: number;
  }>;
  flags: string[];
  interpretation: 'observed_token_account_owner_not_beneficial_owner';
  vaultClassificationVerified: false;
  beneficialOwnershipVerified: false;
  fullSafetyVerified: false;
  tradable: false;
};

export type SolanaOrcaVaultReview = {
  mint: string;
  pool: string;
  network: 'solana-mainnet';
  protocol: 'orca_whirlpool';
  status: 'disabled' | 'unsupported' | 'unavailable' | 'screened';
  verdict: 'unknown' | 'blocked' | 'review_only';
  checkedAt: string | null;
  poolSlot: number | null;
  vaultSlot: number | null;
  poolProgram: string | null;
  mintA: string | null;
  mintB: string | null;
  vaultA: string | null;
  vaultB: string | null;
  vaultARawAmount: string | null;
  vaultBRawAmount: string | null;
  vaultADecimals: number | null;
  vaultBDecimals: number | null;
  clmmLiquidityRaw: string | null;
  vaultAuthorityMatchesPool: boolean;
  warnings: string[];
  vaultReservesObserved: boolean;
  activeSwapDepthVerified: false;
  liquidityLockVerified: false;
  lpWithdrawalAuthorityVerified: false;
  sellabilityVerified: false;
  tradable: false;
};

export type MemeCoinPaperReplayStatus = {
  status: 'offline_replay_available';
  dataSource: 'operator_supplied_offline_fixture';
  liveQuotesConnected: false;
  paperAutomated: false;
  liveTradingEnabled: false;
  strategyLedgers: Array<{
    strategy: SolanaMemeCoinStrategyId;
    state: 'not_running';
    realizedPnlUsd: null;
  }>;
};

export const memeCoinApi = {
  async getPaperReplayStatus(): Promise<MemeCoinPaperReplayStatus> {
    const { data } = await apiClient.get('/api/v1/meme-coins/paper/status');
    return toCamelCase<MemeCoinPaperReplayStatus>(data);
  },
  async reviewSolanaOrcaVaults(mint: string, pool: string): Promise<SolanaOrcaVaultReview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/orca-vaults', {
      params: { mint, pool },
    });
    return toCamelCase<SolanaOrcaVaultReview>(data);
  },
  async reviewSolanaPool(mint: string, pool: string): Promise<SolanaPoolReview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/pool-review', { params: { mint, pool } });
    return toCamelCase<SolanaPoolReview>(data);
  },
  async reviewSolanaOwnerGroups(mint: string): Promise<SolanaOwnerGroupReview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/owner-groups', { params: { mint } });
    return toCamelCase<SolanaOwnerGroupReview>(data);
  },
  async reviewSolanaConcentration(mint: string): Promise<SolanaConcentrationReview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/concentration', { params: { mint } });
    return toCamelCase<SolanaConcentrationReview>(data);
  },
  async reviewSolanaMint(mint: string): Promise<SolanaMintReview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/mint-review', { params: { mint } });
    return toCamelCase<SolanaMintReview>(data);
  },
  async estimateSolanaImpact(liquidityUsd: number, orderUsd: number): Promise<SolanaImpactEstimate> {
    const { data } = await apiClient.get('/api/v1/meme-coins/solana/impact', {
      params: { liquidity_usd: liquidityUsd, order_usd: orderUsd, fee_bps: 30, adverse_slippage_bps: 100 },
    });
    return toCamelCase<SolanaImpactEstimate>(data);
  },
  async getRobinhoodStatus(): Promise<RobinhoodRpcStatus> {
    const { data } = await apiClient.get('/api/v1/meme-coins/robinhood/status');
    return toCamelCase<RobinhoodRpcStatus>(data);
  },
  async scanCandidates(strategy: SolanaMemeCoinStrategyId): Promise<MemeCoinDiscoveryResponse> {
    const { data } = await apiClient.get('/api/v1/meme-coins/candidates', { params: { strategy } });
    return toCamelCase<MemeCoinDiscoveryResponse>(data);
  },
  async getOverview(): Promise<MemeCoinOverview> {
    const { data } = await apiClient.get('/api/v1/meme-coins/overview');
    return toCamelCase<MemeCoinOverview>(data);
  },
};
