import { createElement, type ReactNode } from 'react';
import { render as testingLibraryRender, type RenderOptions } from '@testing-library/react';
import { UiLanguageProvider } from '../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../utils/uiLanguage';

/**
 * Explicit fixture for legacy Chinese-language UI assertions.
 *
 * The application defaults to Turkish. Old unit tests were written when the
 * implicit fallback was Chinese and should opt into that language rather than
 * changing the production user's locale or rewriting Chinese assertions to
 * pass against unrelated Turkish text. Explicitly stored EN/TR choices win.
 *
 * Use ONLY in tests with historical zh expectations. Never in production code
 * or in tests that verify automatic locale detection/defaults.
 */
export function renderLegacyChineseUi(
  ui: ReactNode,
  options?: RenderOptions,
): ReturnType<typeof testingLibraryRender> {
  try {
    if (!window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)) {
      window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    }
  } catch {
    // The provider handles unavailable localStorage safely.
  }
  const AdditionalWrapper = options?.wrapper;
  const WithLanguage = ({ children }: { children: ReactNode }) => (
    <UiLanguageProvider>
      {AdditionalWrapper ? createElement(AdditionalWrapper, {}, children) : children}
    </UiLanguageProvider>
  );
  return testingLibraryRender(ui, { ...options, wrapper: WithLanguage });
}
