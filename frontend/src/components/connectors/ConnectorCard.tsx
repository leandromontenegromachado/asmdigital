import React from 'react';

export type ConnectorStatus = 'connected' | 'inactive' | 'error' | 'editing';

export interface ConnectorCardModel {
  id: string;
  name: string;
  description: string;
  logoUrl?: string;
  logoAlt?: string;
  status: ConnectorStatus;
  syncTime?: string;
  errorMessage?: string;
  errorCode?: string;
}

interface ConnectorCardProps {
  connector: ConnectorCardModel;
  onConfigure: (id: string) => void;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector, onConfigure }) => {
  const isError = connector.status === 'error';
  const isConnected = connector.status === 'connected';
  const isInactive = connector.status === 'inactive';

  return (
    <div
      className={`
        group relative flex flex-col bg-white dark:bg-card-dark rounded-xl shadow-sm border
        border-slate-200 dark:border-transparent transition-all duration-300
        ${isError ? 'hover:border-red-500/50 dark:hover:border-red-500/50' : 'hover:border-primary/50 dark:hover:border-primary/50'}
        ${isInactive ? 'opacity-90 hover:opacity-100' : ''}
      `}
    >
      <div className="p-6 flex flex-col h-full">
        <div className="flex justify-between items-start mb-4">
          <div className={`size-12 rounded-lg bg-slate-50 dark:bg-[#233c48] p-2 flex items-center justify-center ${!connector.logoUrl ? 'font-bold text-slate-700 dark:text-white text-xs' : ''}`}>
            {connector.logoUrl ? (
              <img
                alt={connector.logoAlt || connector.name}
                className={`w-full h-full object-contain transition-opacity ${isInactive ? 'opacity-75 group-hover:opacity-100' : 'opacity-90 group-hover:opacity-100'}`}
                src={connector.logoUrl}
              />
            ) : (
              connector.name
            )}
          </div>

          {isConnected && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-500/20">
              <span className="size-1.5 rounded-full bg-emerald-500"></span>
              Conectado
            </span>
          )}
          {isError && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 dark:bg-red-500/10 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:text-red-400 border border-red-100 dark:border-red-500/20">
              <span className="size-1.5 rounded-full bg-red-500"></span>
              Erro
            </span>
          )}
          {isInactive && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 dark:bg-slate-700/50 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-600">
              <span className="size-1.5 rounded-full bg-slate-400"></span>
              Inativo
            </span>
          )}
        </div>

        <div className="mb-4">
          <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">{connector.name}</h3>
          <p className="text-sm text-slate-500 dark:text-[#92b7c9] line-clamp-2 leading-relaxed">
            {connector.description}
          </p>
        </div>

        {isConnected && connector.syncTime && (
          <div className="mt-auto pt-4 border-t border-slate-100 dark:border-[#233c48] flex items-center justify-between text-xs text-slate-400 dark:text-[#586e7a]">
            <span>Sync: {connector.syncTime}</span>
          </div>
        )}
        {isError && (
          <div className="mt-auto pt-4 border-t border-slate-100 dark:border-[#233c48] flex items-center gap-1 text-xs text-red-500 dark:text-red-400">
            <span className="material-symbols-outlined !text-[14px]">error</span>
            <span>{connector.errorMessage} {connector.errorCode && `(${connector.errorCode})`}</span>
          </div>
        )}
        {isInactive && (
          <div className="mt-auto"></div>
        )}
      </div>

      <div className="px-6 pb-6">
        <button
          onClick={() => onConfigure(connector.id)}
          className={`
            w-full flex items-center justify-center gap-2 rounded-lg h-9 text-sm font-medium transition-colors
            ${isError
              ? 'bg-red-50 dark:bg-red-500/10 hover:bg-red-100 dark:hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-100 dark:border-red-500/20'
              : 'bg-slate-100 dark:bg-[#233c48] hover:bg-slate-200 dark:hover:bg-[#2c4b5a] text-slate-700 dark:text-white group-hover:bg-primary group-hover:text-white dark:group-hover:bg-primary dark:group-hover:text-white'
            }
          `}
        >
          <span className="material-symbols-outlined !text-[18px]">
            {isError ? 'build' : (isConnected ? 'settings' : 'add_link')}
          </span>
          {isError ? 'Corrigir Conexão' : 'Configurar'}
        </button>
      </div>
    </div>
  );
};

export default ConnectorCard;
