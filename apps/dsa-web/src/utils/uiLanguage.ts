import type { UiLanguage } from '../i18n/uiText';

/** Keep legacy translation tables for compatibility, but ship a Turkish-only user interface. */
export const UI_LANGUAGE_STORAGE_KEY = 'dsa.uiLanguage';

export function normalizeUiLanguage(value?: string | null): UiLanguage | null {
  if (value === 'tr' || value === 'zh' || value === 'en') {
    // Previously selected English or Chinese must never leak back into the operator UI.
    return 'tr';
  }
  return null;
}

function getStoredUiLanguage(storage?: Storage | null): UiLanguage | null {
  if (!storage) return null;
  try {
    return normalizeUiLanguage(storage.getItem(UI_LANGUAGE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function getUiLanguageStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function persistUiLanguage(storage: Storage | null, language: UiLanguage): void {
  if (!storage) return;
  try {
    storage.setItem(UI_LANGUAGE_STORAGE_KEY, normalizeUiLanguage(language) ?? 'tr');
  } catch {
    // In-memory Turkish UI continues even if localStorage is unavailable.
  }
}

export function resolveInitialUiLanguage({
  storage,
}: {
  storage?: Storage | null;
  // Kept in the public signature for existing callers; browser preference is ignored.
  navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null;
} = {}): UiLanguage {
  return getStoredUiLanguage(storage) ?? 'tr';
}

export function getRuntimeInitialLanguage(): UiLanguage {
  if (typeof window === 'undefined') return 'tr';
  return resolveInitialUiLanguage({
    storage: getUiLanguageStorage(),
    navigatorLike: window.navigator,
  });
}
