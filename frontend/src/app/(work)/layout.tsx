import React from 'react';
import { Sidebar } from '@/shared/ui/sidebar';

export default function WorkLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="work-layout">
      <a href="#main-content" className="visually-hidden">
        Bỏ qua điều hướng
      </a>
      <Sidebar />
      <main className="work-content" id="main-content">
        {children}
      </main>
    </div>
  );
}
