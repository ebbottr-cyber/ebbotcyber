import { useCallback, useEffect, useRef, useState } from 'react';
import { newsApi, NEWS_CHANGED_EVENT, type NewsStatus } from '../api/news';

/** A single Shell-level poll: unread badge everywhere and optional foreground alerts.

 Browser notifications are never promised while the tab/browser is closed.
 On initial load we set a baseline so historical unread records do not spam users.
*/
export function useNewsNotifications(): number {
  const [unread, setUnread] = useState(0);
  const known = useRef<Set<string> | null>(null);
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    let status: NewsStatus;
    try {
      status = await newsApi.status();
    } catch {
      return;
    }
    if (!alive.current) return;
    setUnread(status.notifications_enabled ? status.unread_count : 0);
    const ids = status.latest_unread.map(item => item.id);
    if (known.current && status.notifications_enabled &&
      typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      for (const item of status.latest_unread.filter(i => !known.current?.has(i.id)).reverse()) {
        try {
          new Notification('ETRE · Yeni piyasa haberi', {
            body: item.title,
            tag: item.id,
          });
        } catch {
          // OS browser notifications are optional. In-app unread badge remains.
        }
      }
    }
    // Do not discard IDs on read-all: old articles should never re-notify.
    known.current = new Set([...(known.current ?? []), ...ids].slice(-300));
  }, []);

  useEffect(() => {
    alive.current = true;
    void refresh();
    const interval = window.setInterval(() => void refresh(), 60000);
    window.addEventListener(NEWS_CHANGED_EVENT, refresh);
    return () => {
      alive.current = false;
      window.clearInterval(interval);
      window.removeEventListener(NEWS_CHANGED_EVENT, refresh);
    };
  }, [refresh]);
  return unread;
}
