import React from 'react';

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  tone?: 'success' | 'error' | 'info';
}

interface ToastsProps {
  items: ToastItem[];
}

const toneStyles = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  error: 'border-red-200 bg-red-50 text-red-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
};

export const Toasts: React.FC<ToastsProps> = ({ items }) => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
      {items.map((toast) => (
        <div
          key={toast.id}
          className={`rounded-lg border px-4 py-3 shadow-lg ${toneStyles[toast.tone || 'info']}`}
        >
          <p className="text-sm font-bold">{toast.title}</p>
          {toast.description && <p className="text-xs">{toast.description}</p>}
        </div>
      ))}
    </div>
  );
};
