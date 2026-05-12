import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { StatCard, StatData } from '../components/StatCard';
import { ConnectorCard, ConnectorStatus } from '../components/ConnectorCard';
import { AlertItem, AlertItemData } from '../components/AlertItem';
import { TimelineItem, AutomationTask } from '../components/TimelineItem';
import { DashboardSummary, getDashboardSummary } from '../api/dashboard';

const connectorProviders: ConnectorStatus['provider'][] = ['aws', 'azure', 'slack', 'jira', 'servicenow'];
const connectorTypes: ConnectorStatus['type'][] = ['cloud', 'chat', 'task', 'db'];
const alertTypes: AlertItemData['type'][] = ['critical', 'warning', 'success'];

const formatLastUpdate = (value?: string) => {
  if (!value) return '-';
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
};

const formatTimeAgo = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  if (Number.isNaN(diffMs)) return '-';
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
  if (diffMinutes < 1) return 'agora';
  if (diffMinutes < 60) return `${diffMinutes} min atrás`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h atrás`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d atrás`;
};

const buildStats = (summary?: DashboardSummary): StatData[] => {
  const stats = summary?.stats;
  const notificationDelta = (stats?.notifications_today || 0) - (stats?.notifications_yesterday || 0);
  const inactiveConnectors = Math.max((stats?.total_connectors || 0) - (stats?.active_connectors || 0), 0);

  return [
    {
      title: 'Conectores Ativos',
      value: stats?.active_connectors ?? 0,
      total: `/${stats?.total_connectors ?? 0}`,
      trend: inactiveConnectors ? `${inactiveConnectors} inativo(s)` : 'Tudo ativo',
      trendDirection: inactiveConnectors ? 'down' : 'neutral',
      icon: 'cable',
    },
    {
      title: 'Notificações Hoje',
      value: stats?.notifications_today ?? 0,
      trend: `${notificationDelta >= 0 ? '+' : ''}${notificationDelta} vs ontem`,
      trendDirection: notificationDelta > 0 ? 'up' : notificationDelta < 0 ? 'down' : 'neutral',
      icon: 'bell',
    },
    {
      title: 'Relatórios Pendentes',
      value: stats?.pending_reports ?? 0,
      trend: `${stats?.pending_reports ?? 0} em aberto`,
      trendDirection: (stats?.pending_reports || 0) > 0 ? 'down' : 'neutral',
      icon: 'file',
    },
    {
      title: 'Rotinas Ativas',
      value: stats?.active_automations ?? 0,
      trend: 'Agendadas',
      trendDirection: 'neutral',
      icon: 'star',
      highlight: true,
    },
  ];
};

const DashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardSummary();
      setSummary(data);
    } catch {
      setError('Não foi possível carregar os dados reais da visão geral.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const dashboardStats = useMemo(() => buildStats(summary), [summary]);

  const connectors: ConnectorStatus[] = useMemo(
    () =>
      (summary?.connectors || []).map((connector) => ({
        id: connector.id,
        name: connector.name,
        status: connector.status === 'offline' ? 'offline' : 'online',
        type: connectorTypes.includes(connector.type as ConnectorStatus['type']) ? (connector.type as ConnectorStatus['type']) : 'cloud',
        provider: connectorProviders.includes(connector.provider as ConnectorStatus['provider']) ? (connector.provider as ConnectorStatus['provider']) : 'aws',
      })),
    [summary]
  );

  const recentAlerts: AlertItemData[] = useMemo(
    () =>
      (summary?.recent_alerts || []).map((alert) => ({
        id: alert.id,
        title: alert.title,
        subtitle: alert.subtitle,
        type: alertTypes.includes(alert.type as AlertItemData['type']) ? (alert.type as AlertItemData['type']) : 'warning',
        tag: alert.tag,
        timeAgo: formatTimeAgo(alert.created_at),
      })),
    [summary]
  );

  const upcomingAutomations: AutomationTask[] = useMemo(
    () =>
      (summary?.upcoming_automations || []).map((task) => ({
        id: task.id,
        time: task.time,
        title: task.title,
        subtitle: task.subtitle,
        status: task.status === 'pending' ? 'pending' : 'upcoming',
        isNext: task.is_next,
      })),
    [summary]
  );

  return (
    <AppShell>
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">Visão Geral</h2>
          <p className="text-slate-500">Acompanhe o desempenho das suas automações em tempo real.</p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <span className="text-sm text-slate-500 font-medium">Última atualização: {formatLastUpdate(summary?.generated_at)}</span>
          <button
            onClick={loadDashboard}
            disabled={loading}
            className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-200 hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-70 transition-colors"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
            <span>{loading ? 'Atualizando...' : 'Atualizar dados'}</span>
          </button>
        </div>
      </header>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{error}</div>}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {dashboardStats.map((stat, index) => (
          <StatCard key={index} data={stat} />
        ))}
      </section>

      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-slate-900">Status dos Conectores</h3>
          <a href="/connectors" className="text-sm font-medium text-primary hover:text-primary-dark hover:underline transition-all">
            Ver todos
          </a>
        </div>
        <div className="flex flex-wrap gap-3">
          {connectors.map((connector) => (
            <ConnectorCard key={connector.id} connector={connector} />
          ))}
          {!loading && connectors.length === 0 && <p className="text-sm text-slate-500">Nenhum conector cadastrado.</p>}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900">Alertas Recentes</h3>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            {recentAlerts.map((alert) => (
              <AlertItem key={alert.id} alert={alert} />
            ))}
            {!loading && recentAlerts.length === 0 && <p className="p-4 text-sm text-slate-500">Nenhuma notificação recente encontrada.</p>}
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h3 className="text-lg font-bold text-slate-900">Próximas Automações</h3>
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm h-full flex flex-col">
            <div className="relative flex flex-col gap-0 border-l border-slate-200 ml-2 flex-1">
              {upcomingAutomations.map((task, index) => (
                <TimelineItem key={task.id} task={task} isLast={index === upcomingAutomations.length - 1} />
              ))}
              {!loading && upcomingAutomations.length === 0 && <p className="pl-6 text-sm text-slate-500">Nenhuma automação agendada.</p>}
            </div>
            <a
              href="/routines"
              className="mt-6 w-full rounded-lg border border-slate-200 bg-white py-2.5 text-center text-sm font-bold text-slate-600 hover:bg-slate-50 hover:text-primary transition-colors shadow-sm"
            >
              Ver Agenda Completa
            </a>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default DashboardPage;
