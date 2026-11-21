import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import { ThemeProvider } from '../ThemeProvider';
import { ThemeToggle } from '../ThemeToggle';

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY));

describe('ThemeToggle', () => {
  it('opens the theme menu and shows all theme modes', async () => {
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    render(
      <UiLanguageProvider>
        <ThemeProvider>
          <ThemeToggle />
        </ThemeProvider>
      </UiLanguageProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: '切换主题' }));

    expect(await screen.findByRole('menu', { name: '主题模式' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '浅色' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '深色' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '跟随系统' })).toBeInTheDocument();
  });
});
