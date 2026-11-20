import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  UiLanguageProvider,
  useUiLanguage,
} from '../UiLanguageContext';
import {
  getRuntimeInitialLanguage,
  persistUiLanguage,
  resolveInitialUiLanguage,
  UI_LANGUAGE_STORAGE_KEY,
} from '../../utils/uiLanguage';
import { UiLanguageToggle } from '../../components/i18n/UiLanguageToggle';

function createStorage(value: string | null): Storage {
  const store = new Map<string, string>();
  if (value !== null) {
    store.set(UI_LANGUAGE_STORAGE_KEY, value);
  }

  return {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, nextValue: string) => {
      store.set(key, nextValue);
    },
  };
}

function BareContextLanguage() {
  const { language, t } = useUiLanguage();
  return (
    <>
      <span data-testid="bare-context-language">{language}</span>
      <span data-testid="bare-context-label">{t('language.toggle')}</span>
    </>
  );
}

describe('UiLanguageContext', () => {
  it('keeps no-provider legacy test fixtures in the original Chinese language', () => {
    vi.stubEnv('VITE_EBBOT_TURKISH_TEST_MODE', 'false');
    try {
      render(<BareContextLanguage />);
      expect(screen.getByTestId('bare-context-language')).toHaveTextContent('zh');
      expect(screen.getByTestId('bare-context-label')).toHaveTextContent('切换界面语言');
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it('keeps no-provider production UI locked to Turkish', () => {
    vi.stubEnv('VITE_EBBOT_TURKISH_TEST_MODE', 'true');
    try {
      render(<BareContextLanguage />);
      expect(screen.getByTestId('bare-context-language')).toHaveTextContent('tr');
      expect(screen.getByTestId('bare-context-label')).toHaveTextContent('Arayüz dilini değiştir');
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it('resolves explicit storage choice before browser language', () => {
    expect(resolveInitialUiLanguage({
      storage: createStorage('zh'),
      navigatorLike: { language: 'en-US', languages: ['en-US'] },
    })).toBe('zh');

    expect(resolveInitialUiLanguage({
      storage: createStorage('en'),
      navigatorLike: { language: 'zh-CN', languages: ['zh-CN'] },
    })).toBe('en');
  });

  it('falls back from invalid storage to the first supported browser language and then zh', () => {
    expect(resolveInitialUiLanguage({
      storage: createStorage('fr'),
      navigatorLike: { language: 'en-US', languages: ['en-US'] },
    })).toBe('en');

    expect(resolveInitialUiLanguage({
      storage: createStorage('fr'),
      navigatorLike: { language: 'zh-CN', languages: ['zh-CN', 'en-US'] },
    })).toBe('zh');

    expect(resolveInitialUiLanguage({
      storage: createStorage(null),
      navigatorLike: { language: 'tr-TR', languages: ['tr-TR'] },
    })).toBe('zh');
  });

  it('falls back to browser language if storage getItem throws', () => {
    const throwingStorage = createStorage('en');
    throwingStorage.getItem = () => {
      throw new Error('Storage getItem disabled');
    };

    expect(resolveInitialUiLanguage({
      storage: throwingStorage,
      navigatorLike: { language: 'en-US', languages: ['en-US'] },
    })).toBe('en');
  });

  it('persists language preference via storage in a safe, non-throwing path', () => {
    const throwingStorage = createStorage('zh');
    throwingStorage.setItem = () => {
      throw new Error('Storage setItem disabled');
    };

    expect(() => persistUiLanguage(throwingStorage, 'en')).not.toThrow();
  });

  it('falls back safely when the localStorage accessor itself throws', () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(window, 'localStorage');
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get: () => {
        throw new Error('localStorage disabled');
      },
    });

    try {
      expect(getRuntimeInitialLanguage()).toBe('zh');
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window, 'localStorage', originalDescriptor);
      }
    }
  });

  it('switches UI language immediately and persists the explicit choice', () => {
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');

    render(
      <UiLanguageProvider>
        <UiLanguageToggle />
      </UiLanguageProvider>
    );

    const toggle = screen.getByRole('button', { name: '切换界面语言' });
    expect(screen.getByText('中文')).toBeInTheDocument();

    fireEvent.click(toggle);

    expect(localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)).toBe('tr');
    expect(screen.getByRole('button', { name: 'Arayüz dilini değiştir' })).toBeInTheDocument();
    expect(screen.getByText('Türkçe')).toBeInTheDocument();
  });
});
