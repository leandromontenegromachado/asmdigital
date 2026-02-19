import React from 'react';
import { Sidebar } from './components/Sidebar';
import { MappingPanel } from './components/MappingPanel';
import { PreviewPanel } from './components/PreviewPanel';
import { ChevronRight, HelpCircle, Bell, Save, AlertCircle } from 'lucide-react';

const App: React.FC = () => {
  return (
    <div className="flex min-h-screen w-full bg-slate-50 font-sans text-slate-900">
      <Sidebar />
      
      <main className="flex-1 flex flex-col md:ml-64 transition-all duration-300">
        {/* Header */}
        <header className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-10 flex items-center px-6 md:px-8">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <a href="#" className="hover:text-primary-600 transition-colors">Configurações</a>
            <ChevronRight size={14} className="text-slate-400" />
            <a href="#" className="hover:text-primary-600 transition-colors">Redmine</a>
            <ChevronRight size={14} className="text-slate-400" />
            <span className="text-slate-800 font-medium">Mapeamento e Normalização</span>
          </div>
          <div className="ml-auto flex items-center gap-4">
            <button className="text-slate-400 hover:text-primary-600 transition-colors">
              <HelpCircle size={20} />
            </button>
            <button className="text-slate-400 hover:text-primary-600 transition-colors relative">
              <Bell size={20} />
              <span className="absolute top-0 right-0 h-2 w-2 bg-red-500 rounded-full ring-2 ring-white"></span>
            </button>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 p-6 md:p-8 overflow-y-auto">
          <div className="max-w-7xl mx-auto space-y-8">
            
            {/* Page Title & Actions */}
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div className="space-y-2 max-w-2xl">
                <h2 className="text-3xl font-black text-slate-900 tracking-tight">Mapeamento de Dados</h2>
                <p className="text-slate-500 text-base leading-relaxed">
                  Configure como os campos personalizados do Redmine são traduzidos para as entidades do sistema (Cliente, Sistema e Entrega). Utilize regras de Regex para limpar e padronizar os dados antes da ingestão.
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button className="px-4 py-2.5 rounded-lg border border-slate-300 text-slate-600 font-semibold text-sm hover:text-slate-800 hover:bg-slate-50 transition-all bg-white shadow-sm">
                  Cancelar
                </button>
                <button className="px-4 py-2.5 rounded-lg bg-primary-500 text-white font-bold text-sm shadow-md shadow-primary-500/20 hover:bg-primary-600 transition-all flex items-center gap-2">
                  <Save size={18} />
                  Salvar Alterações
                </button>
              </div>
            </div>

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
              
              {/* Left Column (Main Config) */}
              <div className="xl:col-span-8">
                <MappingPanel />
              </div>

              {/* Right Column (Preview Sidebar) */}
              <div className="xl:col-span-4">
                <PreviewPanel />
              </div>

            </div>

          </div>
        </div>
      </main>
    </div>
  );
};

export default App;