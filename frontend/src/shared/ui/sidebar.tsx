'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const MAIN_NAV = [
  { href: '/dashboard', label: 'Tổng quan' },
  { href: '/data', label: 'Lịch sử giá' },
  { href: '/replay', label: 'Mô phỏng' },
  { href: '/report', label: 'Báo cáo' },
];

const SECONDARY_NAV = [
  { href: '/', label: 'Giới thiệu' },
  { href: '/about', label: 'Phương pháp' },
];

/** Match active nav: /report/123 matches /report, but /reporting does not. */
function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(href + '/');
}

function NavLinks({ onClick }: { onClick?: () => void }) {
  const pathname = usePathname();
  return (
    <>
      <nav aria-label="Mục làm việc" className="sidebar-nav-main">
        {MAIN_NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-link${active ? ' sidebar-link-active' : ''}`}
              aria-current={active ? 'page' : undefined}
              onClick={onClick}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="sidebar-divider" />
      <nav aria-label="Điều hướng phụ" className="sidebar-nav-secondary">
        {SECONDARY_NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-link${active ? ' sidebar-link-active' : ''}`}
              aria-current={active ? 'page' : undefined}
              onClick={onClick}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const toggleBtnRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();

  // Close drawer on route change
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Return focus to the toggle button when the drawer closes
  const close = useCallback(() => {
    setOpen(false);
    requestAnimationFrame(() => {
      toggleBtnRef.current?.focus();
    });
  }, []);

  // Escape closes the drawer
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, close]);

  // Focus the first control when the drawer opens
  useEffect(() => {
    if (!open) return;
    drawerRef.current?.querySelector<HTMLElement>('a, button')?.focus();
  }, [open]);

  // Keep Tab focus inside the open drawer
  useEffect(() => {
    if (!open || !drawerRef.current) return;
    const drawer = drawerRef.current;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const focusable = drawer.querySelectorAll<HTMLElement>('a[href], button:not([disabled])');
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    drawer.addEventListener('keydown', handleKeyDown);
    return () => drawer.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  return (
    <>
      <aside className="sidebar-desktop" aria-label="Điều hướng làm việc">
        <div className="sidebar-brand">
          <Link href="/dashboard" className="sidebar-brand-link">
            <span className="sidebar-brand-icon" aria-hidden="true">✦</span>
            <span className="sidebar-brand-name">ShootingStar</span>
          </Link>
        </div>
        <NavLinks />
      </aside>

      <button
        ref={toggleBtnRef}
        type="button"
        className="sidebar-mobile-toggle"
        aria-label="Mở menu"
        aria-expanded={open}
        aria-controls="sidebar-drawer"
        onClick={() => setOpen(true)}
      >
        <span aria-hidden="true">☰</span>
        <span>Menu</span>
      </button>

      {open && <div className="sidebar-overlay" aria-hidden="true" onClick={close} />}

      {/* inert removes the closed drawer from Tab order and the accessibility tree. */}
      <div
        id="sidebar-drawer"
        ref={drawerRef}
        className={`sidebar-drawer${open ? ' sidebar-drawer-open' : ''}`}
        aria-label="Điều hướng làm việc"
        role="dialog"
        aria-modal="true"
        inert={!open ? true : undefined}
      >
        <div className="sidebar-drawer-header">
          <span className="sidebar-brand-name">ShootingStar</span>
          <button type="button" className="sidebar-drawer-close" aria-label="Đóng menu" onClick={close}>
            ✕
          </button>
        </div>
        <NavLinks onClick={close} />
      </div>
    </>
  );
}
