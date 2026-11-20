import type React from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { formatUiText, UI_TEXT, type UiLanguage, type UiTextKey, type UiTextParams } from '../i18n/uiText';
import { getRuntimeInitialLanguage, getUiLanguageStorage, persistUiLanguage, shouldForceTurkishUi } from '../utils/uiLanguage';

type UiLanguageContextValue = {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
  t: (key: UiTextKey, params?: UiTextParams) => string;
};

// A bare component tree has no provider. In production the fallback is always
// Turkish; in Vitest compatibility mode it must match the old Chinese-default
// fixture, rather than forcing unrelated component tests to expect Turkish.
// Keep this computed at read time so tests can toggle production mode safely.
const fallbackContext: UiLanguageContextValue = {
  get language() {
    return shouldForceTurkishUi() ? 'tr' : 'zh';
  },
  setLanguage: () => undefined,
  t: (key, params) => {
    const fallbackLanguage = shouldForceTurkishUi() ? 'tr' : 'zh';
    return formatUiText(UI_TEXT[fallbackLanguage][key], params);
  },
};

const UiLanguageContext = createContext<UiLanguageContextValue | null>(null);

export const UiLanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(getRuntimeInitialLanguage);

  const setLanguage = useCallback((nextLanguage: UiLanguage) => {
    const selected = shouldForceTurkishUi() ? 'tr' : nextLanguage;
    setLanguageState(selected);
    persistUiLanguage(getUiLanguageStorage(), selected);
  }, []);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = shouldForceTurkishUi() ? 'tr' : language;
    }
    if (shouldForceTurkishUi()) {
      persistUiLanguage(getUiLanguageStorage(), 'tr');
    }
  }, [language]);

  const value = useMemo<UiLanguageContextValue>(() => ({
    language,
    setLanguage,
    t: (key, params) => formatUiText(UI_TEXT[language][key], params),
  }), [language, setLanguage]);

  return (
    <UiLanguageContext.Provider value={value}>
      {children}
    </UiLanguageContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components -- useUiLanguage is a hook, co-located for context access
export function useUiLanguage(): UiLanguageContextValue {
  return useContext(UiLanguageContext) ?? fallbackContext;
}
