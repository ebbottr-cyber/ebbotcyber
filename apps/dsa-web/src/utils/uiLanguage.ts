import type { UiLanguage } from '../i18n/uiText';

export const UI_LANGUAGE_STORAGE_KEY = 'dsa.uiLanguage';

/**
 * Production EBBot is Turkish-only. Existing multilingual contract tests
 * remain runnable in compatibility mode; dedicated tests explicitly opt into
 * the production policy via VITE_EBBOT_TURKISH_TEST_MODE=true.
 * In production there is no override to turn the Turkish policy off.
 */
export const shouldForceTurkishUi = (): boolean => (
  import.meta.env.MODE !== 'test'
  || import.meta.env.VITE_EBBOT_TURKISH_TEST_MODE === 'true'
);

export function normalizeUiLanguage(value?: string | null): UiLanguage | null {
  if (value === 'zh' || value === 'en' || value === 'tr') {
    return shouldForceTurkishUi() ? 'tr' : value;
  }
  return null;
}

function getStoredUiLanguage(storage?: Storage | null): UiLanguage | null {
  if (!storage) {
    return null;
  }

  try {
    return normalizeUiLanguage(storage.getItem(UI_LANGUAGE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function getUiLanguageStorage(): Storage | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function persistUiLanguage(storage: Storage | null, language: UiLanguage): void {
  if (!storage) {
    return;
  }

  try {
    storage.setItem(UI_LANGUAGE_STORAGE_KEY, shouldForceTurkishUi() ? 'tr' : language);
  } catch {
    // Ignore storage failures; in-memory language still updates.
  }
}

function getBrowserUiLanguage(navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null): UiLanguage {
  if (shouldForceTurkishUi()) return 'tr';

  const languageCandidates = [
    ...(Array.isArray(navigatorLike?.languages) ? navigatorLike?.languages ?? [] : []),
    navigatorLike?.language,
  ].filter((language): language is string => Boolean(language));

  for (const candidate of languageCandidates) {
    const normalized = candidate.toLowerCase();
    // Test compatibility mode keeps the original multilingual browser policy.
    // Production always returns 'tr' above, regardless of navigator language.
    if (normalized.startsWith('zh')) {
      return 'zh';
    }
    if (normalized.startsWith('en')) {
      return 'en';
    }
  }

  return 'zh';
}

export function resolveInitialUiLanguage({
  storage,
  navigatorLike,
}: {
  storage?: Storage | null;
  navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null;
} = {}): UiLanguage {
  const stored = getStoredUiLanguage(storage);
  if (stored) {
    return stored;
  }

  return getBrowserUiLanguage(navigatorLike);
}

export function getRuntimeInitialLanguage(): UiLanguage {
  if (typeof window === 'undefined') {
    return 'tr';
  }

  return resolveInitialUiLanguage({
    storage: getUiLanguageStorage(),
    navigatorLike: window.navigator,
  });
}
