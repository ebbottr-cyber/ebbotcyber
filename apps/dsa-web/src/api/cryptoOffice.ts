import apiClient from './index';

/** This endpoint is read-only and never supplies exchange credentials or order methods. */
export type CryptoOfficeDashboard = {
  schema_version: '1.1';
  generated_at: string;
  mode: 'paper_only';
  application: { name?: string; version?: string };
  safety: { real_exchange_orders: false; live_trading_enabled: false };
  portfolio: Record<string, unknown>;
  risk: Record<string, unknown>;
  performance: Record<string, unknown>;
  validation: Record<string, unknown>;
  agents: Record<string, unknown>;
  strategies: Record<string, unknown>;
  operations: Record<string, unknown>;
};

export class CryptoOfficeContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CryptoOfficeContractError';
  }
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function validateCryptoOfficeDashboard(input: unknown): CryptoOfficeDashboard {
  if (!isObject(input) || input.schema_version !== '1.1' || input.mode !== 'paper_only' ||
      !isObject(input.safety) || input.safety.real_exchange_orders !== false ||
      input.safety.live_trading_enabled !== false) {
    throw new CryptoOfficeContractError('Kripto servisinin güvenlik sözleşmesi geçersiz.');
  }
  const sections = [
    'application', 'portfolio', 'risk', 'performance', 'validation',
    'agents', 'strategies', 'operations',
  ] as const;
  if (sections.some(section => !isObject(input[section]))) {
    throw new CryptoOfficeContractError('Kripto servisinin beklenen veri alanları eksik.');
  }
  if (typeof input.generated_at !== 'string') {
    throw new CryptoOfficeContractError('Veri güncelleme zamanı geçersiz.');
  }
  const timestamp = Date.parse(input.generated_at);
  const age = Date.now() - timestamp;
  if (!Number.isFinite(timestamp) || age > 24 * 60 * 60 * 1000 || age < -5 * 60 * 1000) {
    throw new CryptoOfficeContractError('Kripto servisinden gelen veri eski veya geçersiz.');
  }
  const portfolio = input.portfolio;
  if (!isObject(portfolio)) {
    throw new CryptoOfficeContractError('Kripto portföy verisi eksik.');
  }
  const combined = portfolio.combined;
  if (!isObject(combined) || typeof combined.valuation_complete !== 'boolean') {
    throw new CryptoOfficeContractError('Kripto portföy değerleme durumu geçersiz.');
  }
  const equity = combined.equity;
  if (combined.valuation_complete) {
    if (typeof equity !== 'number' || !Number.isFinite(equity) || equity < 0) {
      throw new CryptoOfficeContractError('Kripto özsermaye verisi geçersiz.');
    }
  } else if (equity !== null) {
    throw new CryptoOfficeContractError('Eksik fiyatlı portföy sıfır olarak gösterilemez.');
  }
  return input as unknown as CryptoOfficeDashboard;
}

export const cryptoOfficeApi = {
  async dashboard(): Promise<CryptoOfficeDashboard> {
    const response = await apiClient.get<unknown>('/api/v1/crypto-office/dashboard');
    return validateCryptoOfficeDashboard(response.data);
  },
};
