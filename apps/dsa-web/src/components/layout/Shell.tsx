import type React from 'react';
import { useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { DesktopUpdateIndicator } from './DesktopUpdateIndicator';
import { ThemeToggle } from '../theme/ThemeToggle';
import { UiLanguageToggle } from '../i18n/UiLanguageToggle';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { useNewsNotifications } from '../../hooks/useNewsNotifications';
import '../../styles/etre-2026.css';

type ShellProps = {
  children?: React.ReactNode;
};

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { t } = useUiLanguage();
  const newsUnread = useNewsNotifications();

  useEffect(() => {
    if (!mobileOpen) return undefined;
    const handleResize = () => {
      if (window.innerWidth >= 1024) setMobileOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [mobileOpen]);

  return (
    <div className="etre-shell text-foreground">
      <div className="etre-shell-mobile-bar lg:hidden">
        <button type="button" onClick={() => setMobileOpen(true)}
          className="etre-action-pill" aria-label={t('layout.openNav')}>
          <Menu className="h-5 w-5" />
        </button>
        <span className="etre-shell-mobile-brand">ETRE</span>
        <div className="etre-top-actions">
          <DesktopUpdateIndicator />
          <UiLanguageToggle />
          <ThemeToggle />
        </div>
      </div>

      <div className="etre-shell-frame">
        <aside className="etre-shell-sidebar" aria-label={t('layout.desktopSidebar')}>
          <SidebarNav newsUnread={newsUnread} onNavigate={() => setMobileOpen(false)} />
        </aside>
        <main className="etre-shell-main">
          <div className="etre-workspace">
            {children ?? <Outlet />}
          </div>
        </main>
      </div>

      <Drawer
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        title={t('layout.navMenu')}
        width="max-w-xs"
        zIndex={90}
        side="left"
      >
        <SidebarNav newsUnread={newsUnread} onNavigate={() => setMobileOpen(false)} />
      </Drawer>
    </div>
  );
};
