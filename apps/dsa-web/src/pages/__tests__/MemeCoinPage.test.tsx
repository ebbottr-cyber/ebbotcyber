import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import MemeCoinPage from '../MemeCoinPage';

const { getOverview, scanCandidates, getRobinhoodStatus, reviewSolanaMint, estimateSolanaImpact, reviewSolanaConcentration, reviewSolanaPool, reviewSolanaOwnerGroups, reviewSolanaOrcaVaults, getPaperReplayStatus, getSolanaQuotePreview, getPaperRiskReadiness, getPaperMtmReadiness, getSolanaMarkCrosscheck } = vi.hoisted(() => ({
  getOverview: vi.fn(), scanCandidates: vi.fn(), getRobinhoodStatus: vi.fn(),
  reviewSolanaMint: vi.fn(), estimateSolanaImpact: vi.fn(), reviewSolanaConcentration: vi.fn(),
  reviewSolanaPool: vi.fn(), reviewSolanaOwnerGroups: vi.fn(), reviewSolanaOrcaVaults: vi.fn(),
  getPaperReplayStatus: vi.fn(), getSolanaQuotePreview: vi.fn(), getPaperRiskReadiness: vi.fn(), getPaperMtmReadiness: vi.fn(), getSolanaMarkCrosscheck: vi.fn(),
}));

vi.mock('../../api/memeCoin', () => ({
  memeCoinApi: { getOverview, scanCandidates, getRobinhoodStatus, reviewSolanaMint, estimateSolanaImpact, reviewSolanaConcentration, reviewSolanaPool, reviewSolanaOwnerGroups, reviewSolanaOrcaVaults, getPaperReplayStatus, getSolanaQuotePreview, getPaperRiskReadiness, getPaperMtmReadiness, getSolanaMarkCrosscheck },
}));

const overview = {
  market: 'multi_chain',
  mode: 'paper_planned',
  liveTradingEnabled: false,
  sharedRiskEngineConnected: false,
  lastMarketEventAt: null,
  strategies: [
    {
      id: 'new_launch',
      name: 'New Launch',
      market: 'solana',
      dataSources: ['Pump.fun'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['token_authorities'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
    {
      id: 'momentum',
      name: 'Momentum',
      market: 'solana',
      dataSources: ['GMGN'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['volume_quality'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
    {
      id: 'robinhood_chain',
      name: 'Robinhood Chain Agent Research',
      market: 'robinhood_chain',
      dataSources: ['Robinhood Chain RPC (optional health check)', 'OpenCatz AI integration (planned)'],
      status: 'not_connected',
      engineConnected: false,
      paperTradingEnabled: false,
      liveTradingEnabled: false,
      riskChecks: ['evm_contract_permissions'],
      metrics: { trades: null, netPnlUsd: null, winRatePct: null },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.localStorage.setItem('dsa.uiLanguage', 'tr');
  getOverview.mockResolvedValue(overview);
  getSolanaMarkCrosscheck.mockResolvedValue({
    strategy: 'new_launch',
    mint: '11111111111111111111111111111111',
    pool: 'So11111111111111111111111111111111111111112',
    network: 'solana-mainnet', status: 'disabled', verdict: 'unknown',
    sampleSellRaw: '1000000', tokenDecimals: null, mintSlot: null,
    jupiterPriceUsd: null, dexscreenerPriceUsd: null,
    dexLiquidityUsd: null, priceDivergencePct: null, sampleQuotedUsd: null,
    jupiterCapturedAtMs: null, dexRetrievedAtMs: null, checkedAt: null,
    quoteCaptureId: null, dexId: null, warningFlags: [],
    sourceIndependenceVerified: false,
    dexMarketObservationTimestampVerified: false,
    tokenSafetyVerified: false, sellFillVerified: false,
    markToMarketExecutionVerified: false, automatedPaperMarksEnabled: false,
    liveTradingEnabled: false, tradable: false,
  });
  getPaperMtmReadiness.mockResolvedValue({
    status: 'offline_mtm_recovery_available',
    markSource: 'unverified_offline_assumptions',
    databaseOnline: false,
    paperSchedulerRunning: false,
    liveTradingEnabled: false,
    strategies: [
      { strategy: 'new_launch', status: 'not_running' },
      { strategy: 'momentum', status: 'not_running' },
    ],
  });
  getPaperRiskReadiness.mockResolvedValue({
    status: 'offline_safeguards_available',
    archiveMode: 'manual_local_sqlite_only',
    journalOnline: false,
    paperEngineRunning: false,
    liveTradingEnabled: false,
    riskFactsVerifiedFromMarket: false,
    strategyLedgers: [
      { strategy: 'new_launch', mode: 'offline_only', liveOrdersEnabled: false },
      { strategy: 'momentum', mode: 'offline_only', liveOrdersEnabled: false },
    ],
  });
  getSolanaQuotePreview.mockResolvedValue({
    strategy: 'new_launch', mint: '11111111111111111111111111111111',
    side: 'buy', source: 'jupiter_swap_v2_order_quote_only',
    inputMint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    outputMint: '11111111111111111111111111111111',
    amountInRaw: '25000000', status: 'disabled', quote: null,
    error: null, liveQuotePreview: false, walletConnected: false,
    transactionRequested: false, transactionSubmitted: false, tradable: false,
  });
  getPaperReplayStatus.mockResolvedValue({
    status: 'offline_replay_available',
    dataSource: 'operator_supplied_offline_fixture',
    liveQuotesConnected: false,
    paperAutomated: false,
    liveTradingEnabled: false,
    strategyLedgers: [
      { strategy: 'new_launch', state: 'not_running', realizedPnlUsd: null },
      { strategy: 'momentum', state: 'not_running', realizedPnlUsd: null },
    ],
  });
  scanCandidates.mockResolvedValue({strategy: 'new_launch', status: 'disabled', source: 'geckoterminal', observedAt: null, candidates: [], error: null});
  getRobinhoodStatus.mockResolvedValue({network:'testnet',chainIdExpected:46630,chainIdSeen:null,blockNumber:null,status:'disabled',checkedAt:null,error:null,tradingEnabled:false});
  reviewSolanaMint.mockResolvedValue({
    mint: 'So11111111111111111111111111111111111111112',
    network: 'solana-mainnet', status: 'disabled', verdict: 'unknown',
    slot: null, checkedAt: null, tokenProgram: null, mintAuthorityRevoked: null,
    freezeAuthorityRevoked: null, decimals: null, supplyBaseUnits: null,
    blockingReasons: [], remainingUnverified: ['sellability'],
    fullSafetyVerified: false, tradable: false,
  });
  reviewSolanaConcentration.mockResolvedValue({
    mint: 'So11111111111111111111111111111111111111112',
    network: 'solana-mainnet', status: 'disabled', verdict: 'unknown',
    checkedAt: null, supplySlot: null, accountsSlot: null,
    supplyBaseUnits: null, observedAccounts: 0,
    topAccountPct: null, topTenAccountsPct: null, observedTopTwentyPct: null,
    warningFlags: [], interpretation: 'token_accounts_not_wallets',
    ownerIdentityVerified: false, poolVaultsClassified: false,
    fullSafetyVerified: false, tradable: false,
  });
  reviewSolanaPool.mockResolvedValue({
    mint: 'So11111111111111111111111111111111111111112',
    pool: '11111111111111111111111111111111',
    network: 'solana', status: 'disabled', verdict: 'unknown',
    checkedAt: null, geckoterminalUsd: null, dexscreenerUsd: null,
    differencePct: null, dexId: null, onchainAccountFound: null,
    onchainOwnerProgram: null, onchainSlot: null, flags: [],
    onchainReservesVerified: false, liquidityLockVerified: false,
    lpOwnerVerified: false, poolAuthenticityVerified: false,
    sellabilityVerified: false, tradable: false,
  });
  reviewSolanaOwnerGroups.mockResolvedValue({
    mint: 'So11111111111111111111111111111111111111112',
    network: 'solana-mainnet', status: 'disabled', verdict: 'unknown',
    checkedAt: null, observedTopTokenAccounts: 0,
    observedOwnerGroups: 0, largestObservedOwnerSharePct: null,
    ownerGroups: [], flags: [],
    interpretation: 'observed_token_account_owner_not_beneficial_owner',
    vaultClassificationVerified: false, beneficialOwnershipVerified: false,
    fullSafetyVerified: false, tradable: false,
  });
  reviewSolanaOrcaVaults.mockResolvedValue({
    mint: 'So11111111111111111111111111111111111111112',
    pool: '11111111111111111111111111111111',
    network: 'solana-mainnet', protocol: 'orca_whirlpool',
    status: 'disabled', verdict: 'unknown', checkedAt: null,
    poolSlot: null, vaultSlot: null, poolProgram: null, mintA: null, mintB: null,
    vaultA: null, vaultB: null, vaultARawAmount: null, vaultBRawAmount: null,
    vaultADecimals: null, vaultBDecimals: null, clmmLiquidityRaw: null,
    vaultAuthorityMatchesPool: false, warnings: [],
    vaultReservesObserved: false, activeSwapDepthVerified: false,
    liquidityLockVerified: false, lpWithdrawalAuthorityVerified: false,
    sellabilityVerified: false, tradable: false,
  });
  estimateSolanaImpact.mockResolvedValue({
    model: 'hypothetical_cpmm_50_50', liquidityUsd: 60000,
    orderUsd: 25, feeBps: 30, adverseSlippageBps: 100,
    modeledFeeUsd: 0.075, modeledOutputValueUsd: 24.90,
    modeledMinOutputValueUsd: 24.65,
    modeledPriceImpactPct: 0.08, modeledTotalCostPct: 0.4,
    orderVsLiquidityPct: 0.0417, flags: [], paperReviewStatus: 'research_only',
    realQuoteAvailable: false, tradable: false,
  });
});

describe('MemeCoinPage', () => {
  it('shows distinct, non-trading strategies and permits read-only selection', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);

    expect(await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' })).toBeInTheDocument();
    expect(screen.getByText('Sanal işlem planlandı')).toBeInTheDocument();
    expect(screen.getAllByText('Canlı işlemler kapalı').length).toBeGreaterThan(0);
    expect(screen.getByText('Pump.fun')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Momentum Avcısı/ }));
    expect(await screen.findByText('GMGN')).toBeInTheDocument();
    expect(screen.getByText('Hacim kalitesi')).toBeInTheDocument();
    expect(screen.getByText(/Henüz test işlemi/)).toBeInTheDocument();
    expect(getOverview).toHaveBeenCalledTimes(1);
  });

  it('does not fake status or performance when the backend is unreachable', async () => {
    getOverview.mockRejectedValue(new Error('network down'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.queryByText('GMGN')).not.toBeInTheDocument();
    expect(screen.queryByText('Pump.fun')).not.toBeInTheDocument();
  });
  it('only requests a scan on an explicit click and shows disabled state without fake candidates', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(scanCandidates).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    expect(await screen.findByText(/MEME_COIN_DISCOVERY_ENABLED=true/)).toBeInTheDocument();
    expect(scanCandidates).toHaveBeenCalledWith('new_launch');
    expect(screen.queryByText('MEME')).not.toBeInTheDocument();
  });

  it('renders unverified candidates and does not offer buy controls', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));

    expect(await screen.findByText('MEME')).toBeInTheDocument();
    expect(screen.getByText('Güvenlik doğrulanmadı')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('shows provider failure rather than pretending that an empty scan succeeded', async () => {
    scanCandidates.mockRejectedValue(new Error('API offline'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Veri kaynağına ulaşılamıyor/)).toBeInTheDocument();
  });

  it('shows Robinhood as a third isolated network with read-only RPC status', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    fireEvent.click(screen.getByRole('button', { name: /Robinhood Chain AI/ }));
    expect(screen.getByText('OpenCatz AI integration (planned)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aday coinleri tara' })).not.toBeInTheDocument();
    expect(getRobinhoodStatus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'RPC bağlantısını kontrol et' }));
    expect(await screen.findByText(/MEME_COIN_ROBINHOOD_RPC_ENABLED=true/)).toBeInTheDocument();
    expect(getRobinhoodStatus).toHaveBeenCalledTimes(1);
    expect(scanCandidates).not.toHaveBeenCalled();
  });

  it('displays actual RPC status but never implies Robinhood token safety', async () => {
    getRobinhoodStatus.mockResolvedValue({
      network: 'testnet', chainIdExpected: 46630, chainIdSeen: 46630,
      blockNumber: 123456, status: 'ok', checkedAt: '2026-11-18T12:00:00Z',
      error: null, tradingEnabled: false,
    });

    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: /Robinhood Chain AI/ }));
    fireEvent.click(screen.getByRole('button', { name: 'RPC bağlantısını kontrol et' }));

    expect(await screen.findByText(/Ağ kimliği doğrulandı/)).toBeInTheDocument();
    expect(screen.getByText('46630')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|satın al/i })).not.toBeInTheDocument();
  });

  it('only reviews a discovered Solana mint after click and keeps all orders disabled', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(reviewSolanaMint).not.toHaveBeenCalled();
    expect(estimateSolanaImpact).not.toHaveBeenCalled();
    expect(reviewSolanaConcentration).not.toHaveBeenCalled();
    expect(reviewSolanaPool).not.toHaveBeenCalled();
    expect(reviewSolanaOwnerGroups).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    const reviewButton = await screen.findByRole('button', { name: 'Mint ve maliyeti incele' });
    fireEvent.click(reviewButton);

    expect(await screen.findByText(/MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true/)).toBeInTheDocument();
    expect(screen.getByText(/Varsayımsal havuz maliyet modeli/)).toBeInTheDocument();
    expect(reviewSolanaMint).toHaveBeenCalledWith('So11111111111111111111111111111111111111112');
    expect(estimateSolanaImpact).toHaveBeenCalledWith(60000, 25);
    expect(reviewSolanaConcentration).toHaveBeenCalledWith('So11111111111111111111111111111111111111112');
    expect(reviewSolanaPool).toHaveBeenCalledWith('So11111111111111111111111111111111111111112', '11111111111111111111111111111111');
    expect(reviewSolanaOwnerGroups).toHaveBeenCalledWith('So11111111111111111111111111111111111111112');
    expect(screen.getByText(/MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=true/)).toBeInTheDocument();
    expect(screen.getByText(/gerçek DEX teklifi/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|satın al/i })).not.toBeInTheDocument();
  });

  it('does not re-interpret a mint with revoked authorities as fully safe', async () => {
    reviewSolanaMint.mockResolvedValue({
      mint: 'So11111111111111111111111111111111111111112',
      network: 'solana-mainnet', status: 'screened', verdict: 'review_only',
      slot: 123, checkedAt: '2026-11-18T12:00:00Z',
      tokenProgram: 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
      mintAuthorityRevoked: true, freezeAuthorityRevoked: true, decimals: 9,
      supplyBaseUnits: '100000000', blockingReasons: [],
      remainingUnverified: ['sellability'], fullSafetyVerified: false, tradable: false,
    });
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));

    expect(await screen.findByText(/bu tokenin güvenli olduğu anlamına GELMEZ/)).toBeInTheDocument();
    expect(screen.getByText(/İşlem engeli devam ediyor/)).toBeInTheDocument();
  });

  it('shows token-account concentration as a warning, not as distinct wallet ownership', async () => {
    reviewSolanaConcentration.mockResolvedValue({
      mint: 'So11111111111111111111111111111111111111112',
      network: 'solana-mainnet', status: 'screened', verdict: 'concentration_signal',
      checkedAt: '2026-11-18T13:30:00Z', supplySlot: 10000, accountsSlot: 10015,
      supplyBaseUnits: '1000', observedAccounts: 3,
      topAccountPct: 25, topTenAccountsPct: 80, observedTopTwentyPct: 80,
      warningFlags: ['top_token_account_at_least_20pct','top_ten_token_accounts_at_least_70pct'],
      interpretation: 'token_accounts_not_wallets',
      ownerIdentityVerified: false, poolVaultsClassified: false,
      fullSafetyVerified: false, tradable: false,
    });
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));

    expect(await screen.findByText(/Yüksek hesap yoğunlaşması tespit edildi/)).toBeInTheDocument();
    expect(screen.getByText(/25.00%/)).toBeInTheDocument();
    expect(screen.getByText(/80.00%/)).toBeInTheDocument();
    expect(screen.getByText(/DEX havuzları veya ilişkili hesaplar ayrıştırılmadı/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|satın al/i })).not.toBeInTheDocument();
  });

  it('cross-checks two liquidity sources and shows sampled owner groups without a trade control', async () => {
    reviewSolanaPool.mockResolvedValue({
      mint: 'So11111111111111111111111111111111111111112',
      pool: '11111111111111111111111111111111',
      network: 'solana', status: 'screened', verdict: 'review_only',
      checkedAt: '2026-11-18T12:00:00Z', geckoterminalUsd: 60000,
      dexscreenerUsd: 61000, differencePct: 1.639, dexId: 'example',
      onchainAccountFound: true, onchainOwnerProgram: 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
      onchainSlot: 1234, flags: [], onchainReservesVerified: false,
      liquidityLockVerified: false, lpOwnerVerified: false,
      poolAuthenticityVerified: false, sellabilityVerified: false, tradable: false,
    });
    reviewSolanaOwnerGroups.mockResolvedValue({
      mint: 'So11111111111111111111111111111111111111112',
      network: 'solana-mainnet', status: 'screened', verdict: 'concentration_signal',
      checkedAt: '2026-11-18T12:00:00Z', observedTopTokenAccounts: 3,
      observedOwnerGroups: 2, largestObservedOwnerSharePct: 35,
      ownerGroups: [{ ownerAddress: '11111111111111111111111111111111',
        sampledTokenAccounts: 2, shareOfTotalSupplyPct: 35 }],
      flags: ['sampled_owner_group_at_least_20pct'],
      interpretation: 'observed_token_account_owner_not_beneficial_owner',
      vaultClassificationVerified: false, beneficialOwnershipVerified: false,
      fullSafetyVerified: false, tradable: false,
    });
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(reviewSolanaPool).not.toHaveBeenCalled();
    expect(reviewSolanaOwnerGroups).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));

    expect(await screen.findByText(/1.64%/)).toBeInTheDocument();
    expect(screen.getByText(/likidite kilidi henüz doğrulanmış DEĞİL/)).toBeInTheDocument();
    expect(screen.getByText(/en büyük 10 token hesabı örneklendi/i)).toBeInTheDocument();
    expect(screen.getAllByText(/35.00%/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('keeps Orca pool audit opt-in and exposes no buy control', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));

    expect(await screen.findByText(/Orca Whirlpool zincir üstü kasa kontrolü/)).toBeInTheDocument();
    expect(reviewSolanaOrcaVaults).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Orca kasalarını incele' }));

    expect(await screen.findByText(/MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=true/)).toBeInTheDocument();
    expect(reviewSolanaOrcaVaults).toHaveBeenCalledWith(
      'So11111111111111111111111111111111111111112',
      '11111111111111111111111111111111',
    );
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('shows observed on-chain Orca balances without promising executable liquidity', async () => {
    reviewSolanaOrcaVaults.mockResolvedValue({
      mint: 'So11111111111111111111111111111111111111112',
      pool: '11111111111111111111111111111111',
      network: 'solana-mainnet', protocol: 'orca_whirlpool',
      status: 'screened', verdict: 'review_only', checkedAt: '2026-11-18T12:00:00Z',
      poolSlot: 1000, vaultSlot: 1004,
      poolProgram: 'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',
      mintA: 'So11111111111111111111111111111111111111112',
      mintB: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
      vaultA: 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
      vaultB: 'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',
      vaultARawAmount: '420000', vaultBRawAmount: '120000',
      vaultADecimals: 6, vaultBDecimals: 6, clmmLiquidityRaw: '123456',
      vaultAuthorityMatchesPool: true, warnings: [],
      vaultReservesObserved: true, activeSwapDepthVerified: false,
      liquidityLockVerified: false, lpWithdrawalAuthorityVerified: false,
      sellabilityVerified: false, tradable: false,
    });
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        poolAddress: '11111111111111111111111111111111',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    fireEvent.click(screen.getByRole('button', { name: 'Orca kasalarını incele' }));

    expect(await screen.findByText(/420000/)).toBeInTheDocument();
    expect(screen.getByText(/120000/)).toBeInTheDocument();
    expect(screen.getByText(/işlem derinliği veya likidite kilidi hâlâ doğrulanmadı/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('shows separate idle paper ledgers without invented profit or buy controls', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    expect(await screen.findByText('İki bağımsız sanal işlem defteri')).toBeInTheDocument();
    expect(screen.getByText(/çevrimdışı test dosyalarıyla çalışabilir/)).toBeInTheDocument();
    expect(screen.getAllByText('Henüz çalışmıyor')).toHaveLength(2);
    expect(getPaperReplayStatus).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/%100 kâr|100% profit/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy|place order/i })).not.toBeInTheDocument();
  });

  it('fails visibly and never fabricates readiness when paper status endpoint is offline', async () => {
    getPaperReplayStatus.mockRejectedValue(new Error('backend unreachable'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    expect(await screen.findByText('Sanal test motorunun bağlantı durumu doğrulanamadı.')).toBeInTheDocument();
    expect(screen.queryByText('Çevrimdışı test motoru hazır')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy/i })).not.toBeInTheDocument();
  });

  it('only requests a Jupiter quote on user click, never an order', async () => {
    const testCandidate = {
    strategy: 'new_launch', symbol: 'MEME',
    tokenAddress: '11111111111111111111111111111111',
    poolAddress: 'So11111111111111111111111111111111111111112',
    liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
    ageMinutes: 15, buys5m: 20, sells5m: 12,
    researchScore: 81.5, riskStatus: 'unverified', tradable: false,
    source: 'geckoterminal',
  };
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [testCandidate],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    expect(getSolanaQuotePreview).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Fiyat teklifini sorgula' }));
    expect(await screen.findByText(/MEME_COIN_JUPITER_QUOTES_ENABLED=true/)).toBeInTheDocument();
    expect(getSolanaQuotePreview).toHaveBeenCalledWith(
      'new_launch', '11111111111111111111111111111111', 'buy', 25000000,
    );
    expect(screen.queryByRole('button', { name: /satın al|buy|execute|imzala/i })).not.toBeInTheDocument();
  });

  it('displays recorded raw Jupiter amounts and no actual execution claims', async () => {
    const testCandidate = {
    strategy: 'new_launch', symbol: 'MEME',
    tokenAddress: '11111111111111111111111111111111',
    poolAddress: 'So11111111111111111111111111111111111111112',
    liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
    ageMinutes: 15, buys5m: 20, sells5m: 12,
    researchScore: 81.5, riskStatus: 'unverified', tradable: false,
    source: 'geckoterminal',
  };
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [testCandidate],
    });
    getSolanaQuotePreview.mockResolvedValue({
      strategy: 'new_launch', mint: testCandidate.tokenAddress, side: 'buy',
      source: 'jupiter_swap_v2_order_quote_only',
      inputMint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
      outputMint: testCandidate.tokenAddress, amountInRaw: '25000000',
      status: 'ok', error: null, liveQuotePreview: true,
      walletConnected: false, transactionRequested: false,
      transactionSubmitted: false, tradable: false,
      quote: {
        captureId: 'ab'.repeat(32), source: 'jupiter_swap_v2_order_quote_only',
        strategy: 'new_launch', mint: testCandidate.tokenAddress, side: 'buy',
        inputMint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        outputMint: testCandidate.tokenAddress,
        amountInRaw: '25000000', amountOutRaw: '100000000',
        feeBps: 2, router: 'metis',
        capturedAtMs: 1000000, capturedAt: '1970-01-01T00:16:40+00:00',
        transactionReturned: false, executionIsReal: false,
        tokenSafetyVerified: false, estimatedNetworkFeeAvailable: false,
        tradable: false,
      },
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fiyat teklifini sorgula' }));
    expect((await screen.findAllByText(/100000000/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/25000000/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Cüzdan yok, işlem yapılmadı/)).toBeInTheDocument();
    expect(screen.getByText(/\"capture_id\":/)).toBeInTheDocument();
    expect(screen.queryByText(/\"captureId\":/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /satın al|buy|execute/i })).not.toBeInTheDocument();
  });

  it('supports explicit sell base-unit amounts and rejects invalid input', async () => {
    const testCandidate = {
    strategy: 'new_launch', symbol: 'MEME',
    tokenAddress: '11111111111111111111111111111111',
    poolAddress: 'So11111111111111111111111111111111111111112',
    liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
    ageMinutes: 15, buys5m: 20, sells5m: 12,
    researchScore: 81.5, riskStatus: 'unverified', tradable: false,
    source: 'geckoterminal',
  };
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [testCandidate],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    fireEvent.change(screen.getByLabelText(/Jupiter V2 — Gerçek fiyat teklifi önizlemesi/), {
      target: { value: 'sell' },
    });
    fireEvent.change(screen.getByLabelText(/Satılacak token miktarı/), {
      target: { value: '-5' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Fiyat teklifini sorgula' }));
    expect(await screen.findByText(/pozitif tam sayı/)).toBeInTheDocument();
    expect(getSolanaQuotePreview).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Satılacak token miktarı/), {
      target: { value: '1000000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Fiyat teklifini sorgula' }));
    expect(getSolanaQuotePreview).toHaveBeenCalledWith(
      'new_launch', '11111111111111111111111111111111', 'sell', 1000000,
    );
  });

  it('shows both V10 offline safety modules as not running, with no profit figures', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });

    expect(await screen.findByText('Sanal İşlem Risk Kontrolleri (V10)')).toBeInTheDocument();
    expect(screen.getAllByText('Arşiv ve risk modülü sunucuda çalışmıyor.')).toHaveLength(2);
    expect(screen.getByText(/İki strateji için ayrı SQLite teklif arşivi/)).toBeInTheDocument();
    expect(screen.getByText(/gerçek piyasa güvenliği veya kazanç anlamına gelmez/)).toBeInTheDocument();
    expect(getPaperRiskReadiness).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: /alım yap|satın al|start|execute|buy/i })).not.toBeInTheDocument();
  });

  it('shows V10 readiness endpoint failures without fabricated archive counts', async () => {
    getPaperRiskReadiness.mockRejectedValue(new Error('offline'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(await screen.findByText('Risk kontrolü hazırlık durumu doğrulanamadı.')).toBeInTheDocument();
    expect(screen.queryByText(/Çevrimdışı geliştirme hazır/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Gerçekleşen kar/i)).not.toBeInTheDocument();
  });

  it('shows the V11 offline valuation and recovery states without invented market PnL', async () => {
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(await screen.findByText('Açık Pozisyon Değerleme ve Kurtarma (V11)')).toBeInTheDocument();
    expect(screen.getByText(/yerel kurtarma veritabanı sunucuya bağlı değil/)).toBeInTheDocument();
    expect(screen.getByText(/test senaryosunda girilen satış fiyatlarını kullanır/)).toBeInTheDocument();
    expect(screen.getByText(/kayıtlar tekrar hesaplanır ve SQLite kontrol noktasıyla karşılaştırılır/)).toBeInTheDocument();
    expect(getPaperMtmReadiness).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: /buy|satın al|sanal işlem başlat/i })).not.toBeInTheDocument();
  });

  it('fails closed if the V11 status endpoint is unavailable', async () => {
    getPaperMtmReadiness.mockRejectedValue(new Error('unreachable'));
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    expect(await screen.findByText('V11 modül hazırlık durumu doğrulanamadı.')).toBeInTheDocument();
    expect(screen.queryByText(/yerel kurtarma veritabanı sunucuya bağlı değil/)).not.toBeInTheDocument();
  });

  it('requires an explicit manual action for V12 comparison and never creates trades', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: '11111111111111111111111111111111',
        poolAddress: 'So11111111111111111111111111111111111111112',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    expect(await screen.findByText('İki Kaynaktan Fiyat Karşılaştırması (V12)')).toBeInTheDocument();
    expect(getSolanaMarkCrosscheck).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Satış fiyatlarını karşılaştır' }));
    expect(await screen.findByText(/MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=true/)).toBeInTheDocument();
    expect(getSolanaMarkCrosscheck).toHaveBeenCalledWith(
      'new_launch', '11111111111111111111111111111111',
      'So11111111111111111111111111111111111111112', 1000000,
    );
    expect(screen.queryByRole('button', { name: /satın al|buy|execute/i })).not.toBeInTheDocument();
  });

  it('flags large Jupiter/DEX price divergence and validates raw sell amount', async () => {
    scanCandidates.mockResolvedValue({
      strategy: 'new_launch', status: 'ok', source: 'geckoterminal',
      observedAt: '2026-11-18T12:00:00Z', error: null,
      candidates: [{
        strategy: 'new_launch', symbol: 'MEME',
        tokenAddress: '11111111111111111111111111111111',
        poolAddress: 'So11111111111111111111111111111111111111112',
        liquidityUsd: 60000, volume5mUsd: 9000, change5mPct: 7,
        ageMinutes: 15, buys5m: 20, sells5m: 12,
        researchScore: 81.5, riskStatus: 'unverified', tradable: false,
        source: 'geckoterminal',
      }],
    });
    getSolanaMarkCrosscheck.mockResolvedValue({
      strategy: 'new_launch', mint: '11111111111111111111111111111111',
      pool: 'So11111111111111111111111111111111111111112',
      network: 'solana-mainnet', status: 'screened', verdict: 'flagged',
      sampleSellRaw: '1000000', tokenDecimals: 6, mintSlot: 10000,
      jupiterPriceUsd: '1.600000000000', dexscreenerPriceUsd: '2.00',
      dexLiquidityUsd: '60000', priceDivergencePct: '20.0000',
      sampleQuotedUsd: '1.6', jupiterCapturedAtMs: 1000000,
      dexRetrievedAtMs: 1000100, checkedAt: '2026-11-18T12:00:00Z',
      quoteCaptureId: 'a'.repeat(64), dexId: 'orca',
      warningFlags: ['price_sources_diverge_over_10pct'],
      sourceIndependenceVerified: false,
      dexMarketObservationTimestampVerified: false,
      tokenSafetyVerified: false, sellFillVerified: false,
      markToMarketExecutionVerified: false, automatedPaperMarksEnabled: false,
      liveTradingEnabled: false, tradable: false,
    });
    render(<UiLanguageProvider><MemeCoinPage /></UiLanguageProvider>);
    await screen.findByRole('heading', { name: 'Meme Coin Stratejileri' });
    fireEvent.click(screen.getByRole('button', { name: 'Aday coinleri tara' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Mint ve maliyeti incele' }));
    fireEvent.change(screen.getByLabelText('Karşılaştırma için ham token miktarı'), {
      target: { value: '-100' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Satış fiyatlarını karşılaştır' }));
    expect(await screen.findByText(/Pozitif tam sayı ham token miktarı gir/)).toBeInTheDocument();
    expect(getSolanaMarkCrosscheck).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Karşılaştırma için ham token miktarı'), {
      target: { value: '1000000' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Satış fiyatlarını karşılaştır' }));
    expect(await screen.findByText(/20.0000%/)).toBeInTheDocument();
    expect(screen.getByText(/price_sources_diverge_over_10pct/)).toBeInTheDocument();
    expect(screen.getByText(/Otomatik sanal değerlemeye bağlanmadı/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|satın al|execute/i })).not.toBeInTheDocument();
  });

});
