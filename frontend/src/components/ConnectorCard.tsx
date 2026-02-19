import React from 'react';
import { Cloud, MessageSquare, Database, Server, CheckCircle2 } from 'lucide-react';

export interface ConnectorStatus {
  id: string;
  name: string;
  status: 'online' | 'offline';
  type: 'cloud' | 'chat' | 'task' | 'db';
  provider: 'aws' | 'azure' | 'slack' | 'jira' | 'servicenow';
}

interface ConnectorCardProps {
  connector: ConnectorStatus;
}

const getProviderIcon = (provider: ConnectorStatus['provider']) => {
  switch (provider) {
    case 'aws':
      return <Cloud size={18} />;
    case 'azure':
      return <Cloud size={18} />;
    case 'slack':
      return <MessageSquare size={18} />;
    case 'jira':
      return <CheckCircle2 size={18} />;
    case 'servicenow':
      return <Database size={18} />;
    default:
      return <Server size={18} />;
  }
};

const getProviderColors = (provider: ConnectorStatus['provider'], status: string) => {
  if (status === 'offline') {
    return {
      bg: 'bg-red-50',
      border: 'border-red-200',
      iconBg: 'bg-white',
      iconText: 'text-purple-600',
      statusText: 'text-red-600',
    };
  }

  switch (provider) {
    case 'aws':
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-orange-50', iconText: 'text-orange-600', statusText: 'text-emerald-600' };
    case 'azure':
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-blue-50', iconText: 'text-blue-600', statusText: 'text-emerald-600' };
    case 'slack':
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-purple-50', iconText: 'text-purple-600', statusText: 'text-emerald-600' };
    case 'jira':
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-blue-50', iconText: 'text-blue-500', statusText: 'text-emerald-600' };
    case 'servicenow':
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-green-50', iconText: 'text-green-600', statusText: 'text-emerald-600' };
    default:
      return { bg: 'bg-white', border: 'border-slate-200', iconBg: 'bg-slate-50', iconText: 'text-slate-600', statusText: 'text-emerald-600' };
  }
};

export const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector }) => {
  const colors = getProviderColors(connector.provider, connector.status);

  return (
    <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 shadow-sm transition-colors ${colors.bg} ${colors.border} ${connector.status === 'online' ? 'hover:border-slate-300' : ''}`}>
      <div className={`flex items-center justify-center size-8 rounded-full border border-transparent ${colors.iconBg} ${colors.iconText} ${connector.status === 'offline' ? 'border-purple-100' : ''}`}>
        {getProviderIcon(connector.provider)}
      </div>
      <div className="flex flex-col">
        <span className="text-xs font-bold text-slate-800">{connector.name}</span>
        <span className={`text-[10px] font-bold flex items-center gap-1 ${colors.statusText}`}>
          ● {connector.status === 'online' ? 'Online' : 'Offline'}
        </span>
      </div>
    </div>
  );
};
