import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, Database, Radar, RefreshCw, ShieldCheck, TrendingUp, Wallet } from 'lucide-react';
import { memeCoinApi, type MemeCoinOverview, type MemeCoinStrategyId, type MemeCoinDiscoveryResponse, type RobinhoodRpcStatus, type SolanaMintReview, type SolanaImpactEstimate, type SolanaConcentrationReview, type SolanaPoolReview, type SolanaOwnerGroupReview, type SolanaOrcaVaultReview, type MemeCoinPaperReplayStatus, type SolanaJupiterQuotePreview, type SolanaJupiterQuoteCapture, type MemeCoinOfflineRiskReadiness, type MemeCoinMtmReadiness, type SolanaDualSourceMarkPreview } from '../api/memeCoin';
import { AppPage, Badge, Card, PageHeader } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage } from '../i18n/uiText';

/** Explicitly export the Python bridge's snake_case snapshot contract.
 * Displaying the camelCase API client object would not replay correctly.
 */
function toOfflineQuoteCapture(raw: SolanaJupiterQuoteCapture) {
  return {
    capture_id: raw.captureId,
    source: raw.source,
    strategy: raw.strategy,
    mint: raw.mint,
    side: raw.side,
    input_mint: raw.inputMint,
    output_mint: raw.outputMint,
    amount_in_raw: raw.amountInRaw,
    amount_out_raw: raw.amountOutRaw,
    fee_bps: raw.feeBps,
    router: raw.router,
    captured_at_ms: raw.capturedAtMs,
    captured_at: raw.capturedAt,
    transaction_returned: raw.transactionReturned,
    execution_is_real: raw.executionIsReal,
    token_safety_verified: raw.tokenSafetyVerified,
    estimated_network_fee_available: raw.estimatedNetworkFeeAvailable,
    tradable: raw.tradable,
  };
}

const CONTENT = {
  tr: {
    title: 'Meme Coin Stratejileri',
    intro: 'Solana için iki bağımsız strateji ve Robinhood Chain için ayrı EVM modülü. Gerçek işlem yapılmaz.',
    refresh: 'Durumu yenile',
    unavailable: 'Strateji durumuna ulaşılamadı. Canlı veri veya işlem varmış gibi gösterilmiyor.',
    notConnected: 'Bağlı değil',
    planned: 'Sanal işlem planlandı',
    disabled: 'Canlı işlemler kapalı',
    newLaunch: 'Yeni Coin Avcısı',
    momentum: 'Momentum Avcısı',
    newLaunchInfo: 'Yeni token ve likidite havuzlarını tespit edip güvenlik incelemesi yapacak ayrı motor.',
    momentumInfo: 'Hacim, fiyat hareketi ve büyük cüzdan aktivitelerini inceleyecek ayrı motor.',
    strategy: 'Strateji ayrıntıları',
    sources: 'Planlanan veri kaynakları',
    checks: 'Planlanan risk kontrolleri',
    paper: 'Sanal işlem motoru',
    execution: 'Gerçek emir yürütme',
    ready: 'Etkin',
    pending: 'Henüz bağlı değil',
    data: 'Veri akışı',
    performance: 'Doğrulanmış performans',
    noResults: 'Henüz test işlemi veya performans kaydı bulunmuyor.',
    paperStatusTitle: 'İki bağımsız sanal işlem defteri',
    paperOfflineReady: 'Çevrimdışı test motoru hazır',
    paperNotRunning: 'Henüz çalışmıyor',
    paperUnlinked: 'Gerçek kotasyon bağlantısı yok. İki stratejinin sanal işlem defterleri yalnızca çevrimdışı test dosyalarıyla çalışabilir; panelde gerçek performans gösterilmez.',
    paperNotAvailable: 'Sanal test motorunun bağlantı durumu doğrulanamadı.',
    safetyTitle: 'Sanal İşlem Risk Kontrolleri (V10)',
    safetyOffline: 'Çevrimdışı geliştirme hazır, otomatik işlem çalışmıyor.',
    safetyNotRunning: 'Arşiv ve risk modülü sunucuda çalışmıyor.', 
    safetyJournal: 'İki strateji için ayrı SQLite teklif arşivi: yalnızca yerel dosyada manuel kullanım.',
    safetyGuard: 'Veri eskimesi, düşük likidite, günlük sanal zarar ve art arda başarısızlık kontrolleri.',
    safetyLimits: 'Acil durdurma: çevrimdışı test motorunda mevcut.',
    safetyDisclaimer: 'Bu kontroller gerçek piyasa güvenliği veya kazanç anlamına gelmez. Gerçek piyasa risk verileriyle doğrulanmadı.',
    safetyUnavailable: 'Risk kontrolü hazırlık durumu doğrulanamadı.',
    mtmTitle: 'Açık Pozisyon Değerleme ve Kurtarma (V11)',
    mtmReady: 'Çevrimdışı MTM simülasyonu ve yeniden başlatma kontrolü hazır.',
    mtmNotRunning: 'Simülasyon başlatılmadı, yerel kurtarma veritabanı sunucuya bağlı değil.',
    mtmLedgerInactive: 'V11 simülasyon defteri çevrimdışı.',
    mtmAssumptions: 'Değerleme, test senaryosunda girilen satış fiyatlarını kullanır. Gerçek fiyat ya da gerçekleşebilir satış teklifi değildir.',
    mtmRisk: 'Açık pozisyonların varsayımsal kaybı $50 günlük ve $100 toplam sınırları aşarsa yeni test alımları durur.',
    mtmRecovery: 'Yeniden açılışta kayıtlar tekrar hesaplanır ve SQLite kontrol noktasıyla karşılaştırılır.',
    mtmUnavailable: 'V11 modül hazırlık durumu doğrulanamadı.',
    paperLedgerNew: 'Yeni Coin Avcısı',
    paperLedgerMomentum: 'Momentum Avcısı',
    next: 'Sonraki geliştirme',
    nextInfo: 'Gerçek zamanlı Solana veri adaptörleri, risk filtreleri ve komisyon/kayma modellemeli sanal işlemler ayrı servis olarak eklenecek.',
    safety: 'Cüzdan bağlanmadı, alım satım yapılmıyor. Mevcut EBBot ve Solana Hype işlemleri değiştirilmedi.',
    noStrategies: 'Henüz kayıtlı strateji bulunmuyor.',
    scan: 'Aday coinleri tara',
    scanLoading: 'Taranıyor...',
    scanDisabled: 'Keşif özelliği sunucuda kapalı. MEME_COIN_DISCOVERY_ENABLED=true ile açılabilir.',
    scanUnavailable: 'Veri kaynağına ulaşılamıyor; aday listesi oluşturulmadı.',
    scanEmpty: 'Seçili koşullara uygun havuz bulunamadı.',
    scanResults: 'Araştırma adayları (alım sinyali değil)',
    scanNote: 'Havuz verileri gecikmeli olabilir. Token yetkileri, cüzdan dağılımı ve satılabilirlik doğrulanmadığı için tüm adaylar yalnızca izleme amaçlıdır.',
    scanScore: 'Araştırma puanı',
    scanLiquidity: 'Likidite (USD)',
    scanVolume: '5 dk hacim (USD)',
    scanChange: '5 dk değişim',
    scanAge: 'Havuz yaşı (dk)',
    scanTrades: 'Alış / Satış',
    scanUnverified: 'Güvenlik doğrulanmadı',
    scanTimestamp: 'Veri zamanı',
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: 'OpenCatz mimarisinden yararlanan, Solana sisteminden bağımsız EVM analiz modülü. DEX taraması ve ajanlar henüz bağlı değil.',
    robinhoodRpc: 'Robinhood Chain ağ durumu (yalnızca okuma)',
    robinhoodProbe: 'RPC bağlantısını kontrol et',
    robinhoodChecking: 'Kontrol ediliyor...',
    robinhoodDisabled: 'RPC kontrolü kapalı. MEME_COIN_ROBINHOOD_RPC_ENABLED=true ile açılabilir.',
    robinhoodUnavailable: 'Robinhood Chain RPC durumuna ulaşılamadı.',
    robinhoodMismatch: 'Ağ kimliği uyuşmuyor. Bu ağ güvenilir değil.',
    robinhoodHealthy: 'Ağ kimliği doğrulandı; bu sonuç token güvenliğini kanıtlamaz.',
    robinhoodNetwork: 'Ağ',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: 'Son blok',
    robinhoodWarning: 'OpenCatz, DEX taraması ve gerçek alım satım bağlı değil. Bu yalnızca RPC sağlık kontrolüdür.',
    robinhoodAgents: 'AI ajan modülleri (taslak)',
    inspect: 'Mint ve maliyeti incele',
    inspectTitle: 'Solana token ön incelemesi',
    inspectLoading: 'Kontrol ediliyor...',
    inspectAmount: 'Örnek işlem tutarı (USD)',
    mintDisabled: 'On-chain mint denetimi kapalı. MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true ile etkinleştirilebilir.',
    mintUnavailable: 'Mint kontrolü kullanılamıyor veya veri eksik.',
    mintBlocked: 'Token yetkisi kaynaklı engel veya desteklenmeyen program tespit edildi.',
    mintReviewOnly: 'Mint ve dondurma yetkisi kaldırılmış; bu tokenin güvenli olduğu anlamına GELMEZ.',
    mintAuthority: 'Yeni token basma yetkisi',
    freezeAuthority: 'Cüzdan dondurma yetkisi',
    authorityRevoked: 'Kaldırılmış',
    authorityActive: 'Aktif',
    authorityUnknown: 'Doğrulanamadı',
    unknownSafety: 'Likidite sahipliği, büyük cüzdanlar ve satış yapılabilirliği hâlâ doğrulanmadı. İşlem engeli devam ediyor.',
    concentrationTitle: 'En büyük token hesapları',
    concentrationDisclaimer: 'Bu sonuçlar cüzdan sahiplerini değil, token hesap bakiyelerini ölçer. DEX havuzları veya ilişkili hesaplar ayrıştırılmadı.',
    concentrationDisabled: 'Yoğunlaşma denetimi kapalı. MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=true ile açılır.',
    concentrationUnavailable: 'Token hesap dağılımı alınamadı veya tutarsız; işlem yapılamaz.',
    concentrationSignal: 'Yüksek hesap yoğunlaşması tespit edildi. Gerçek sahiplik ve havuz kasaları incelenmeli.',
    concentrationNoSignal: 'İlk 20 hesapta eşik aşımı görülmedi; bu sonuç tokenin güvenli olduğunu göstermez.',
    concentrationTop1: 'En büyük token hesabı',
    concentrationTop10: 'İlk 10 token hesabı',
    concentrationNote: 'Toplam arzdaki pay · Token hesapları, benzersiz yatırımcılar değildir',
    poolTitle: 'Havuz likiditesi çapraz kontrolü',
    poolDisabled: 'Havuz kontrolü kapalı. MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED=true ile açılır.',
    poolUnavailable: 'Havuz bilgileri doğrulanamadı; araştırma sonucu güvenilir değil.',
    poolBlocked: 'Likidite değerleri, havuz adresi veya zincir hesabı için uyarı oluştu.',
    poolReviewOnly: 'Veri kaynakları tutarlı görünüyor; havuz rezervleri veya likidite kilidi henüz doğrulanmış DEĞİL.',
    sourceDifference: 'Kaynaklar arası fark',
    poolAccountOwner: 'Havuz hesabının programı',
    poolDisclaimer: 'DEX Screener ve GeckoTerminal ortak kaynaklardan veri alabilir; eşleşmeleri bağımsız on-chain rezerv kanıtı değildir.',
    groupTitle: 'Sahip adresine göre gruplanan token hesapları',
    groupDisabled: 'Sahip adresi gruplaması kapalı. MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED=true ile açılır.',
    groupUnavailable: 'Zincir üzerindeki sahip adresleri gruplandırılamadı.',
    groupWarning: 'Bir veya daha fazla hesap aynı kontrol adresini kullanıyor; uyarı yoğunlaşması görüldü.',
    groupReviewOnly: 'Örneklenmiş hesaplarda eşik aşılmadı; güvenli anlamına gelmez.',
    groupDisclaimer: 'Yalnızca en büyük 10 token hesabı örneklendi. Kontrol adresi yatırımcının gerçek kimliğini, LP kilidini veya nihai sahipliği kanıtlamaz.',
    topGroup: 'En büyük gözlenen sahip grubu',
    orcaTitle: 'Orca Whirlpool zincir üstü kasa kontrolü',
    orcaButton: 'Orca kasalarını incele',
    orcaLoading: 'Orca kasaları sorgulanıyor...',
    orcaDisabled: 'Kontrol kapalı. MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=true ile açılır.',
    orcaUnsupported: 'Seçilen havuz Orca Whirlpool programına ait değil; bu denetim desteklemiyor.',
    orcaUnavailable: 'Orca havuz ya da kasa verileri doğrulanamadı.',
    orcaScreened: 'Havuz ve iki kasanın token adresleri eşleşti. Gerçek bakiyeler okundu; işlem derinliği veya likidite kilidi hâlâ doğrulanmadı.',
    orcaBlocked: 'Orca havuzunda sıfır bakiye veya sıfır güncel CLMM likiditesi uyarısı var.',
    orcaVaultA: 'Kasa A (ham birim)',
    orcaVaultB: 'Kasa B (ham birim)',
    orcaNotes: 'Yalnızca Orca Whirlpool ve klasik SPL token kasaları desteklenir. Ham bakiyeler, yürütülebilir alım/satım miktarı değildir.',
    jupTitle: 'Jupiter V2 — Gerçek fiyat teklifi önizlemesi',
    jupDescription: 'Cüzdan bağlamadan yalnızca teklif alınır. Bu teklif işlem, garanti edilmiş fiyat veya güvenlik onayı değildir.',
    jupBuy: 'Alım (USDC)',
    jupSell: 'Satım (ham token)',
    jupSellRaw: 'Satılacak token miktarı (en küçük ham birim)',
    jupPreview: 'Fiyat teklifini sorgula',
    jupLoading: 'Teklif alınıyor...',
    jupDisabled: 'Jupiter bağlantısı kapalı. MEME_COIN_JUPITER_QUOTES_ENABLED=true ile açılır.',
    jupUnavailable: 'Jupiter fiyat teklifi alınamadı veya yanıt doğrulanamadı.',
    jupCooldown: 'API hız sınırı: kısa bir aradan sonra yeniden dene.',
    jupInvalidInput: 'Satım için pozitif tam sayı olarak ham token miktarı gir.',
    jupOutput: 'Beklenen çıktı (ham birimler)',
    jupInput: 'Giriş (ham birimler)',
    jupRouter: 'Rota',
    jupFee: 'Jupiter platform ücreti (bps)',
    jupCaptured: 'Teklif kayıt zamanı (UTC)',
    jupCopy: 'JSON kaydını kopyalayarak daha sonra çevrimdışı testte kullanabilirsin.',
    jupRaw: 'Teklifin JSON kaydı',
    jupNoExecution: 'Cüzdan yok, işlem yapılmadı. Ağ ücretleri bu teklifte hesaplanmıyor. Satılabilirlik garanti değil.',
    markTitle: 'İki Kaynaktan Fiyat Karşılaştırması (V12)',
    markDesc: 'Jupiter satış teklifi ile seçilen havuzun DEX Screener USD fiyatını karşılaştırır. Cüzdan bağlanmaz.',
    markButton: 'Satış fiyatlarını karşılaştır',
    markLoading: 'Fiyatlar karşılaştırılıyor...',
    markDisabled: 'MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=true ile açılır.',
    markNeedsJupiter: 'MEME_COIN_JUPITER_QUOTES_ENABLED=true da etkin olmalı.',
    markRateLimited: 'Jupiter hız sınırı; daha sonra yeniden dene.',
    markUnavailable: 'Fiyat karşılaştırması doğrulanamadı.',
    markBadAmount: 'Pozitif tam sayı ham token miktarı gir.',
    markFlagged: 'Fiyat farkı, likidite veya mint riski var; güvenli değil.',
    markCompared: 'Fiyatlar yakın görünüyor; bağımsız güvenlik ya da satış garantisi değildir.',
    markJupPrice: 'Jupiter USD/token',
    markDexPrice: 'DEX Screener USD/token',
    markSpread: 'Fark',
    markRiskNote: 'DEX fiyatının kaynak gözlem zamanı doğrulanmıyor. Otomatik sanal değerlemeye bağlanmadı.',
    impactTitle: 'Varsayımsal havuz maliyet modeli',
    impactWarning: '50/50 sabit çarpım AMM varsayımıdır; gerçek DEX teklifi, gerçek kayma veya gerçekleşecek fiyat değildir.',
    impactPct: 'Model fiyat etkisi',
    costPct: 'Model toplam maliyet',
    feeUsd: 'Model havuz komisyonu',
    worstUsd: 'Ek %1 fiyat değişimi sonrası model alt sınırı',
    impactBlocked: 'Model limitlerini aşıyor; sanal işlem araştırması engellendi.',
    inspectFailed: 'İnceleme verileri alınamadı.',
  },
  en: {
    title: 'Meme Coin Strategies',
    intro: 'Two independent Solana strategies plus a separate Robinhood Chain EVM module. Live trading is disabled.',
    refresh: 'Refresh status',
    unavailable: 'Strategy status is unavailable. Live data and trades are not fabricated.',
    notConnected: 'Not connected',
    planned: 'Paper trading planned',
    disabled: 'Live trading disabled',
    newLaunch: 'New Launch Hunter',
    momentum: 'Momentum Hunter',
    newLaunchInfo: 'Independent engine planned to discover new tokens and liquidity pools with safety checks.',
    momentumInfo: 'Independent engine planned to examine volume, price action, and wallet activity.',
    strategy: 'Strategy details',
    sources: 'Planned data sources',
    checks: 'Planned risk checks',
    paper: 'Paper execution engine',
    execution: 'Real order execution',
    ready: 'Enabled',
    pending: 'Not connected yet',
    data: 'Data feed',
    performance: 'Verified performance',
    noResults: 'No simulation trades or performance results exist yet.',
    paperStatusTitle: 'Two independent paper ledgers',
    paperOfflineReady: 'Offline test runner available',
    paperNotRunning: 'Not running',
    paperUnlinked: 'No live quote feed is connected. Both strategy ledgers only run with local offline fixture files; this panel does not show verified performance.',
    paperNotAvailable: 'Could not verify offline replay status.',
    safetyTitle: 'Paper Replay Safety Controls (V10)',
    safetyOffline: 'Offline safeguards available; automated trading is not running.',
    safetyNotRunning: 'Archive and risk module are not running on the server.',
    safetyJournal: 'Independent SQLite quote archives for both strategies: manual local use only.',
    safetyGuard: 'Data freshness, low liquidity, daily modeled loss and repeated failure limits.',
    safetyLimits: 'Emergency stop available in the offline replay.',
    safetyDisclaimer: 'These do not prove market safety or profitability and have not been validated against real market risk data.',
    safetyUnavailable: 'Could not verify risk control readiness.',
    mtmTitle: 'Open Position Valuation & Recovery (V11)',
    mtmReady: 'Offline MTM scenario and restart verification available.',
    mtmNotRunning: 'The simulator is not running; local recovery database is not attached to the server.',
    mtmLedgerInactive: 'V11 paper ledger is offline.',
    mtmAssumptions: 'Valuation uses assumed sell prices from offline fixtures, not real or executable quotes.',
    mtmRisk: 'Modeled open losses of $50/day per strategy or $100 globally block new simulated buys.',
    mtmRecovery: 'Restart reconstructs history and compares the result with the SQLite checkpoint.',
    mtmUnavailable: 'V11 module readiness could not be verified.',
    paperLedgerNew: 'New Launch Hunter',
    paperLedgerMomentum: 'Momentum Hunter',
    next: 'Next development',
    nextInfo: 'Build isolated live Solana data adapters, risk filters, and realistic simulated fills including fees and slippage.',
    safety: 'No wallet is connected and no trades are placed. Existing EBBot and Solana Hype operations are unchanged.',
    noStrategies: 'No strategies registered.',
    scan: 'Scan candidates',
    scanLoading: 'Scanning...',
    scanDisabled: 'Discovery is disabled on this server. Set MEME_COIN_DISCOVERY_ENABLED=true to opt in.',
    scanUnavailable: 'Market source unavailable. No candidates shown.',
    scanEmpty: 'No pools pass the selected research filters.',
    scanResults: 'Research candidates (not buy signals)',
    scanNote: 'Pool data may be delayed. Token authorities, holders and sellability are not verified; every candidate is watch-only.',
    scanScore: 'Research score',
    scanLiquidity: 'Liquidity (USD)',
    scanVolume: '5m volume (USD)',
    scanChange: '5m change',
    scanAge: 'Pool age (min)',
    scanTrades: 'Buys / sells',
    scanUnverified: 'Risk unverified',
    scanTimestamp: 'Snapshot at',
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: 'Independent EVM analysis module inspired by OpenCatz architecture. DEX scans and AI agents are not connected yet.',
    robinhoodRpc: 'Robinhood Chain network status (read-only)',
    robinhoodProbe: 'Check RPC connectivity',
    robinhoodChecking: 'Checking...',
    robinhoodDisabled: 'RPC probe is disabled. Set MEME_COIN_ROBINHOOD_RPC_ENABLED=true to opt in.',
    robinhoodUnavailable: 'Robinhood Chain RPC status is unavailable.',
    robinhoodMismatch: 'Chain ID mismatch. The endpoint cannot be trusted.',
    robinhoodHealthy: 'Network chain ID verified; this does not verify token safety.',
    robinhoodNetwork: 'Network',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: 'Latest block',
    robinhoodWarning: 'OpenCatz, DEX scanning and live trading are not connected. This is only an RPC health check.',
    robinhoodAgents: 'AI agent modules (planned)',
    inspect: 'Review mint & costs',
    inspectTitle: 'Solana token preliminary review',
    inspectLoading: 'Reviewing...',
    inspectAmount: 'Example order size (USD)',
    mintDisabled: 'On-chain mint audit is disabled. Opt in with MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true.',
    mintUnavailable: 'Mint review is unavailable or lacks required data.',
    mintBlocked: 'Token authority or unsupported program restriction identified.',
    mintReviewOnly: 'Mint and freeze authorities revoked, but this does NOT prove token safety.',
    mintAuthority: 'Mint authority',
    freezeAuthority: 'Freeze authority',
    authorityRevoked: 'Revoked',
    authorityActive: 'Active',
    authorityUnknown: 'Unknown',
    unknownSafety: 'Holder concentration, liquidity ownership and sellability are still unverified. Trading remains blocked.',
    concentrationTitle: 'Largest token accounts',
    concentrationDisclaimer: 'These are token-account balances, not wallet owners. DEX vaults and related accounts have not been classified.',
    concentrationDisabled: 'Concentration check is off. Set MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=true to opt in.',
    concentrationUnavailable: 'Token-account balances are unavailable or inconsistent; no trading allowed.',
    concentrationSignal: 'High token-account concentration detected. Owner identity and pool vaults need further review.',
    concentrationNoSignal: 'No threshold crossed by the largest 20 accounts; this does not prove token safety.',
    concentrationTop1: 'Largest token account',
    concentrationTop10: 'Top 10 token accounts',
    concentrationNote: 'Share of total supply · Token accounts are not distinct investors',
    poolTitle: 'Pool liquidity cross-check',
    poolDisabled: 'Pool review is off. Set MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED=true.',
    poolUnavailable: 'Pool data could not be verified; no risk clearance available.',
    poolBlocked: 'Liquidity divergence, identity or on-chain account warning detected.',
    poolReviewOnly: 'Reported liquidity is consistent, but actual reserves and liquidity locks are NOT verified.',
    sourceDifference: 'Difference between sources',
    poolAccountOwner: 'Pool account program',
    poolDisclaimer: 'DEX Screener and GeckoTerminal may use shared sources; their agreement is not an independent on-chain reserve verification.',
    groupTitle: 'Token accounts grouped by on-chain owner address',
    groupDisabled: 'Owner grouping is off. Set MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED=true.',
    groupUnavailable: 'Token account control addresses could not be grouped.',
    groupWarning: 'Potential concentration among sampled token account owner addresses.',
    groupReviewOnly: 'No threshold crossed in sampled accounts; this is not a safety clearance.',
    groupDisclaimer: 'Only the ten largest token accounts are sampled. A control address does not establish ultimate ownership or LP locks.',
    topGroup: 'Largest sampled control-address group',
    orcaTitle: 'Orca Whirlpool on-chain vault review',
    orcaButton: 'Inspect Orca vaults',
    orcaLoading: 'Inspecting Orca vaults...',
    orcaDisabled: 'Audit disabled. Set MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=true.',
    orcaUnsupported: 'This pool is not owned by the Orca Whirlpool program; unsupported here.',
    orcaUnavailable: 'Orca pool or vault data could not be verified.',
    orcaScreened: 'Pool and vault mints match, balances observed. Tradable depth and liquidity locks remain unverified.',
    orcaBlocked: 'An empty vault or zero current CLMM liquidity was detected.',
    orcaVaultA: 'Vault A (raw units)',
    orcaVaultB: 'Vault B (raw units)',
    orcaNotes: 'Only Orca Whirlpool + classic SPL token vaults are supported. Raw vault balances are NOT executable buy/sell liquidity.',
    jupTitle: 'Jupiter V2 — Live quote preview',
    jupDescription: 'Walletless quote only. It does not prove execution, guaranteed price or token safety.',
    jupBuy: 'Buy (USDC)',
    jupSell: 'Sell (raw token)',
    jupSellRaw: 'Sell amount (smallest raw token units)',
    jupPreview: 'Request quote preview',
    jupLoading: 'Loading quote...',
    jupDisabled: 'Jupiter preview disabled. Set MEME_COIN_JUPITER_QUOTES_ENABLED=true.',
    jupUnavailable: 'Jupiter quote unavailable or failed validation.',
    jupCooldown: 'Rate limited: retry after a short cooldown.',
    jupInvalidInput: 'Enter a positive integer amount in raw token base units.',
    jupOutput: 'Expected output (raw units)',
    jupInput: 'Input (raw units)',
    jupRouter: 'Router',
    jupFee: 'Jupiter platform fee (bps)',
    jupCaptured: 'Captured at (UTC)',
    jupCopy: 'Copy the JSON snapshot for future local offline replay.',
    jupRaw: 'Quote JSON snapshot',
    jupNoExecution: 'No wallet or transaction. Network fees are not in this quote. Sellability and actual fills are not guaranteed.',
    markTitle: 'Two-source price comparison (V12)',
    markDesc: 'Compares a Jupiter sell quote with the USD price of the exact DEX Screener pool, without wallets.',
    markButton: 'Compare sell prices',
    markLoading: 'Comparing prices...',
    markDisabled: 'Set MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=true.',
    markNeedsJupiter: 'Also enable MEME_COIN_JUPITER_QUOTES_ENABLED=true.',
    markRateLimited: 'Jupiter rate limit: retry later.',
    markUnavailable: 'Price comparison could not be verified.',
    markBadAmount: 'Enter a positive integer token amount in raw units.',
    markFlagged: 'Price discrepancy, liquidity or mint warning; not safe.',
    markCompared: 'Prices appear close, but no independent safety or sellability confirmation.',
    markJupPrice: 'Jupiter USD/token',
    markDexPrice: 'DEX Screener USD/token',
    markSpread: 'Difference',
    markRiskNote: 'DEX market observation timestamp is unverified. Not connected to automated paper valuation.',
    impactTitle: 'Hypothetical pool cost model',
    impactWarning: 'Assumes 50/50 constant-product AMM; NOT an executable quote, actual slippage or real fill price.',
    impactPct: 'Modeled price impact',
    costPct: 'Modeled total cost',
    feeUsd: 'Modeled pool fee',
    worstUsd: 'Modeled floor after extra 1% adverse move',
    impactBlocked: 'Model limits exceeded; paper-trade research blocked.',
    inspectFailed: 'Could not retrieve review data.',
  },
  zh: {
    title: 'Meme Coin 策略',
    intro: 'Solana 双策略和独立的 Robinhood Chain EVM 模块。实盘交易关闭。',
    refresh: '刷新状态',
    unavailable: '无法获取策略状态。不展示虚构的实时数据或交易。',
    notConnected: '未连接',
    planned: '计划模拟交易',
    disabled: '实盘已关闭',
    newLaunch: '新币发现',
    momentum: '动量发现',
    newLaunchInfo: '计划独立发现新代币及流动性池并进行安全检查。',
    momentumInfo: '计划独立分析成交量、价格波动和钱包活动。',
    strategy: '策略详情',
    sources: '计划数据源',
    checks: '计划风控检查',
    paper: '模拟执行引擎',
    execution: '实盘执行',
    ready: '已启用',
    pending: '尚未连接',
    data: '行情数据',
    performance: '已验证业绩',
    noResults: '尚无模拟交易或业绩记录。',
    paperStatusTitle: '两个独立模拟交易账本',
    paperOfflineReady: '离线测试引擎可用',
    paperNotRunning: '未运行',
    paperUnlinked: '尚未连接真实报价。两个策略账本只处理本地离线数据，不展示未经验证的收益。',
    paperNotAvailable: '无法确认离线回放状态。',
    safetyTitle: '模拟交易风险控制（V10）',
    safetyOffline: '离线保护模块已准备，自动交易没有运行。',
    safetyNotRunning: '服务器未运行档案或风险模块。',
    safetyJournal: '两个独立策略的 SQLite 本地报价档案，仅手动使用。',
    safetyGuard: '数据时效、流动性、每日模拟损失和连续失败限制。',
    safetyLimits: '离线模拟支持紧急停止。',
    safetyDisclaimer: '不代表真实市场安全或盈利，尚未验证实时市场风险数据。',
    safetyUnavailable: '无法确认风险控制就绪状态。',
    mtmTitle: '持仓估值及故障恢复（V11）',
    mtmReady: '离线持仓估值及重启校验模块已准备。',
    mtmNotRunning: '模拟器未运行，恢复数据库没有接入服务器。',
    mtmLedgerInactive: 'V11 模拟账本离线。',
    mtmAssumptions: '估值使用离线情景的假设卖出价格，不是真实可成交报价。',
    mtmRisk: '单策略每日模拟损失 50 美元或总损失 100 美元会停止新的模拟买单。',
    mtmRecovery: '重启时重放交易历史，并与 SQLite 检查点核对。',
    mtmUnavailable: '无法确认 V11 模块状态。',
    paperLedgerNew: '新币发现',
    paperLedgerMomentum: '动量发现',
    next: '下一阶段',
    nextInfo: '搭建独立的 Solana 数据适配器、风控过滤器和包含费用及滑点的模拟成交。',
    safety: '未连接钱包、未执行交易。现有 EBBot 与 Solana Hype 不受影响。',
    noStrategies: '暂无策略。',
    scan: '扫描候选池',
    scanLoading: '扫描中...',
    scanDisabled: '服务器未启用扫描。设置 MEME_COIN_DISCOVERY_ENABLED=true 后启用。',
    scanUnavailable: '数据源不可用，未显示候选资产。',
    scanEmpty: '没有符合条件的流动性池。',
    scanResults: '研究候选（非买入信号）',
    scanNote: '池数据可能延迟。代币权限、持有分布和可卖性未验证，仅供观察。',
    scanScore: '研究评分',
    scanLiquidity: '流动性 (USD)',
    scanVolume: '5分钟成交额',
    scanChange: '5分钟涨跌',
    scanAge: '池年龄（分钟）',
    scanTrades: '买入 / 卖出',
    scanUnverified: '风险未验证',
    scanTimestamp: '快照时间',
    robinhood: 'Robinhood Chain AI',
    robinhoodInfo: '独立的 EVM 分析模块，借鉴 OpenCatz 架构；DEX 扫描和智能代理尚未连接。',
    robinhoodRpc: 'Robinhood Chain 网络状态（只读）',
    robinhoodProbe: '检测 RPC 连接',
    robinhoodChecking: '检测中...',
    robinhoodDisabled: 'RPC 检测未启用。设置 MEME_COIN_ROBINHOOD_RPC_ENABLED=true 后开启。',
    robinhoodUnavailable: 'Robinhood Chain RPC 状态不可用。',
    robinhoodMismatch: '链 ID 不匹配，网络不可信。',
    robinhoodHealthy: '网络 ID 已验证；不代表代币安全。',
    robinhoodNetwork: '网络',
    robinhoodChainId: 'Chain ID',
    robinhoodBlock: '最新区块',
    robinhoodWarning: '尚未连接 OpenCatz、DEX 扫描或实盘。这里只检测 RPC 健康状态。',
    robinhoodAgents: 'AI 代理模块（规划中）',
    inspect: '检查 Mint 与成本',
    inspectTitle: 'Solana 代币初步检查',
    inspectLoading: '检查中...',
    inspectAmount: '模拟订单金额（美元）',
    mintDisabled: '链上 Mint 检查未开启。设置 MEME_COIN_SOLANA_MINT_AUDIT_ENABLED=true 后启用。',
    mintUnavailable: 'Mint 检查不可用或缺少数据。',
    mintBlocked: '检测到代币权限风险或不支持的程序。',
    mintReviewOnly: '铸造和冻结权限已撤销，但不表示代币安全。',
    mintAuthority: '铸币权限',
    freezeAuthority: '冻结权限',
    authorityRevoked: '已撤销',
    authorityActive: '有效',
    authorityUnknown: '未知',
    unknownSafety: '持仓集中度、流动性所有权和可卖性仍未验证，交易继续禁止。',
    concentrationTitle: '最大代币账户',
    concentrationDisclaimer: '结果统计代币账户，不是钱包实际持有人。未区分 DEX 资金池和关联账户。',
    concentrationDisabled: '账户集中度检查关闭。设置 MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED=true 可开启。',
    concentrationUnavailable: '账户余额数据不可用或不一致，不允许交易。',
    concentrationSignal: '发现高账户集中度，需要继续验证所有权和池资金。',
    concentrationNoSignal: '前 20 个账户未超过阈值，但不代表代币安全。',
    concentrationTop1: '最大代币账户',
    concentrationTop10: '前 10 个代币账户',
    concentrationNote: '占总供应量比例 · 账户不代表独立投资者',
    poolTitle: '资金池流动性交叉核查',
    poolDisabled: '资金池核查关闭。设置 MEME_COIN_SOLANA_LIQUIDITY_REVIEW_ENABLED=true 后开启。',
    poolUnavailable: '资金池数据无法核对，不表示安全。',
    poolBlocked: '流动性数值、池地址或链上账户存在警示。',
    poolReviewOnly: '平台数据基本一致，但未验证真实储备或流动性锁定。',
    sourceDifference: '数据源差异',
    poolAccountOwner: '资金池账户程序',
    poolDisclaimer: 'DEX Screener 和 GeckoTerminal 可能共享数据源；一致性不能证明链上储备。',
    groupTitle: '代币账户按链上控制地址分组',
    groupDisabled: '控制地址分组关闭。设置 MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED=true 后开启。',
    groupUnavailable: '无法分组链上控制地址。',
    groupWarning: '样本中的控制地址存在集中度警示。',
    groupReviewOnly: '样本未超阈值，但不证明安全。',
    groupDisclaimer: '仅抽样前十个代币账户；控制地址不代表最终受益人或 LP 锁定。',
    topGroup: '最大样本控制组',
    orcaTitle: 'Orca Whirlpool 链上资金库核查',
    orcaButton: '检查 Orca 资金库',
    orcaLoading: '正在读取 Orca 资金库...',
    orcaDisabled: '检查未开启。设置 MEME_COIN_ORCA_VAULT_AUDIT_ENABLED=true。',
    orcaUnsupported: '该资金池不是 Orca Whirlpool 程序账户，不支持此检查。',
    orcaUnavailable: '无法核实 Orca 资金池或资金库。',
    orcaScreened: '资金池及代币地址匹配；已读取余额，但交易深度及锁定状态仍未知。',
    orcaBlocked: '检测到资金库余额为零或 CLMM 流动性为零。',
    orcaVaultA: '资金库 A（原始单位）',
    orcaVaultB: '资金库 B（原始单位）',
    orcaNotes: '仅支持 Orca Whirlpool 和经典 SPL Token。账户余额不代表可成交交易深度。',
    jupTitle: 'Jupiter V2 — 实时报价预览',
    jupDescription: '无需钱包，仅获取报价；不代表成交、安全或保证价格。',
    jupBuy: '买入 (USDC)',
    jupSell: '卖出 (原始单位)',
    jupSellRaw: '卖出代币的最小原始单位',
    jupPreview: '获取报价',
    jupLoading: '获取报价中...',
    jupDisabled: 'Jupiter 报价关闭。设置 MEME_COIN_JUPITER_QUOTES_ENABLED=true。',
    jupUnavailable: '无法获取或核验 Jupiter 报价。',
    jupCooldown: '请求限速，请稍后重试。',
    jupInvalidInput: '请输入正整数的代币原始单位。',
    jupOutput: '预计输出（原始单位）',
    jupInput: '输入（原始单位）',
    jupRouter: '路由',
    jupFee: 'Jupiter 平台费用 (bps)',
    jupCaptured: '报价记录时间 (UTC)',
    jupCopy: '可复制 JSON 快照用于离线回放。',
    jupRaw: '报价 JSON 快照',
    jupNoExecution: '无钱包和交易；报价未包含网络费用，也不保证可卖出或成交。',
    markTitle: '双数据源价格比对（V12）',
    markDesc: '比较 Jupiter 卖出报价与指定 DEX Screener 池的美元报价，不连接钱包。',
    markButton: '对比卖出报价',
    markLoading: '正在比对...',
    markDisabled: '请启用 MEME_COIN_DUAL_SOURCE_MARKS_ENABLED=true。',
    markNeedsJupiter: '还需要 MEME_COIN_JUPITER_QUOTES_ENABLED=true。',
    markRateLimited: 'Jupiter 限速，请稍后重试。',
    markUnavailable: '无法核验价格对比。',
    markBadAmount: '请输入正整数代币原始单位。',
    markFlagged: '价格、流动性或代币存在警告，不能确认安全。',
    markCompared: '价格接近不证明独立来源、可卖出性或安全。',
    markJupPrice: 'Jupiter 美元/代币',
    markDexPrice: 'DEX Screener 美元/代币',
    markSpread: '差异',
    markRiskNote: 'DEX 来源观察时间未证实，未连接自动模拟估值。',
    impactTitle: '假设的资金池成本模型',
    impactWarning: '采用 50/50 恒定乘积模型，不是真实 DEX 报价、真实滑点或成交价格。',
    impactPct: '模型价格影响',
    costPct: '模型总成本',
    feeUsd: '模型手续费',
    worstUsd: '额外 1% 不利波动后的模型下限',
    impactBlocked: '超出模型限制，不允许模拟研究。',
    inspectFailed: '无法获取检查数据。',
  },
} satisfies Record<UiLanguage, Record<string, string>>;

const STRATEGY_DETAILS: Record<MemeCoinStrategyId, { icon: typeof Radar; accent: string }> = {
  new_launch: { icon: Radar, accent: 'text-cyan' },
  momentum: { icon: TrendingUp, accent: 'text-success' },
  robinhood_chain: { icon: Radar, accent: 'text-purple' },
};

const RISK_LABELS: Record<string, Record<UiLanguage, string>> = {
  token_authorities: { tr: 'Token yetkileri', en: 'Token authorities', zh: '代币权限' },
  holder_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Holder concentration', zh: '持仓集中度' },
  liquidity: { tr: 'Likidite', en: 'Liquidity', zh: '流动性' },
  sell_simulation: { tr: 'Satış simülasyonu', en: 'Sell simulation', zh: '卖出模拟' },
  volume_quality: { tr: 'Hacim kalitesi', en: 'Volume integrity', zh: '成交量质量' },
  wallet_concentration: { tr: 'Cüzdan yoğunlaşması', en: 'Wallet concentration', zh: '钱包集中度' },
  price_impact: { tr: 'Fiyat etkisi', en: 'Price impact', zh: '价格冲击' },
  evm_contract_permissions: { tr: 'Akıllı sözleşme yetkileri', en: 'Smart contract permissions', zh: '智能合约权限' },
  pool_liquidity: { tr: 'Havuz likiditesi', en: 'Pool liquidity', zh: '资金池流动性' },
};

export default function MemeCoinPage() {
  const { language } = useUiLanguage();
  const copy = CONTENT[language];
  const [overview, setOverview] = useState<MemeCoinOverview | null>(null);
  const [paperStatus, setPaperStatus] = useState<MemeCoinPaperReplayStatus | null>(null);
  const [paperStatusError, setPaperStatusError] = useState(false);
  const [riskReadiness, setRiskReadiness] = useState<MemeCoinOfflineRiskReadiness | null>(null);
  const [riskReadinessError, setRiskReadinessError] = useState(false);
  const [mtmReadiness, setMtmReadiness] = useState<MemeCoinMtmReadiness | null>(null);
  const [mtmReadinessError, setMtmReadinessError] = useState(false);
  const [selected, setSelected] = useState<MemeCoinStrategyId>('new_launch');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [scanResult, setScanResult] = useState<MemeCoinDiscoveryResponse | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState(false);
  const [researchAmount, setResearchAmount] = useState(25);
  const [researchTarget, setResearchTarget] = useState<{ mint: string; symbol: string; pool: string } | null>(null);
  const [mintResearch, setMintResearch] = useState<SolanaMintReview | null>(null);
  const [impactResearch, setImpactResearch] = useState<SolanaImpactEstimate | null>(null);
  const [concentrationResearch, setConcentrationResearch] = useState<SolanaConcentrationReview | null>(null);
  const [poolResearch, setPoolResearch] = useState<SolanaPoolReview | null>(null);
  const [ownerGroupResearch, setOwnerGroupResearch] = useState<SolanaOwnerGroupReview | null>(null);
  const [poolResearchError, setPoolResearchError] = useState(false);
  const [ownerGroupResearchError, setOwnerGroupResearchError] = useState(false);
  const [concentrationError, setConcentrationError] = useState(false);
  const [mintResearchError, setMintResearchError] = useState(false);
  const [impactResearchError, setImpactResearchError] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [orcaReview, setOrcaReview] = useState<SolanaOrcaVaultReview | null>(null);
  const [orcaLoading, setOrcaLoading] = useState(false);
  const [orcaError, setOrcaError] = useState(false);
  const [quoteSide, setQuoteSide] = useState<'buy' | 'sell'>('buy');
  const [sellRawAmount, setSellRawAmount] = useState('1000000');
  const [quotePreview, setQuotePreview] = useState<SolanaJupiterQuotePreview | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState(false);
  const [quoteInputError, setQuoteInputError] = useState(false);
  const quoteRequestSeq = useRef(0);
  const markRequestSeq = useRef(0);
  const [markPreview, setMarkPreview] = useState<SolanaDualSourceMarkPreview | null>(null);
  const [markLoading, setMarkLoading] = useState(false);
  const [markError, setMarkError] = useState(false);
  const [markInputError, setMarkInputError] = useState(false);
  const orcaRequestSeq = useRef(0);
  const researchRequestSeq = useRef(0);
  const [robinhoodStatus, setRobinhoodStatus] = useState<RobinhoodRpcStatus | null>(null);
  const [robinhoodLoading, setRobinhoodLoading] = useState(false);
  const [robinhoodError, setRobinhoodError] = useState(false);
  const robinhoodRequestSeq = useRef(0);
  const scanRequestSeq = useRef(0);
  const requestSeq = useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(false);
    try {
      const [overviewResult, paperResult, riskResult, mtmResult] = await Promise.allSettled([
        memeCoinApi.getOverview(),
        memeCoinApi.getPaperReplayStatus(),
        memeCoinApi.getPaperRiskReadiness(),
        memeCoinApi.getPaperMtmReadiness(),
      ]);
      if (seq === requestSeq.current) {
        if (overviewResult.status === 'fulfilled') {
          setOverview(overviewResult.value);
        } else {
          setOverview(null);
          setError(true);
        }
        if (paperResult.status === 'fulfilled') {
          setPaperStatus(paperResult.value);
          setPaperStatusError(false);
        } else {
          setPaperStatus(null);
          setPaperStatusError(true);
        }
        if (riskResult.status === 'fulfilled') {
          setRiskReadiness(riskResult.value);
          setRiskReadinessError(false);
        } else {
          setRiskReadiness(null);
          setRiskReadinessError(true);
        }
        if (mtmResult.status === 'fulfilled') {
          setMtmReadiness(mtmResult.value);
          setMtmReadinessError(false);
        } else {
          setMtmReadiness(null);
          setMtmReadinessError(true);
        }
      }
    } catch {
      if (seq === requestSeq.current) {
        setOverview(null);
        setPaperStatus(null);
        setRiskReadiness(null);
        setMtmReadiness(null);
        setError(true);
        setPaperStatusError(true);
        setRiskReadinessError(true);
        setMtmReadinessError(true);
      }
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => { requestSeq.current += 1; };
  }, [refresh]);

  const scanCandidates = useCallback(async () => {
    if (selected === 'robinhood_chain') return;
    const seq = ++scanRequestSeq.current;
    setScanLoading(true);
    setScanError(false);
    setScanResult(null);
    researchRequestSeq.current += 1;
    orcaRequestSeq.current += 1;
    quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
    setOrcaReview(null);
    setQuotePreview(null);
    setMarkPreview(null);
    setQuoteLoading(false);
    setQuoteError(false);
    setQuoteInputError(false);
    setOrcaError(false);
    setOrcaLoading(false);
    setResearchTarget(null);
    setMintResearch(null);
    setImpactResearch(null);
    setConcentrationResearch(null);
    setPoolResearch(null);
    setOwnerGroupResearch(null);
    setPoolResearchError(false);
    setOwnerGroupResearchError(false);
    setConcentrationError(false);
    try {
      const result = await memeCoinApi.scanCandidates(selected);
      if (seq === scanRequestSeq.current) setScanResult(result);
    } catch {
      if (seq === scanRequestSeq.current) {
        setScanResult(null);
        setScanError(true);
      }
    } finally {
      if (seq === scanRequestSeq.current) setScanLoading(false);
    }
  }, [selected]);

  const inspectSolanaCandidate = useCallback(async (mint: string, symbol: string, pool: string, liquidityUsd: number) => {
    const seq = ++researchRequestSeq.current;
    setResearchTarget({ mint, symbol, pool });
    orcaRequestSeq.current += 1;
    quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
    setOrcaReview(null);
    setQuotePreview(null);
    setMarkPreview(null);
    setQuoteLoading(false);
    setQuoteError(false);
    setQuoteInputError(false);
    setOrcaLoading(false);
    setOrcaError(false);
    setMintResearch(null);
    setImpactResearch(null);
    setConcentrationResearch(null);
    setPoolResearch(null);
    setOwnerGroupResearch(null);
    setPoolResearchError(false);
    setOwnerGroupResearchError(false);
    setConcentrationError(false);
    setMintResearchError(false);
    setImpactResearchError(false);
    setResearchLoading(true);
    const [mintResponse, impactResponse, concentrationResponse, poolResponse, ownerGroupResponse] = await Promise.allSettled([
      memeCoinApi.reviewSolanaMint(mint),
      memeCoinApi.estimateSolanaImpact(liquidityUsd, researchAmount),
      memeCoinApi.reviewSolanaConcentration(mint),
      memeCoinApi.reviewSolanaPool(mint, pool),
      memeCoinApi.reviewSolanaOwnerGroups(mint),
    ]);
    if (seq !== researchRequestSeq.current) return;
    if (mintResponse.status === 'fulfilled') {
      setMintResearch(mintResponse.value);
    } else {
      setMintResearchError(true);
    }
    if (impactResponse.status === 'fulfilled') {
      setImpactResearch(impactResponse.value);
    } else {
      setImpactResearchError(true);
    }
    if (concentrationResponse.status === 'fulfilled') {
      setConcentrationResearch(concentrationResponse.value);
    } else {
      setConcentrationError(true);
    }
    if (poolResponse.status === 'fulfilled') {
      setPoolResearch(poolResponse.value);
    } else {
      setPoolResearchError(true);
    }
    if (ownerGroupResponse.status === 'fulfilled') {
      setOwnerGroupResearch(ownerGroupResponse.value);
    } else {
      setOwnerGroupResearchError(true);
    }
    setResearchLoading(false);
  }, [researchAmount]);

  const inspectOrcaVaults = useCallback(async (mint: string, pool: string) => {
    const seq = ++orcaRequestSeq.current;
    setOrcaReview(null);
    setQuotePreview(null);
    setMarkPreview(null);
    setQuoteLoading(false);
    setQuoteError(false);
    setQuoteInputError(false);
    setOrcaError(false);
    setOrcaLoading(true);
    try {
      const data = await memeCoinApi.reviewSolanaOrcaVaults(mint, pool);
      if (seq === orcaRequestSeq.current) setOrcaReview(data);
    } catch {
      if (seq === orcaRequestSeq.current) setOrcaError(true);
    } finally {
      if (seq === orcaRequestSeq.current) setOrcaLoading(false);
    }
  }, []);

  const inspectJupiterQuote = useCallback(async () => {
    const strategy = selected;
    if (strategy === 'robinhood_chain' || !researchTarget) return;
    const rawAmount = quoteSide === 'buy' ? researchAmount * 1_000_000 : Number(sellRawAmount);
    if (!Number.isSafeInteger(rawAmount) || rawAmount < 1 || rawAmount > 1_000_000_000_000_000
        || (quoteSide === 'sell' && !/^[0-9]+$/.test(sellRawAmount))) {
      setQuoteInputError(true);
      setQuotePreview(null);
    setMarkPreview(null);
      return;
    }
    setQuoteInputError(false);
    setQuoteError(false);
    setQuotePreview(null);
    setMarkPreview(null);
    setQuoteLoading(true);
    const seq = ++quoteRequestSeq.current;
    try {
      const result = await memeCoinApi.getSolanaQuotePreview(
        strategy, researchTarget.mint, quoteSide, rawAmount,
      );
      if (seq === quoteRequestSeq.current) setQuotePreview(result);
    } catch {
      if (seq === quoteRequestSeq.current) setQuoteError(true);
    } finally {
      if (seq === quoteRequestSeq.current) setQuoteLoading(false);
    }
  }, [quoteSide, researchAmount, researchTarget, selected, sellRawAmount]);

  const inspectDualSourceMark = useCallback(async () => {
    if (selected === 'robinhood_chain' || !researchTarget) return;
    const amount = Number(sellRawAmount);
    if (!/^[0-9]+$/.test(sellRawAmount)
      || !Number.isSafeInteger(amount) || amount < 1 || amount > 1_000_000_000_000_000) {
      setMarkInputError(true);
      setMarkPreview(null);
      return;
    }
    setMarkInputError(false);
    setMarkError(false);
    setMarkPreview(null);
    setMarkLoading(true);
    const sequence = ++markRequestSeq.current;
    try {
      const result = await memeCoinApi.getSolanaMarkCrosscheck(
        selected, researchTarget.mint, researchTarget.pool, amount,
      );
      if (sequence === markRequestSeq.current) setMarkPreview(result);
    } catch {
      if (sequence === markRequestSeq.current) setMarkError(true);
    } finally {
      if (sequence === markRequestSeq.current) setMarkLoading(false);
    }
  }, [selected, researchTarget, sellRawAmount]);

  const checkRobinhood = useCallback(async () => {
    const seq = ++robinhoodRequestSeq.current;
    setRobinhoodLoading(true);
    setRobinhoodError(false);
    setRobinhoodStatus(null);
    try {
      const data = await memeCoinApi.getRobinhoodStatus();
      if (seq === robinhoodRequestSeq.current) setRobinhoodStatus(data);
    } catch {
      if (seq === robinhoodRequestSeq.current) {
        setRobinhoodStatus(null);
        setRobinhoodError(true);
      }
    } finally {
      if (seq === robinhoodRequestSeq.current) setRobinhoodLoading(false);
    }
  }, []);

  useEffect(() => () => {
    scanRequestSeq.current += 1;
    robinhoodRequestSeq.current += 1;
    researchRequestSeq.current += 1;
    orcaRequestSeq.current += 1;
    quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
  }, []);

  const current = overview?.strategies.find((item) => item.id === selected) ?? overview?.strategies[0];
  const currentDetails = current ? STRATEGY_DETAILS[current.id] : undefined;
  const name = (id: MemeCoinStrategyId) => id === 'new_launch' ? copy.newLaunch : id === 'momentum' ? copy.momentum : copy.robinhood;
  const description = (id: MemeCoinStrategyId) => id === 'new_launch' ? copy.newLaunchInfo : id === 'momentum' ? copy.momentumInfo : copy.robinhoodInfo;

  return (
    <AppPage>
      <div className="space-y-5">
        <PageHeader
          eyebrow="SOLANA + ROBINHOOD CHAIN / EBBOT"
          title={copy.title}
          description={copy.intro}
          actions={
            <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void refresh()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              {copy.refresh}
            </button>
          }
        />

        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="warning">{copy.planned}</Badge>
            <Badge variant="default">{copy.disabled}</Badge>
            <Badge variant="default">{copy.notConnected}</Badge>
          </div>
          <p className="flex gap-2 text-sm text-secondary-text"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />{copy.safety}</p>
        </Card>

        {error && <div role="alert"><Card className="flex gap-2 border border-danger/30 text-danger">
          <AlertTriangle className="h-5 w-5 shrink-0" />{copy.unavailable}
        </Card></div>}

        {!error && (
          <div className="grid gap-4 md:grid-cols-3">
            {overview?.strategies.map((item) => {
              const details = STRATEGY_DETAILS[item.id];
              const Icon = details.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={selected === item.id}
                  onClick={() => {
                    scanRequestSeq.current += 1;
                    robinhoodRequestSeq.current += 1;
                    researchRequestSeq.current += 1;
                    orcaRequestSeq.current += 1;
                    quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
                    setOrcaReview(null);
                    setQuotePreview(null);
    setMarkPreview(null);
                    setQuoteLoading(false);
                    setQuoteError(false);
                    setQuoteInputError(false);
                    setOrcaError(false);
                    setOrcaLoading(false);
                    setResearchTarget(null);
                    setMintResearch(null);
                    setImpactResearch(null);
                    setConcentrationResearch(null);
                    setPoolResearch(null);
                    setOwnerGroupResearch(null);
                    setPoolResearchError(false);
                    setOwnerGroupResearchError(false);
                    setConcentrationError(false);
                    setResearchLoading(false);
                    setSelected(item.id);
                    setRobinhoodStatus(null);
                    setRobinhoodError(false);
                    setRobinhoodLoading(false);
                    setScanResult(null);
                    setScanError(false);
                    setScanLoading(false);
                  }}
                  className={`rounded-2xl border p-5 text-left transition-colors ${selected === item.id ? 'border-cyan/60 bg-card shadow-soft-card' : 'border-border/60 bg-card/65 hover:bg-hover'}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <Icon className={`h-6 w-6 ${details.accent}`} />
                    <Badge>{copy.notConnected}</Badge>
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-foreground">{name(item.id)}</h2>
                  <p className="mt-1 text-sm text-secondary-text">{description(item.id)}</p>
                  <p className="mt-3 text-xs text-secondary-text">{copy.data}: {item.engineConnected ? copy.ready : copy.pending}</p>
                </button>
              );
            })}
            {loading && !overview && <Card>{copy.pending}</Card>}
            {!loading && !overview && !error && <Card>{copy.noStrategies}</Card>}
          </div>
        )}

        {current && currentDetails && !error && (
          <Card title={`${copy.strategy} — ${name(current.id)}`} className="space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-xl bg-elevated/60 p-4">
                <Database className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.data}</p>
                <p className="mt-1 font-medium">{current.engineConnected ? copy.ready : copy.pending}</p>
              </div>
              <div className="rounded-xl bg-elevated/60 p-4">
                <Activity className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.paper}</p>
                <p className="mt-1 font-medium">{current.paperTradingEnabled ? copy.ready : copy.pending}</p>
              </div>
              <div className="rounded-xl bg-elevated/60 p-4">
                <Wallet className="mb-2 h-5 w-5 text-secondary-text" />
                <p className="text-xs text-secondary-text">{copy.execution}</p>
                <p className="mt-1 font-medium">{current.liveTradingEnabled ? copy.ready : copy.disabled}</p>
              </div>
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <section>
                <h3 className="font-semibold">{copy.sources}</h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-secondary-text">
                  {current.dataSources.map((source) => <li key={source}>{source}</li>)}
                </ul>
              </section>
              <section>
                <h3 className="font-semibold">{copy.checks}</h3>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-secondary-text">
                  {current.riskChecks.map((check) => <li key={check}>{RISK_LABELS[check]?.[language] ?? check}</li>)}
                </ul>
              </section>
            </div>
            {current.id === 'robinhood_chain' && current.agentModules && current.agentModules.length > 0 && (
              <section>
                <h3 className="mb-2 font-semibold">{copy.robinhoodAgents}</h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {current.agentModules.map((agent) => (
                    <div key={agent.id} className="flex items-center justify-between gap-2 rounded-lg bg-elevated/60 px-3 py-2 text-sm">
                      <span>{agent.name}</span><Badge>{copy.pending}</Badge>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </Card>
        )}

        {current && current.market === 'solana' && !error && (
          <Card className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">{copy.scanResults}</h3>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void scanCandidates()} disabled={scanLoading}>
                <Radar className="h-4 w-4" />{scanLoading ? copy.scanLoading : copy.scan}
              </button>
            </div>
            <p className="text-xs text-secondary-text">{copy.scanNote}</p>
            <label className="flex flex-wrap items-center gap-2 text-sm" htmlFor="meme-research-amount">
              {copy.inspectAmount}
              <select
                id="meme-research-amount"
                className="rounded-lg border border-border bg-card px-3 py-1.5"
                value={researchAmount}
                onChange={(event) => {
                  researchRequestSeq.current += 1;
                  orcaRequestSeq.current += 1;
                  quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
                  setOrcaReview(null);
                  setQuotePreview(null);
    setMarkPreview(null);
                  setQuoteLoading(false);
                  setQuoteError(false);
                  setQuoteInputError(false);
                  setOrcaLoading(false);
                  setOrcaError(false);
                  setResearchAmount(Number(event.target.value));
                  setResearchTarget(null);
                  setMintResearch(null);
                  setImpactResearch(null);
                  setConcentrationResearch(null);
                  setPoolResearch(null);
                  setOwnerGroupResearch(null);
                  setPoolResearchError(false);
                  setOwnerGroupResearchError(false);
                  setConcentrationError(false);
                  setResearchLoading(false);
                }}
              >
                <option value={25}>$25</option><option value={50}>$50</option><option value={100}>$100</option>
              </select>
            </label>
            {scanError && <p role="alert" className="text-sm text-danger">{copy.scanUnavailable}</p>}
            {scanResult?.status === 'disabled' && <p className="text-sm text-warning">{copy.scanDisabled}</p>}
            {scanResult?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.scanUnavailable}</p>}
            {scanResult?.status === 'ok' && (
              <>
                <p className="text-xs text-secondary-text">{copy.scanTimestamp}: {scanResult.observedAt ?? '—'} · GeckoTerminal</p>
                {scanResult.candidates.length === 0 ? (
                  <p className="text-sm text-secondary-text">{copy.scanEmpty}</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[720px] text-left text-xs">
                      <thead><tr className="border-b border-border/60 text-secondary-text">
                        <th className="p-2">Token</th><th className="p-2">{copy.scanScore}</th><th className="p-2">{copy.scanLiquidity}</th>
                        <th className="p-2">{copy.scanVolume}</th><th className="p-2">{copy.scanChange}</th>
                        <th className="p-2">{copy.scanAge}</th><th className="p-2">{copy.scanTrades}</th><th className="p-2">{copy.inspectTitle}</th>
                      </tr></thead>
                      <tbody>{scanResult.candidates.map((coin) => (
                        <tr key={coin.tokenAddress} className="border-b border-border/40">
                          <td className="p-2">
                            <span className="font-semibold">{coin.symbol}</span>
                            <span className="block font-mono text-[10px] text-secondary-text">{coin.tokenAddress.slice(0, 6)}…{coin.tokenAddress.slice(-5)}</span>
                            <span className="text-[10px] text-warning">{copy.scanUnverified}</span>
                          </td>
                          <td className="p-2">{coin.researchScore.toFixed(1)}</td>
                          <td className="p-2">{coin.liquidityUsd.toLocaleString()}</td>
                          <td className="p-2">{coin.volume5mUsd.toLocaleString()}</td>
                          <td className="p-2">{coin.change5mPct.toFixed(2)}%</td>
                          <td className="p-2">{coin.ageMinutes.toFixed(0)}</td>
                          <td className="p-2">{coin.buys5m} / {coin.sells5m}</td>
                          <td className="p-2">
                            <button type="button" className="btn-secondary whitespace-nowrap px-2 py-1 text-xs" onClick={() => void inspectSolanaCandidate(coin.tokenAddress, coin.symbol, coin.poolAddress, coin.liquidityUsd)}>
                              {copy.inspect}
                            </button>
                          </td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                )}
              </>
            )}
            {researchTarget && (
              <div className="space-y-3 border-t border-border/50 pt-3" aria-label={copy.inspectTitle}>
                <h4 className="font-semibold">{copy.inspectTitle}: {researchTarget.symbol}</h4>
                <p className="break-all font-mono text-xs text-secondary-text">{researchTarget.mint}</p>
                {researchLoading && <p className="text-sm text-secondary-text">{copy.inspectLoading}</p>}
                {(mintResearchError || impactResearchError || concentrationError || poolResearchError || ownerGroupResearchError) && <p role="alert" className="text-sm text-danger">{copy.inspectFailed}</p>}
                {mintResearch?.status === 'disabled' && <p className="text-sm text-warning">{copy.mintDisabled}</p>}
                {mintResearch && ['unavailable','unsupported'].includes(mintResearch.status) && <p className="text-sm text-danger">{copy.mintUnavailable}</p>}
                {mintResearch?.status === 'screened' && (
                  <div className="space-y-2">
                    <p className="text-sm">{mintResearch.verdict === 'blocked' ? copy.mintBlocked : copy.mintReviewOnly}</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <p className="text-sm">{copy.mintAuthority}: {mintResearch.mintAuthorityRevoked === null ? copy.authorityUnknown : mintResearch.mintAuthorityRevoked ? copy.authorityRevoked : copy.authorityActive}</p>
                      <p className="text-sm">{copy.freezeAuthority}: {mintResearch.freezeAuthorityRevoked === null ? copy.authorityUnknown : mintResearch.freezeAuthorityRevoked ? copy.authorityRevoked : copy.authorityActive}</p>
                    </div>
                    {mintResearch.blockingReasons.length > 0 && <p className="text-xs text-danger">{mintResearch.blockingReasons.join(', ')}</p>}
                  </div>
                )}
                {impactResearch && (
                  <div className="space-y-2 rounded-xl bg-elevated/60 p-3">
                    <h5 className="font-semibold">{copy.impactTitle}</h5>
                    <p className="text-xs text-secondary-text">{copy.impactWarning}</p>
                    <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                      <p>{copy.impactPct}: {impactResearch.modeledPriceImpactPct.toFixed(2)}%</p>
                      <p>{copy.costPct}: {impactResearch.modeledTotalCostPct.toFixed(2)}%</p>
                      <p>{copy.feeUsd}: ${impactResearch.modeledFeeUsd.toFixed(4)}</p>
                      <p>{copy.worstUsd}: ${impactResearch.modeledMinOutputValueUsd.toFixed(2)}</p>
                    </div>
                    {impactResearch.paperReviewStatus === 'blocked' && <p className="text-sm text-danger">{copy.impactBlocked}</p>}
                  </div>
                )}
                {concentrationResearch && (
                  <div className="space-y-2 rounded-xl bg-elevated/60 p-3">
                    <h5 className="font-semibold">{copy.concentrationTitle}</h5>
                    <p className="text-xs text-secondary-text">{copy.concentrationDisclaimer}</p>
                    {concentrationResearch.status === 'disabled' && <p className="text-sm text-warning">{copy.concentrationDisabled}</p>}
                    {concentrationResearch.status === 'unavailable' && <p className="text-sm text-danger">{copy.concentrationUnavailable}</p>}
                    {concentrationResearch.status === 'screened' && (
                      <>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>{copy.concentrationTop1}: {concentrationResearch.topAccountPct?.toFixed(2) ?? '—'}%</div>
                          <div>{copy.concentrationTop10}: {concentrationResearch.topTenAccountsPct?.toFixed(2) ?? '—'}%</div>
                        </div>
                        <p className="text-xs text-secondary-text">{copy.concentrationNote}</p>
                        <p className={`text-sm ${concentrationResearch.verdict === 'concentration_signal' ? 'text-danger' : 'text-warning'}`}>
                          {concentrationResearch.verdict === 'concentration_signal' ? copy.concentrationSignal : copy.concentrationNoSignal}
                        </p>
                      </>
                    )}
                  </div>
                )}
                {poolResearch && (
                  <div className="space-y-2 rounded-xl bg-elevated/60 p-3">
                    <h5 className="font-semibold">{copy.poolTitle}</h5>
                    <p className="text-xs text-secondary-text">{copy.poolDisclaimer}</p>
                    {poolResearch.status === 'disabled' && <p className="text-sm text-warning">{copy.poolDisabled}</p>}
                    {poolResearch.status === 'unavailable' && <p className="text-sm text-danger">{copy.poolUnavailable}</p>}
                    {poolResearch.status === 'screened' && (
                      <>
                        <p className="text-sm">GeckoTerminal: {poolResearch.geckoterminalUsd?.toLocaleString()} USD · DEX Screener: {poolResearch.dexscreenerUsd?.toLocaleString()} USD</p>
                        <p className="text-sm">{copy.sourceDifference}: {poolResearch.differencePct?.toFixed(2)}%</p>
                        <p className="break-all text-xs text-secondary-text">{copy.poolAccountOwner}: {poolResearch.onchainOwnerProgram ?? '—'}</p>
                        <p className="text-sm text-warning">{poolResearch.verdict === 'blocked' ? copy.poolBlocked : copy.poolReviewOnly}</p>
                        {poolResearch.flags.length > 0 && <p className="text-xs text-danger">{poolResearch.flags.join(', ')}</p>}
                      </>
                    )}
                  </div>
                )}
                {ownerGroupResearch && (
                  <div className="space-y-2 rounded-xl bg-elevated/60 p-3">
                    <h5 className="font-semibold">{copy.groupTitle}</h5>
                    <p className="text-xs text-secondary-text">{copy.groupDisclaimer}</p>
                    {ownerGroupResearch.status === 'disabled' && <p className="text-sm text-warning">{copy.groupDisabled}</p>}
                    {ownerGroupResearch.status === 'unavailable' && <p className="text-sm text-danger">{copy.groupUnavailable}</p>}
                    {ownerGroupResearch.status === 'screened' && (
                      <>
                        <p className="text-sm">{copy.topGroup}: {ownerGroupResearch.largestObservedOwnerSharePct?.toFixed(2)}%</p>
                        <p className={`text-sm ${ownerGroupResearch.verdict === 'concentration_signal' ? 'text-danger' : 'text-warning'}`}>
                          {ownerGroupResearch.verdict === 'concentration_signal' ? copy.groupWarning : copy.groupReviewOnly}
                        </p>
                        {ownerGroupResearch.ownerGroups.slice(0, 5).map((group) => (
                          <p className="break-all font-mono text-xs text-secondary-text" key={group.ownerAddress}>
                            {group.ownerAddress.slice(0, 6)}…{group.ownerAddress.slice(-5)} · {group.sampledTokenAccounts} · {group.shareOfTotalSupplyPct.toFixed(2)}%
                          </p>
                        ))}
                      </>
                    )}
                  </div>
                )}
                <div className="space-y-3 rounded-xl bg-elevated/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h5 className="font-semibold">{copy.orcaTitle}</h5>
                    <button type="button" className="btn-secondary" disabled={orcaLoading} onClick={() => void inspectOrcaVaults(researchTarget.mint, researchTarget.pool)}>
                      {orcaLoading ? copy.orcaLoading : copy.orcaButton}
                    </button>
                  </div>
                  <p className="text-xs text-secondary-text">{copy.orcaNotes}</p>
                  {orcaError && <p role="alert" className="text-sm text-danger">{copy.orcaUnavailable}</p>}
                  {orcaReview?.status === 'disabled' && <p className="text-sm text-warning">{copy.orcaDisabled}</p>}
                  {orcaReview?.status === 'unsupported' && <p className="text-sm text-warning">{copy.orcaUnsupported}</p>}
                  {orcaReview?.status === 'unavailable' && <p className="text-sm text-danger">{copy.orcaUnavailable}</p>}
                  {orcaReview?.status === 'screened' && (
                    <>
                      <p className={`text-sm ${orcaReview.verdict === 'blocked' ? 'text-danger' : 'text-warning'}`}>
                        {orcaReview.verdict === 'blocked' ? copy.orcaBlocked : copy.orcaScreened}
                      </p>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <p className="break-all font-mono text-xs">{copy.orcaVaultA}: {orcaReview.vaultARawAmount ?? '—'}</p>
                        <p className="break-all font-mono text-xs">{copy.orcaVaultB}: {orcaReview.vaultBRawAmount ?? '—'}</p>
                      </div>
                      {orcaReview.warnings.length > 0 && <p className="text-xs text-danger">{orcaReview.warnings.join(', ')}</p>}
                    </>
                  )}
                </div>
                <div className="space-y-3 rounded-xl bg-elevated/60 p-3">
                  <h5 className="font-semibold">{copy.jupTitle}</h5>
                  <p className="text-xs text-secondary-text">{copy.jupDescription}</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <label htmlFor="jupiter-quote-side" className="text-xs">{copy.jupTitle}</label>
                    <select id="jupiter-quote-side" className="rounded-lg border border-border bg-card px-2 py-1.5 text-sm"
                      value={quoteSide}
                      onChange={(e) => {
                        quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
                        setQuoteSide(e.target.value as 'buy' | 'sell');
                        setQuotePreview(null);
    setMarkPreview(null);
                        setQuoteError(false);
                        setQuoteInputError(false);
                        setQuoteLoading(false);
                      }}>
                      <option value="buy">{copy.jupBuy}</option>
                      <option value="sell">{copy.jupSell}</option>
                    </select>
                    {quoteSide === 'sell' ? (
                      <label className="text-xs">{copy.jupSellRaw}
                        <input type="text" inputMode="numeric" className="ml-2 rounded-lg border border-border bg-card px-2 py-1.5 text-sm"
                          value={sellRawAmount}
                          onChange={(e) => {
                            quoteRequestSeq.current += 1;
    markRequestSeq.current += 1;
                            setSellRawAmount(e.target.value);
                            setQuotePreview(null);
    setMarkPreview(null);
                            setQuoteLoading(false);
                            setQuoteError(false);
                            setQuoteInputError(false);
                          }}/>
                      </label>
                    ) : <span className="text-xs text-secondary-text">{researchAmount} USDC</span>}
                    <button type="button" className="btn-secondary" disabled={quoteLoading} onClick={() => void inspectJupiterQuote()}>
                      {quoteLoading ? copy.jupLoading : copy.jupPreview}
                    </button>
                  </div>
                  {quoteInputError && <p role="alert" className="text-sm text-danger">{copy.jupInvalidInput}</p>}
                  {quoteError && <p role="alert" className="text-sm text-danger">{copy.jupUnavailable}</p>}
                  {quotePreview?.status === 'disabled' && <p className="text-sm text-warning">{copy.jupDisabled}</p>}
                  {quotePreview?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.jupUnavailable}</p>}
                  {quotePreview?.status === 'rate_limited' && <p className="text-sm text-warning">{copy.jupCooldown}</p>}
                  {quotePreview?.status === 'ok' && quotePreview.quote && (
                    <div className="space-y-2">
                      <div className="grid gap-2 text-sm sm:grid-cols-2">
                        <p className="break-all">{copy.jupInput}: {quotePreview.quote.amountInRaw}</p>
                        <p className="break-all">{copy.jupOutput}: {quotePreview.quote.amountOutRaw}</p>
                        <p>{copy.jupRouter}: {quotePreview.quote.router}</p>
                        <p>{copy.jupFee}: {quotePreview.quote.feeBps}</p>
                      </div>
                      <p className="text-xs text-secondary-text">{copy.jupCaptured}: {quotePreview.quote.capturedAt}</p>
                      <p className="text-xs text-warning">{copy.jupNoExecution}</p>
                      <details>
                        <summary className="cursor-pointer text-xs font-semibold">{copy.jupRaw}</summary>
                        <p className="my-2 text-xs text-secondary-text">{copy.jupCopy}</p>
                        <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-md bg-card p-2 text-xs">{JSON.stringify(toOfflineQuoteCapture(quotePreview.quote), null, 2)}</pre>
                      </details>
                    </div>
                  )}
                </div>
                <div className="space-y-3 rounded-xl bg-elevated/60 p-3">
                  <h5 className="font-semibold">{copy.markTitle}</h5>
                  <p className="text-xs text-secondary-text">{copy.markDesc}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <label htmlFor="dual-source-sell-raw" className="text-xs">{copy.jupSellRaw}</label>
                    <input id="dual-source-sell-raw" type="text" inputMode="numeric"
                      className="w-40 rounded-lg border border-border bg-card px-2 py-1.5 text-sm"
                      value={sellRawAmount}
                      onChange={(event) => {
                        markRequestSeq.current += 1;
                        setSellRawAmount(event.target.value);
                        setMarkPreview(null);
                        setMarkError(false);
                        setMarkInputError(false);
                      }} />
                    <button type="button" className="btn-secondary" disabled={markLoading}
                      onClick={() => void inspectDualSourceMark()}>
                      {markLoading ? copy.markLoading : copy.markButton}
                    </button>
                  </div>
                  {markInputError && <p role="alert" className="text-sm text-danger">{copy.markBadAmount}</p>}
                  {markError && <p role="alert" className="text-sm text-danger">{copy.markUnavailable}</p>}
                  {markPreview?.status === 'disabled' && <p className="text-sm text-warning">{copy.markDisabled}</p>}
                  {markPreview?.status === 'prerequisite_disabled' && <p className="text-sm text-warning">{copy.markNeedsJupiter}</p>}
                  {markPreview?.status === 'rate_limited' && <p className="text-sm text-warning">{copy.markRateLimited}</p>}
                  {markPreview?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.markUnavailable}</p>}
                  {markPreview?.status === 'screened' && (
                    <div className="space-y-2 text-sm">
                      <p>{copy.markJupPrice}: {markPreview.jupiterPriceUsd}</p>
                      <p>{copy.markDexPrice}: {markPreview.dexscreenerPriceUsd}</p>
                      <p>{copy.markSpread}: {markPreview.priceDivergencePct}%</p>
                      <p className="text-xs text-warning">
                        {markPreview.verdict === 'flagged' ? copy.markFlagged : copy.markCompared}
                      </p>
                      {markPreview.warningFlags.length > 0 && <p className="break-all text-xs text-danger">{markPreview.warningFlags.join(', ')}</p>}
                      <p className="text-xs text-secondary-text">{copy.markRiskNote}</p>
                    </div>
                  )}
                </div>
                <p className="text-xs text-warning">{copy.unknownSafety}</p>
              </div>
            )}
          </Card>
        )}

        {current?.id === 'robinhood_chain' && !error && (
          <Card className="space-y-4" title={copy.robinhoodRpc}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-secondary-text">{copy.robinhoodWarning}</p>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void checkRobinhood()} disabled={robinhoodLoading}>
                <RefreshCw className={`h-4 w-4 ${robinhoodLoading ? 'animate-spin' : ''}`} />
                {robinhoodLoading ? copy.robinhoodChecking : copy.robinhoodProbe}
              </button>
            </div>
            {robinhoodError && <p role="alert" className="text-sm text-danger">{copy.robinhoodUnavailable}</p>}
            {robinhoodStatus?.status === 'disabled' && <p className="text-sm text-warning">{copy.robinhoodDisabled}</p>}
            {robinhoodStatus?.status === 'unavailable' && <p role="alert" className="text-sm text-danger">{copy.robinhoodUnavailable}</p>}
            {robinhoodStatus?.status === 'mismatch' && <p role="alert" className="text-sm text-danger">{copy.robinhoodMismatch}</p>}
            {robinhoodStatus?.status === 'ok' && (
              <>
                <Badge variant="success">{copy.robinhoodHealthy}</Badge>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div><p className="text-secondary-text">{copy.robinhoodNetwork}</p><p>{robinhoodStatus.network}</p></div>
                  <div><p className="text-secondary-text">{copy.robinhoodChainId}</p><p>{robinhoodStatus.chainIdSeen}</p></div>
                  <div><p className="text-secondary-text">{copy.robinhoodBlock}</p><p>{robinhoodStatus.blockNumber?.toLocaleString() ?? '—'}</p></div>
                </div>
                <p className="text-xs text-secondary-text">{robinhoodStatus.checkedAt}</p>
              </>
            )}
          </Card>
        )}

        <Card title={copy.paperStatusTitle} className="space-y-3">
          <p className="text-sm text-secondary-text">{copy.paperUnlinked}</p>
          {paperStatusError && <p role="alert" className="text-sm text-danger">{copy.paperNotAvailable}</p>}
          {paperStatus && (
            <>
              <Badge variant="warning">{copy.paperOfflineReady}</Badge>
              <div className="grid gap-3 sm:grid-cols-2">
                {paperStatus.strategyLedgers.map((ledger) => (
                  <div className="rounded-lg border border-border/50 p-3" key={ledger.strategy}>
                    <p className="font-semibold">{ledger.strategy === 'new_launch' ? copy.paperLedgerNew : copy.paperLedgerMomentum}</p>
                    <p className="text-sm text-secondary-text">{copy.paperNotRunning}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card title={copy.safetyTitle} className="space-y-3">
          {riskReadinessError && <p role="alert" className="text-sm text-danger">{copy.safetyUnavailable}</p>}
          {riskReadiness && (
            <>
              <p className="text-sm font-medium text-warning">{copy.safetyOffline}</p>
              <p className="text-xs text-secondary-text">{copy.safetyJournal}</p>
              <p className="text-xs text-secondary-text">{copy.safetyGuard}</p>
              <p className="text-xs text-secondary-text">{copy.safetyLimits}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {riskReadiness.strategyLedgers.map((item) => (
                  <div className="rounded-lg border border-border/50 p-3" key={item.strategy}>
                    <p className="font-semibold">{item.strategy === 'new_launch' ? copy.paperLedgerNew : copy.paperLedgerMomentum}</p>
                    <p className="text-xs text-secondary-text">{copy.safetyNotRunning}</p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-warning">{copy.safetyDisclaimer}</p>
            </>
          )}
        </Card>

        <Card title={copy.mtmTitle} className="space-y-3">
          {mtmReadinessError && <p role="alert" className="text-sm text-danger">{copy.mtmUnavailable}</p>}
          {mtmReadiness && (
            <>
              <Badge variant="warning">{copy.mtmReady}</Badge>
              <p className="text-sm text-secondary-text">{copy.mtmNotRunning}</p>
              <p className="text-xs text-secondary-text">{copy.mtmAssumptions}</p>
              <p className="text-xs text-secondary-text">{copy.mtmRisk}</p>
              <p className="text-xs text-secondary-text">{copy.mtmRecovery}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {mtmReadiness.strategies.map((entry) => (
                  <div className="rounded-lg border border-border/50 p-3" key={entry.strategy}>
                    <p className="font-semibold">{entry.strategy === 'new_launch' ? copy.paperLedgerNew : copy.paperLedgerMomentum}</p>
                    <p className="text-xs text-secondary-text">{copy.mtmLedgerInactive}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <Card title={copy.performance}>
            <p className="text-sm text-secondary-text">{copy.noResults}</p>
          </Card>
          <Card title={copy.next}>
            <p className="text-sm text-secondary-text">{copy.nextInfo}</p>
          </Card>
        </div>
      </div>
    </AppPage>
  );
}
