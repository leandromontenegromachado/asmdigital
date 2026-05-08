import React, { useEffect, useState } from 'react';
import { AlertTriangle, Bell, CheckCircle2, Clock, Flame, ListChecks, RefreshCw, ShieldAlert } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { ExecutiveDashboardSummary, getExecutiveDashboardSummary } from '../api/executiveDashboard';

const formatDateTime = (value: string) => new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
const formatDate = (value?: string | null) => (value ? new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR') : '-');

const MetricCard: React.FC<{ title: string; value: number; tone?: 'default' | 'warning' | 'danger'; icon: React.ReactNode }> = ({ title, value, tone = 'default', icon }) => {
  const toneClass = {
    default: 'border-slate-200 bg-white text-slate-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    danger: 'border-red-200 bg-red-50 text-red-900',
  }[tone];

  return (
    <article className={`rounded-xl border p-5 shadow-sm ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">{title}</p>
          <p className="mt-2 text-3xl font-black">{value}</p>
        </div>
        <div className="rounded-lg bg-white/80 p-2 text-slate-600 shadow-sm">{icon}</div>
      </div>
    </article>
  );
};

const ExecutiveDashboardPage: React.FC = () => {
  const [summary, setSummary] = useState<ExecutiveDashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await getExecutiveDashboardSummary());
    } catch {
      setError('Não foi possível carregar o dashboard executivo.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell>
      <Topbar title="Dashboard Executivo" subtitle="Resumo operacional de eventos gerenciais e pendências." />

      <div className="mb-4 flex justify-end">
        <button onClick={load} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-primary-dark">
          <RefreshCw className="h-4 w-4" />
          Atualizar
        </button>
      </div>

      {loading && <StateBlock tone="loading" title="Carregando" description="Buscando indicadores executivos..." />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}

      {!loading && !error && summary && (
        <div className="space-y-6">
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard title="Eventos hoje" value={summary.total_events_today} icon={<Bell className="h-5 w-5" />} />
            <MetricCard title="Eventos novos" value={summary.new_events} icon={<Clock className="h-5 w-5" />} />
            <MetricCard title="Eventos high" value={summary.high_events} tone="warning" icon={<Flame className="h-5 w-5" />} />
            <MetricCard title="Eventos critical" value={summary.critical_events} tone="danger" icon={<ShieldAlert className="h-5 w-5" />} />
            <MetricCard title="Pendências abertas" value={summary.open_pending_items} icon={<ListChecks className="h-5 w-5" />} />
            <MetricCard title="Pendências vencidas" value={summary.overdue_pending_items} tone="danger" icon={<AlertTriangle className="h-5 w-5" />} />
            <MetricCard title="Pendências escaladas" value={summary.escalated_pending_items} tone="warning" icon={<AlertTriangle className="h-5 w-5" />} />
            <MetricCard title="Rotinas com falha hoje" value={summary.failed_routines_today} tone="danger" icon={<CheckCircle2 className="h-5 w-5" />} />
          </section>

          <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Top projetos com mais eventos</h2>
              <div className="mt-4 space-y-3">
                {summary.top_projects_by_events.length === 0 && <p className="text-sm text-slate-500">Nenhum evento hoje.</p>}
                {summary.top_projects_by_events.map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span className="min-w-0 break-words text-sm font-semibold text-slate-700">{item.label}</span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-700">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Top responsáveis com mais pendências</h2>
              <div className="mt-4 space-y-3">
                {summary.top_responsibles_by_pending_items.length === 0 && <p className="text-sm text-slate-500">Nenhuma pendência atribuída.</p>}
                {summary.top_responsibles_by_pending_items.map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span className="min-w-0 break-words text-sm font-semibold text-slate-700">{item.label}</span>
                    <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-700">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="text-lg font-bold text-slate-900">Eventos críticos</h2>
              </div>
              <div className="divide-y divide-slate-100">
                {summary.critical_event_list.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhum evento crítico.</p>}
                {summary.critical_event_list.map((event) => (
                  <article key={event.id} className="p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="break-words text-sm font-bold text-slate-900">{event.title}</h3>
                        <p className="mt-1 text-xs text-slate-500">{event.event_type} • {event.source_id || event.source_type || 'sem origem'} • {formatDateTime(event.created_at)}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${event.severity === 'critical' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>{event.severity}</span>
                    </div>
                  </article>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="text-lg font-bold text-slate-900">Pendências vencidas</h2>
              </div>
              <div className="divide-y divide-slate-100">
                {summary.overdue_pending_item_list.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhuma pendência vencida.</p>}
                {summary.overdue_pending_item_list.map((item) => (
                  <article key={item.id} className="p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="break-words text-sm font-bold text-slate-900">{item.title}</h3>
                        <p className="mt-1 text-xs text-slate-500">{item.responsible_name || 'Sem responsável'} • vence em {formatDate(item.due_date)}</p>
                      </div>
                      <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">{item.priority}</span>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
};

export default ExecutiveDashboardPage;
