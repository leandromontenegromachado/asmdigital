import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, ChevronRight } from 'lucide-react';
import { Alert } from '../types';

interface AlertItemProps {
  alert: Alert;
}

const getAlertConfig = (type: Alert['type']) => {
  switch (type) {
    case 'critical':
      return {
        iconBg: 'bg-red-50',
        iconText: 'text-red-600',
        borderColor: 'border-red-100',
        icon: <AlertCircle size={20} />,
        badgeBg: 'bg-red-50',
        badgeBorder: 'border-red-100',
        badgeText: 'text-red-700'
      };
    case 'warning':
      return {
        iconBg: 'bg-amber-50',
        iconText: 'text-amber-600',
        borderColor: 'border-amber-100',
        icon: <AlertTriangle size={20} />,
        badgeBg: 'bg-amber-50',
        badgeBorder: 'border-amber-100',
        badgeText: 'text-amber-700'
      };
    case 'success':
      return {
        iconBg: 'bg-emerald-50',
        iconText: 'text-emerald-600',
        borderColor: 'border-emerald-100',
        icon: <CheckCircle size={20} />,
        badgeBg: 'bg-emerald-50',
        badgeBorder: 'border-emerald-100',
        badgeText: 'text-emerald-700'
      };
  }
};

export const AlertItem: React.FC<AlertItemProps> = ({ alert }) => {
  const config = getAlertConfig(alert.type);

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-4 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors cursor-pointer group">
      <div className="flex items-center gap-4 flex-1">
        <div className={`flex-shrink-0 size-10 rounded-full border flex items-center justify-center ${config.iconBg} ${config.iconText} ${config.borderColor}`}>
          {config.icon}
        </div>
        <div className="flex flex-col">
          <p className="text-sm font-bold text-slate-900">{alert.title}</p>
          <p className="text-xs text-slate-500">{alert.subtitle}</p>
        </div>
      </div>
      <div className="flex items-center justify-between sm:justify-end gap-4 sm:w-auto w-full">
        <span className={`text-xs font-bold border px-2 py-1 rounded ${config.badgeBg} ${config.badgeBorder} ${config.badgeText}`}>
          {alert.tag}
        </span>
        <span className="text-xs text-slate-400 font-medium min-w-[70px] text-right">{alert.timeAgo}</span>
        <button className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-primary transition-opacity">
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};