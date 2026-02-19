import React from 'react';

interface StatusBadgeProps {
  status: 'online' | 'offline' | 'running' | 'failed' | 'success';
}

const styles = {
  online: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  offline: 'bg-red-50 text-red-700 border-red-200',
  running: 'bg-blue-50 text-blue-700 border-blue-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold ${styles[status]}`}>
      {status}
    </span>
  );
};
