import React from 'react';
import Link from 'next/link';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="spread">
      <div className="page-header">
        <h1 className="page-title">{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Card({
  children,
  className = '',
  compact = false,
}: {
  children: React.ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return <div className={`card${compact ? ' card-compact' : ''}${className ? ` ${className}` : ''}`}>{children}</div>;
}

export function Badge({
  variant = 'neutral',
  children,
}: {
  variant?: 'success' | 'warning' | 'error' | 'neutral' | 'accent';
  children: React.ReactNode;
}) {
  return <span className={`badge badge-${variant}`}>{children}</span>;
}

export function StatBox({
  label,
  value,
  subtext,
}: {
  label: string;
  value: string | number;
  subtext?: string;
}) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {subtext && <div className="stat-subtext">{subtext}</div>}
    </div>
  );
}

export function Notice({
  variant = 'info',
  title,
  children,
  action,
}: {
  variant?: 'info' | 'warning' | 'error' | 'success' | 'neutral';
  title?: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div
      className={`notice${variant === 'info' ? '' : ` notice-${variant}`}`}
      role={variant === 'error' ? 'alert' : 'status'}
    >
      <div className="notice-body">
        {title && <strong>{title}</strong>}
        {title && children ? ' ' : null}
        {children}
      </div>
      {action}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <Notice variant="error" title="Không kết nối được dịch vụ dữ liệu.">
      {message}
    </Notice>
  );
}

export function EmptyState({
  title = 'Chưa có dữ liệu',
  message,
  actionLabel,
  actionHref,
}: {
  title?: string;
  message?: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="empty-state">
      <h3 className="empty-title">{title}</h3>
      {message && <p className="empty-message">{message}</p>}
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn btn-secondary btn-sm">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="row" style={{ gap: 8 }} role="status">
      <span className="spinner" aria-hidden="true" />
      {label && <span>{label}</span>}
    </span>
  );
}
