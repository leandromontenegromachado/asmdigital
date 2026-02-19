import React from 'react';
import { Sidebar } from './components/Sidebar';
import { StatCard } from './components/StatCard';
import { ConnectorCard } from './components/ConnectorCard';
import { AlertItem } from './components/AlertItem';
import { TimelineItem } from './components/TimelineItem';
import { RefreshCw } from 'lucide-react';
import { DASHBOARD_STATS, CONNECTORS, RECENT_ALERTS, UPCOMING_AUTOMATIONS } from './constants';

function App() {
  return (
    <div className="flex h-screen w-full bg-background-main">
      <Sidebar />
      
      <main className="flex-1 flex flex-col overflow-y-auto">
        <div className="mx-auto w-full max-w-7xl p-4 md:p-6 lg:p-8 flex flex-col gap-8">
          
          {/* Header */}
          <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex flex-col gap-1">
              <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">Visão Geral</h2>
              <p className="text-slate-500">Acompanhe o desempenho das suas automações em tempo real.</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-500 font-medium">Última atualização: Hoje, 14:00</span>
              <button className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-200 hover:bg-primary-dark transition-colors">
                <RefreshCw size={18} />
                <span>Atualizar dados</span>
              </button>
            </div>
          </header>

          {/* Stats Grid */}
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {DASHBOARD_STATS.map((stat, index) => (
              <StatCard key={index} data={stat} />
            ))}
          </section>

          {/* Connectors Section */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-900">Status dos Conectores</h3>
              <a href="#" className="text-sm font-medium text-primary hover:text-primary-dark hover:underline transition-all">
                Ver todos
              </a>
            </div>
            <div className="flex flex-wrap gap-3">
              {CONNECTORS.map((connector) => (
                <ConnectorCard key={connector.id} connector={connector} />
              ))}
            </div>
          </section>

          {/* Bottom Grid: Alerts & Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Recent Alerts */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900">Alertas Recentes</h3>
                <div className="flex gap-2">
                  <button className="text-xs font-bold text-slate-500 hover:text-primary transition-colors bg-white px-3 py-1 rounded-md border border-slate-200 shadow-sm">
                    Filtrar
                  </button>
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                {RECENT_ALERTS.map((alert) => (
                  <AlertItem key={alert.id} alert={alert} />
                ))}
              </div>
            </div>

            {/* Upcoming Automations Timeline */}
            <div className="flex flex-col gap-4">
              <h3 className="text-lg font-bold text-slate-900">Próximas Automações</h3>
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm h-full flex flex-col">
                <div className="relative flex flex-col gap-0 border-l border-slate-200 ml-2 flex-1">
                  {UPCOMING_AUTOMATIONS.map((task, index) => (
                    <TimelineItem 
                      key={task.id} 
                      task={task} 
                      isLast={index === UPCOMING_AUTOMATIONS.length - 1} 
                    />
                  ))}
                </div>
                <button className="mt-6 w-full rounded-lg border border-slate-200 bg-white py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50 hover:text-primary transition-colors shadow-sm">
                  Ver Agenda Completa
                </button>
              </div>
            </div>

          </div>

        </div>
      </main>
    </div>
  );
}

export default App;