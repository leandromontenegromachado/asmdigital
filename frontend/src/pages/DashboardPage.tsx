import React from 'react';
import { RefreshCw } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { StatCard, StatData } from '../components/StatCard';
import { ConnectorCard, ConnectorStatus } from '../components/ConnectorCard';
import { AlertItem, AlertItemData } from '../components/AlertItem';
import { TimelineItem, AutomationTask } from '../components/TimelineItem';

const DASHBOARD_STATS: StatData[] = [
  {
    title: 'Conectores Ativos',
    value: '12',
    total: '/15',
    trend: 'Estável',
    trendDirection: 'neutral',
    icon: 'cable',
  },
  {
    title: 'Alertas Enviados (Hoje)',
    value: '342',
    trend: '+12%',
    trendDirection: 'up',
    icon: 'bell',
  },
  {
    title: 'Relatórios Pendentes',
    value: '3',
    trend: '-2 vs ontem',
    trendDirection: 'down',
    icon: 'file',
  },
  {
    title: 'Economia de Tempo (IA)',
    value: '14h',
    trend: '+2.5h',
    trendDirection: 'up',
    icon: 'star',
    highlight: true,
  },
];

const CONNECTORS: ConnectorStatus[] = [
  { id: '1', name: 'AWS', status: 'online', type: 'cloud', provider: 'aws' },
  { id: '2', name: 'Azure', status: 'online', type: 'cloud', provider: 'azure' },
  { id: '3', name: 'Slack', status: 'offline', type: 'chat', provider: 'slack' },
  { id: '4', name: 'Jira', status: 'online', type: 'task', provider: 'jira' },
  { id: '5', name: 'ServiceNow', status: 'online', type: 'db', provider: 'servicenow' },
];

const RECENT_ALERTS: AlertItemData[] = [
  {
    id: '1',
    title: 'Erro de Backup no Servidor DB-01',
    subtitle: 'Falha na conexão TCP/IP • Cluster A',
    type: 'critical',
    timeAgo: '10 min atrás',
    tag: 'Crítico',
  },
  {
    id: '2',
    title: 'Uso de CPU elevado',
    subtitle: 'Instância i-034af acima de 85% por 5m',
    type: 'warning',
    timeAgo: '25 min atrás',
    tag: 'Atenção',
  },
  {
    id: '3',
    title: 'Deploy automático concluído',
    subtitle: 'Release v2.4.1 em produção',
    type: 'success',
    timeAgo: '1h atrás',
    tag: 'Sucesso',
  },
];

const UPCOMING_AUTOMATIONS: AutomationTask[] = [
  {
    id: '1',
    time: '14:00',
    title: 'Gerar Relatório Semanal',
    subtitle: 'Enviar para Gestão de TI',
    status: 'upcoming',
    isNext: true,
  },
  {
    id: '2',
    time: '14:30',
    title: 'Limpeza de Cache',
    subtitle: 'Servidores de Aplicação',
    status: 'pending',
  },
  {
    id: '3',
    time: '16:00',
    title: 'Sincronização LDAP',
    subtitle: 'Atualização de usuários',
    status: 'pending',
  },
  {
    id: '4',
    time: '18:00',
    title: 'Verificação de Segurança',
    subtitle: 'Scan de vulnerabilidades',
    status: 'pending',
  },
];

const DashboardPage: React.FC = () => {
  return (
    <AppShell>
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

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {DASHBOARD_STATS.map((stat, index) => (
          <StatCard key={index} data={stat} />
        ))}
      </section>

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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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

        <div className="flex flex-col gap-4">
          <h3 className="text-lg font-bold text-slate-900">Próximas Automações</h3>
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm h-full flex flex-col">
            <div className="relative flex flex-col gap-0 border-l border-slate-200 ml-2 flex-1">
              {UPCOMING_AUTOMATIONS.map((task, index) => (
                <TimelineItem key={task.id} task={task} isLast={index === UPCOMING_AUTOMATIONS.length - 1} />
              ))}
            </div>
            <button className="mt-6 w-full rounded-lg border border-slate-200 bg-white py-2.5 text-sm font-bold text-slate-600 hover:bg-slate-50 hover:text-primary transition-colors shadow-sm">
              Ver Agenda Completa
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default DashboardPage;
