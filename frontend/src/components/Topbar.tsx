import React from 'react';
import { Bell, Search } from 'lucide-react';

interface TopbarProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export const Topbar: React.FC<TopbarProps> = ({ title, subtitle, action }) => {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex flex-col gap-1">
        <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">{title}</h2>
        {subtitle && <p className="text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm">
          <Search size={16} />
          <span>Buscar</span>
        </div>
        <button className="flex items-center justify-center rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-600 shadow-sm hover:bg-slate-50">
          <Bell size={16} />
        </button>
        {action}
      </div>
    </header>
  );
};
