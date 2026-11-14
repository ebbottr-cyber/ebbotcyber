import { describe, expect, it } from 'vitest';

import { getReportText, normalizeReportLanguage } from '../reportLanguage';
import { getSentimentLabel } from '../../types/analysis';

describe('reportLanguage ko support', () => {
  it('normalizes ko and falls back to zh for unknown', () => {
    expect(normalizeReportLanguage('ko')).toBe('ko');
    expect(normalizeReportLanguage('en')).toBe('en');
    expect(normalizeReportLanguage('fr')).toBe('zh');
    expect(normalizeReportLanguage(undefined)).toBe('zh');
  });

  it('returns Korean report copy for ko', () => {
    const ko = getReportText('ko');
    expect(ko.keyInsights).toBe('핵심 인사이트');
    expect(ko.actionAdvice).toBe('대응 전략');
    expect(ko.fullReport).toBe('전체 분석 리포트');
  });

  it('keeps zh/en report copy unchanged', () => {
    expect(getReportText('zh').keyInsights).toBe('核心洞察');
    expect(getReportText('en').keyInsights).toBe('KEY INSIGHTS');
  });

  it('returns Korean sentiment labels by band', () => {
    expect(getSentimentLabel(90, 'ko')).toBe('매우 낙관');
    expect(getSentimentLabel(50, 'ko')).toBe('중립');
    expect(getSentimentLabel(10, 'ko')).toBe('매우 비관');
    expect(getSentimentLabel(90, 'en')).toBe('Very Bullish');
  });
});

describe('reportLanguage tr support', () => {
  it('preserves tr rather than falling back to zh', () => {
    expect(normalizeReportLanguage('tr')).toBe('tr');
    expect(normalizeReportLanguage('en')).toBe('en');
    expect(normalizeReportLanguage('ko')).toBe('ko');
    expect(normalizeReportLanguage('unrecognized')).toBe('zh');
  });

  it('renders Turkish report headings without changing JSON keys', () => {
    const tr = getReportText('tr');
    expect(tr.keyInsights).toBe('Temel Bulgular');
    expect(tr.actionAdvice).toBe('İşlem Önerisi');
    expect(tr.stopLoss).toBe('Zarar Durdur');
    expect(tr.fullReport).toBe('Ayrıntılı Analiz Raporu');
  });

  it('returns Turkish sentiment labels for all five bands', () => {
    expect(getSentimentLabel(10, 'tr')).toBe('Çok Olumsuz');
    expect(getSentimentLabel(30, 'tr')).toBe('Olumsuz');
    expect(getSentimentLabel(50, 'tr')).toBe('Nötr');
    expect(getSentimentLabel(70, 'tr')).toBe('Olumlu');
    expect(getSentimentLabel(90, 'tr')).toBe('Çok Olumlu');
    // Match backend get_sentiment_label thresholds (20/40/60/80 included in higher band).
    expect(getSentimentLabel(20, 'tr')).toBe('Olumsuz');
    expect(getSentimentLabel(40, 'tr')).toBe('Nötr');
    expect(getSentimentLabel(60, 'tr')).toBe('Olumlu');
    expect(getSentimentLabel(80, 'tr')).toBe('Çok Olumlu');
  });
});
