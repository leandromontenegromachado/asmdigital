import React, { useState } from 'react';
import Header from './components/Header';
import ConnectorCard from './components/ConnectorCard';
import ConnectorEditor from './components/ConnectorEditor';
import { INITIAL_CONNECTORS } from './constants';
import { Connector, ConnectorStatus } from './types';

const App: React.FC = () => {
  const [connectors, setConnectors] = useState<Connector[]>(INITIAL_CONNECTORS);

  const handleConfigure = (id: string) => {
    setConnectors(prev => prev.map(c => {
      if (c.id === id) {
        // Mocking the config if it doesn't exist for the demo
        const existingConfig = c.config || {
          urlLabel: 'Endpoint URL',
          urlValue: 'https://api.example.com',
          tokenLabel: 'API Key',
          tokenValue: '',
          projectLabel: 'Environment',
          projectValue: 'Production',
          projects: ['Production', 'Staging', 'Dev']
        };
        return { ...c, status: 'editing', config: existingConfig };
      }
      return c.status === 'editing' ? { ...c, status: c.errorMessage ? 'error' as ConnectorStatus : 'inactive' as ConnectorStatus } : c;
    }));
  };

  const handleCancel = (id: string) => {
     setConnectors(prev => prev.map(c => {
       // Revert to connected if it was connected, error if it was error, or inactive
       if (c.id === id) {
          // Simplification for demo: Revert to 'connected' if it was Azure (hardcoded check) or 'error' if FADPRO, else inactive.
          // A real app would store previous state.
          let prevStatus: ConnectorStatus = 'inactive';
          if (c.id === 'azure-devops') prevStatus = 'connected'; 
          if (c.id === 'redmine') prevStatus = 'connected';
          if (c.id === 'fadpro') prevStatus = 'error';
          
          return { ...c, status: prevStatus };
       }
       return c;
     }));
  };

  const handleSave = (id: string) => {
    setConnectors(prev => prev.map(c => 
      c.id === id ? { ...c, status: 'connected', errorMessage: undefined, errorCode: undefined, syncTime: 'Agora mesmo' } : c
    ));
  };

  return (
    <>
      <Header />
      <main className="flex-1 w-full max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8 mb-20">
        
        {/* Breadcrumbs */}
        <nav aria-label="Breadcrumb" className="flex mb-6">
          <ol className="inline-flex items-center space-x-1 md:space-x-2 rtl:space-x-reverse">
            <li className="inline-flex items-center">
              <a className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white transition-colors" href="#">
                <span className="material-symbols-outlined !text-[18px] mr-1">home</span>
                Home
              </a>
            </li>
            <li>
              <div className="flex items-center">
                <span className="material-symbols-outlined !text-[16px] text-slate-400 dark:text-[#586e7a]">chevron_right</span>
                <a className="ms-1 text-sm font-medium text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white md:ms-2 transition-colors" href="#">Configurações</a>
              </div>
            </li>
            <li aria-current="page">
              <div className="flex items-center">
                <span className="material-symbols-outlined !text-[16px] text-slate-400 dark:text-[#586e7a]">chevron_right</span>
                <span className="ms-1 text-sm font-medium text-slate-900 dark:text-white md:ms-2">Conectores de Dados</span>
              </div>
            </li>
          </ol>
        </nav>

        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight text-slate-900 dark:text-white mb-2">Conectores de Dados</h1>
            <p className="text-slate-500 dark:text-[#92b7c9] text-lg max-w-2xl leading-relaxed">
              Gerencie as integrações de API para automação de relatórios, criação de tickets e envio de alertas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative w-full md:w-auto group">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-[#92b7c9] group-focus-within:text-primary">
                <span className="material-symbols-outlined">filter_list</span>
              </span>
              <select className="h-10 w-full md:w-48 appearance-none rounded-lg border border-slate-200 dark:border-[#233c48] bg-white dark:bg-[#192b33] pl-10 pr-8 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none cursor-pointer transition-shadow">
                <option>Todos os tipos</option>
                <option>Gestão de Projetos</option>
                <option>Comunicação</option>
                <option>ERP/Financeiro</option>
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-slate-400">
                <span className="material-symbols-outlined !text-[18px]">expand_more</span>
              </span>
            </div>
            <button className="flex items-center gap-2 bg-primary hover:bg-sky-600 text-white px-4 h-10 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-sky-500/20 active:scale-95 transform">
              <span className="material-symbols-outlined !text-[20px]">add</span>
              <span>Novo Conector</span>
            </button>
          </div>
        </div>

        {/* Connectors Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {connectors.map((connector) => (
            connector.status === 'editing' ? (
              <ConnectorEditor 
                key={connector.id} 
                connector={connector} 
                onCancel={() => handleCancel(connector.id)}
                onSave={() => handleSave(connector.id)}
              />
            ) : (
              <ConnectorCard 
                key={connector.id} 
                connector={connector} 
                onConfigure={handleConfigure} 
              />
            )
          ))}
        </div>
      </main>
    </>
  );
};

export default App;
