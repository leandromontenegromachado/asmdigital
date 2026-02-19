import React from 'react';

interface StateBlockProps {
  title: string;
  description?: string;
  tone?: 'loading' | 'empty' | 'error';
}

const toneStyles = {
  loading: 'bg-slate-50 text-slate-600 border-slate-200',
  empty: 'bg-white text-slate-500 border-slate-200',
  error: 'bg-red-50 text-red-700 border-red-200',
};

export const StateBlock: React.FC<StateBlockProps> = ({ title, description, tone = 'empty' }) => {
  return (
    <div className={`rounded-xl border p-8 text-center ${toneStyles[tone]}`}>
      <p className="text-sm font-bold">{title}</p>
      {description && <p className="text-xs mt-2">{description}</p>}
    </div>
  );
};
