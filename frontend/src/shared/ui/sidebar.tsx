'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const MAIN_NAV = [
  { href: '/dashboard', label: 'Tổng quan' },
  { href: '/data', label: 'Lịch sử giá' },
  { href: '/replay', label: 'Mô phỏng (Replay)' },
  { href: '/research', label: 'Kết quả thử nghiệm' },
  { href: '/patterns', label: 'Mẫu hình giá' },
  { href: '/signals', label: 'Dự đoán' },
];

const SECONDARY_NAV = [
  { href: '/', label: 'Giới thiệu' },
  { href: '/about', label: 'Phương pháp' },
];

/** Match active nav: /research/123 matches /research, but /researching does not. */
function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  // exact match or segment prefix
  return pathname === href || pathname.startsWith(href + '/');
}

function NavLinks({
  onClick,
}: {
  onClick?: () => void;
}) {
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
              className={`sidebar-link sidebar-link-secondary${active ? ' sidebar-link-active' : ''}`}
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

  // Return focus to toggle button when drawer closes
  const close = useCallback(() => {
    setOpen(false);
    // Defer so the drawer is actually gone before we move focus
    requestAnimationFrame(() => {
      toggleBtnRef.current?.focus();
    });
  }, []);

  // Escape key closes drawer
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, close]);

  // Focus trap: when drawer opens, focus first link
  useEffect(() => {
    if (!open) return;
    const firstLink = drawerRef.current?.querySelector<HTMLElement>('a, button');
    firstLink?.focus();
  }, [open]);

  // Focus trap loop inside drawer
  useEffect(() => {
    if (!open || !drawerRef.current) return;
    const drawer = drawerRef.current;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const focusable = drawer.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])'
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    drawer.addEventListener('keydown', handleKeyDown);
    return () => drawer.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  return (
    <>
      {/* ── Desktop sidebar ── */}
      <aside className="sidebar-desktop" aria-label="Điều hướng làm việc">
        <div className="sidebar-brand">
          <Link href="/" className="sidebar-brand-link">
            <span className="sidebar-brand-icon">✦</span>
            <span className="sidebar-brand-name">ShootingStar</span>
          </Link>
        </div>
        <NavLinks />
      </aside>

      {/* ── Mobile toggle button ── */}
      <button
        ref={toggleBtnRef}
        className="sidebar-mobile-toggle"
        aria-label="Mở mục làm việc"
        aria-expanded={open}
        aria-controls="sidebar-drawer"
        onClick={() => setOpen(true)}
      >
        <span className="sidebar-hamburger" aria-hidden="true">☰</span>
        <span>Mục làm việc</span>
      </button>

      {/* ── Mobile overlay backdrop ── */}
      {open && (
        <div
          className="sidebar-overlay"
          aria-hidden="true"
          onClick={close}
        />
      )}

      {/* ── Mobile drawer ── */}
      {/* inert removes element from Tab order and AT tree when closed;
          aria-hidden alone does NOT block Tab focus.
          React 19 supports inert as a boolean prop. */}
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
          <button
            className="sidebar-drawer-close"
            aria-label="Đóng menu"
            onClick={close}
          >
            ✕
          </button>
        </div>
        <NavLinks onClick={close} />
      </div>
    </>
  );
}
