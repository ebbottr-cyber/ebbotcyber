import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { UiLanguageToggle } from '../../components/i18n/UiLanguageToggle';
import { UiLanguageProvider, useUiLanguage } from '../../contexts/UiLanguageContext';
import {
  getRuntimeInitialLanguage,
  normalizeUiLanguage,
  persistUiLanguage,
  resolveInitialUiLanguage,
  UI_LANGUAGE_STORAGE_KEY,
} from '../uiLanguage';

const OperatorDisplay = () => {
  const { language, setLanguage, t } = useUiLanguage();
  return (
    <>
      <output data-testid="operator-language">{language}</output>
      <output data-testid="operator-home">{t('layout.nav.home')}</output>
      <button type="button" onClick={() => setLanguage('zh')}>Eski Çince isteği</button>
      <button type="button" onClick={() => setLanguage('en')}>Eski İngilizce isteği</button>
    </>
  );
};

beforeEach(() => {
  window.localStorage.clear();
});

describe('EBBot Turkish-only user interface', () => {
  it('migrates old saved Chinese/English languages and ignores browser locale', () => {
    expect(normalizeUiLanguage('zh')).toBe('tr');
    expect(normalizeUiLanguage('en')).toBe('tr');
    expect(normalizeUiLanguage('tr')).toBe('tr');
    expect(normalizeUiLanguage('unknown')).toBeNull();
    for (const saved of ['zh', 'en', 'tr']) {
      window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, saved);
      expect(resolveInitialUiLanguage({
        storage: window.localStorage,
        navigatorLike: { language: 'zh-CN', languages: ['zh-CN', 'en-US'] },
      })).toBe('tr');
      expect(getRuntimeInitialLanguage()).toBe('tr');
    }
    window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
    expect(resolveInitialUiLanguage({ storage: null })).toBe('tr');
    persistUiLanguage(window.localStorage, 'zh');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('tr');
    persistUiLanguage(window.localStorage, 'en');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('tr');
  });

  it('never renders Chinese or English after legacy saved language or setLanguage calls', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    render(
      <UiLanguageProvider>
        <OperatorDisplay />
        <UiLanguageToggle />
      </UiLanguageProvider>,
    );
    expect(screen.getByTestId('operator-language')).toHaveTextContent('tr');
    expect(screen.getByTestId('operator-home')).toHaveTextContent('Ana Sayfa');
    expect(screen.getByRole('status', { name: 'Arayüz dili: Türkçe' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /dil/i })).not.toBeInTheDocument();
    expect(screen.queryByText('中文')).not.toBeInTheDocument();
    await waitFor(() => expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('tr'));
    expect(document.documentElement.lang).toBe('tr');
    fireEvent.click(screen.getByRole('button', { name: 'Eski Çince isteği' }));
    expect(screen.getByTestId('operator-language')).toHaveTextContent('tr');
    fireEvent.click(screen.getByRole('button', { name: 'Eski İngilizce isteği' }));
    expect(screen.getByTestId('operator-language')).toHaveTextContent('tr');
    expect(window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('tr');
  });
});
