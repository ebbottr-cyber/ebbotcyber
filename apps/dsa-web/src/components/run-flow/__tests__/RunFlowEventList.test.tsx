import { fireEvent, render as rtlRender, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import type { RunFlowEvent } from '../../../types/runFlow';
import { RunFlowEventList } from '../RunFlowEventList';

// Legacy Chinese text assertions are scoped to this test, not the Turkish production default.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  if (!window.localStorage.getItem(UI_LANGUAGE_STORAGE_KEY)) {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
  }
  return rtlRender(ui, { ...options, wrapper: UiLanguageProvider });
}

afterEach(() => {
  window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
});

const events: RunFlowEvent[] = [
  {
    id: 'evt-1',
    timestamp: '2026-06-08T08:00:01Z',
    severity: 'info',
    type: 'task_created',
    nodeId: 'request',
    title: '任务创建',
  },
  {
    id: 'evt-2',
    timestamp: '2026-06-08T08:00:02Z',
    severity: 'warning',
    type: 'provider_fallback',
    nodeId: 'daily_data',
    title: '日线降级',
    message: 'Tushare 失败后切换 AkShare',
  },
  {
    id: 'evt-3',
    timestamp: '2026-06-08T08:00:03Z',
    severity: 'danger',
    type: 'task_cancelled',
    nodeId: 'queue',
    title: '任务取消',
  },
];

describe('RunFlowEventList', () => {
  it('filters fallback and cancellation events with visible text labels', () => {
    render(<RunFlowEventList events={events} />);

    expect(screen.getByText('任务创建')).toBeInTheDocument();
    expect(screen.getByText('日线降级')).toBeInTheDocument();
    expect(screen.getByText('任务取消')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '降级回退/重试' }));

    expect(screen.getByText('日线降级')).toBeInTheDocument();
    expect(screen.queryByText('任务创建')).not.toBeInTheDocument();
    expect(screen.queryByText('任务取消')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '取消' }));

    expect(screen.getByText('任务取消')).toBeInTheDocument();
    expect(screen.queryByText('日线降级')).not.toBeInTheDocument();
    expect(screen.getByText('危险')).toBeInTheDocument();
  });

  it('selects the event node when an event row is clicked', () => {
    const onSelectNode = vi.fn();
    render(<RunFlowEventList events={events} onSelectNode={onSelectNode} />);

    fireEvent.click(screen.getByRole('button', { name: '查看事件 日线降级 关联节点' }));

    expect(onSelectNode).toHaveBeenCalledWith('daily_data');
  });
});
