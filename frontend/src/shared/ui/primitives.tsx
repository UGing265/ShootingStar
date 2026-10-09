import React from 'react';
import Link from 'next/link';

export function Card({
  children,
  className = '',
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div className={`card ${className}`} style={style}>
      {children}
    </div>
  );
}

export function Badge({
  variant = 'neutral',
  children,
}: {
  variant?: 'success' | 'warning' | 'error' | 'neutral' | 'accent';
  children: React.ReactNode;
}) {
  return (
    <span className={`badge badge-${variant}`}>
      {children}
    </span>
  );
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
    <div className="stat-box">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {subtext && <div className="stat-subtext">{subtext}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  actionLabel,
  actionHref,
}: {
  title: string;
  message: string;
  actionLabel?: string;
  actionHref?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">✧</div>
      <h3 className="empty-title">{title}</h3>
      <p className="empty-message">{message}</p>
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn-action">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}

export function ErrorBanner({
  message,
}: {
  message: string;
}) {
  return (
    <div className="error-banner" role="alert">
      <span className="error-icon">⚠️</span>
      <div className="error-text">
        <strong>Không thể kết nối tới dịch vụ:</strong> {message}
      </div>
    </div>
  );
}
