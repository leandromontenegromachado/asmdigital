import React from 'react';
import { Cable, Bell, FileText, Star, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export interface StatData {
  title: string;
  value: string | number;
  total?: string | number;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  icon: 'cable' | 'bell' | 'file' | 'star';
  highlight?: boolean;
}

interface StatCardProps {
  data: StatData;
}

const getIcon = (iconName: string) => {
  switch (iconName) {
    case 'cable':
      return <Cable size={20} />;
    case 'bell':
      return <Bell size={20} />;
    case 'file':
      return <FileText size={20} />;
    case 'star':
      return <Star size={20} />;
    default:
      return <Cable size={20} />;
  }
};

const getTrendIcon = (direction: string) => {
  switch (direction) {
    case 'up':
      return <TrendingUp size={14} className="mr-1" />;
    case 'down':
      return <TrendingDown size={14} className="mr-1" />;
    default:
      return <Minus size={14} className="mr-1" />;
  }
};

export const StatCard: React.FC<StatCardProps> = ({ data }) => {
  return (
    <div
      className={`
        flex flex-col gap-2 rounded-xl border border-slate-200 bg-white p-6 shadow-sm 
        hover:shadow-md transition-shadow relative overflow-hidden group
        ${data.highlight ? 'ring-0' : ''}
      `}
    >
      {data.highlight && (
        <div className="absolute right-0 top-0 h-32 w-32 translate-x-10 -translate-y-10 rounded-full bg-gradient-to-br from-blue-50 to-blue-100/50 opacity-50 blur-2xl transition-all group-hover:opacity-100 pointer-events-none"></div>
      )}

      <div className="flex items-center justify-between relative z-10">
        <p className="text-sm font-medium text-slate-500">{data.title}</p>
        <div className="p-2 bg-blue-50 rounded-lg text-primary">{getIcon(data.icon)}</div>
      </div>

      <div className="flex items-end justify-between mt-2 relative z-10">
        <p className="text-3xl font-bold text-slate-900">
          {data.value}
          {data.total && <span className="text-lg text-slate-400 font-medium">{data.total}</span>}
        </p>
        {data.trend && (
          <span
            className={`
              flex items-center text-xs font-bold px-2 py-1 rounded-md
              ${data.trendDirection === 'down' && data.icon !== 'file' ? 'text-red-600 bg-red-50' : 'text-emerald-600 bg-emerald-50'}
              ${data.trendDirection === 'down' && data.icon === 'file' ? 'text-emerald-600 bg-emerald-50' : ''}
            `}
          >
            {getTrendIcon(data.trendDirection || 'neutral')}
            {data.trend}
          </span>
        )}
      </div>
    </div>
  );
};
