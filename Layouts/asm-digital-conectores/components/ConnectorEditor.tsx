import React, { useState } from 'react';
import { Connector } from '../types';

interface ConnectorEditorProps {
  connector: Connector;
  onCancel: () => void;
  onSave: () => void;
}

const ConnectorEditor: React.FC<ConnectorEditorProps> = ({ connector, onCancel, onSave }) => {
  const [tokenVisible, setTokenVisible] = useState(false);

  // Fallback if config is missing (robustness)
  const config = connector.config || {
    urlLabel: 'URL',
    urlValue: '',
    tokenLabel: 'Token',
    tokenValue: '',
    projectLabel: 'Project',
    projectValue: '',
    projects: []
  };

  return (
    <div className="col-span-1 md:col-span-2 relative flex flex-col bg-white dark:bg-card-dark rounded-xl shadow-lg ring-2 ring-primary dark:ring-primary z-10 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
      <div className="absolute top-0 left-0 w-1 h-full bg-primary"></div>
      
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="size-12 rounded-lg bg-slate-50 dark:bg-[#233c48] p-2 flex items-center justify-center">
              {connector.logoUrl && (
                <img 
                  alt={connector.logoAlt} 
                  className="w-full h-full object-contain" 
                  src={connector.logoUrl} 
                />
              )}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">{connector.name}</h3>
              <p className="text-sm text-slate-500 dark:text-[#92b7c9]">{connector.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="text-slate-400 hover:text-slate-600 dark:text-[#92b7c9] dark:hover:text-white transition-colors" title="Documentação">
              <span className="material-symbols-outlined">help</span>
            </button>
            <button onClick={onCancel} className="text-slate-400 hover:text-slate-600 dark:text-[#92b7c9] dark:hover:text-white transition-colors" title="Fechar edição">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Form Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            {/* URL Input */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-[#92b7c9] mb-1.5">{config.urlLabel}</label>
              <div className="relative group">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 group-focus-within:text-primary transition-colors">
                  <span className="material-symbols-outlined !text-[20px]">link</span>
                </span>
                <input 
                  className="w-full rounded-lg border border-slate-300 dark:border-[#233c48] bg-white dark:bg-[#111c22] py-2.5 pl-10 pr-4 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-shadow" 
                  placeholder="https://..." 
                  type="url" 
                  defaultValue={config.urlValue}
                />
              </div>
            </div>

            {/* Token Input */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-[#92b7c9] mb-1.5">{config.tokenLabel}</label>
              <div className="relative group">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 group-focus-within:text-primary transition-colors">
                  <span className="material-symbols-outlined !text-[20px]">key</span>
                </span>
                <input 
                  className="w-full rounded-lg border border-slate-300 dark:border-[#233c48] bg-white dark:bg-[#111c22] py-2.5 pl-10 pr-10 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-shadow font-mono" 
                  placeholder="Cole seu token aqui" 
                  type={tokenVisible ? "text" : "password"}
                  defaultValue={config.tokenValue}
                />
                <button 
                  onClick={() => setTokenVisible(!tokenVisible)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-primary cursor-pointer"
                  type="button"
                >
                  <span className="material-symbols-outlined !text-[20px]">{tokenVisible ? 'visibility_off' : 'visibility'}</span>
                </button>
              </div>
              <p className="mt-1 text-xs text-slate-400 dark:text-[#586e7a]">O token expira em 30 dias.</p>
            </div>
          </div>

          <div className="space-y-4">
            {/* Project Select */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-[#92b7c9] mb-1.5">{config.projectLabel}</label>
              <div className="relative group">
                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 group-focus-within:text-primary transition-colors">
                  <span className="material-symbols-outlined !text-[20px]">folder</span>
                </span>
                <select 
                  className="w-full appearance-none rounded-lg border border-slate-300 dark:border-[#233c48] bg-white dark:bg-[#111c22] py-2.5 pl-10 pr-8 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none cursor-pointer"
                  defaultValue={config.projectValue}
                >
                  {config.projects.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400">
                  <span className="material-symbols-outlined !text-[20px]">expand_more</span>
                </span>
              </div>
            </div>

            {/* Warning Box */}
            {config.warning && (
              <div className="bg-amber-50/50 dark:bg-[#111c22]/50 rounded-lg p-3 border border-amber-100 dark:border-[#233c48] mt-6">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-amber-500 !text-[20px]">warning</span>
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-200">Atenção</span>
                </div>
                <p className="text-xs text-slate-500 dark:text-[#92b7c9] leading-relaxed">
                  {config.warning}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="bg-slate-50 dark:bg-[#233c48]/30 px-6 py-4 flex items-center justify-between border-t border-slate-100 dark:border-[#233c48]">
        <button className="flex items-center gap-2 text-slate-600 dark:text-[#92b7c9] hover:text-primary dark:hover:text-primary text-sm font-medium transition-colors">
          <span className="material-symbols-outlined !text-[20px]">sync_alt</span>
          Testar Conexão
        </button>
        <div className="flex gap-3">
          <button onClick={onCancel} className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-white hover:bg-slate-100 dark:hover:bg-[#233c48] transition-colors">
            Cancelar
          </button>
          <button onClick={onSave} className="px-6 py-2 rounded-lg bg-primary hover:bg-sky-600 text-white text-sm font-medium shadow-md shadow-sky-500/20 transition-all transform active:scale-95">
            Salvar Alterações
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectorEditor;
