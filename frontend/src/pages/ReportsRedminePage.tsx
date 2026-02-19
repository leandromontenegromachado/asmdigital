import React, { useEffect, useState } from 'react';
import { Download, Play } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { Table } from '../components/Table';
import { Toasts, ToastItem } from '../components/Toasts';
import { listConnectors, listRedmineQueries, Connector, RedmineQuery } from '../api/connectors';
import { generateRedmineReport, getReport, exportReportCsv, exportReportPdf, ReportDetail } from '../api/reports';

const ReportsRedminePage: React.FC = () => {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [connectorId, setConnectorId] = useState<number | null>(null);
  const [projectIds, setProjectIds] = useState('');
  const [queryId, setQueryId] = useState('');
  const [queryUrl, setQueryUrl] = useState('');
  const [queries, setQueries] = useState<RedmineQuery[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(false);
  const [queriesProjectId, setQueriesProjectId] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [statusId, setStatusId] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const getConnectorProjectIds = (id: number | null) => {
    if (!id) return [];
    const connector = connectors.find((item) => item.id === id);
    const raw = connector?.config_json?.project_ids;
    if (!Array.isArray(raw)) return [];
    return raw.map((item: unknown) => String(item).trim()).filter(Boolean);
  };

  const loadConnectors = async () => {
    const data = await listConnectors();
    setConnectors(data);
    if (data.length && !connectorId) {
      setConnectorId(data[0].id);
    }
  };

  useEffect(() => {
    loadConnectors();
  }, []);

  useEffect(() => {
    if (!connectorId || !connectors.length) return;
    const connectorProjects = getConnectorProjectIds(connectorId);
    if (!connectorProjects.length) return;
    const joined = connectorProjects.join(', ');
    setProjectIds(joined);
    setQueriesProjectId(normalizeProjectId(connectorProjects[0]));
  }, [connectorId, connectors]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((items) => [...items, { id, ...toast }]);
    setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id));
    }, 3500);
  };

  const parseQueryUrl = (value: string) => {
    try {
      const url = new URL(value.trim());
      const search = url.searchParams;
      const qid = search.get('query_id') || '';
      const parts = url.pathname.split('/').filter(Boolean);
      const projectIndex = parts.indexOf('projects');
      const projectKey = projectIndex >= 0 && parts.length > projectIndex + 1 ? parts[projectIndex + 1] : '';
      return { queryId: qid, projectId: projectKey };
    } catch (err) {
      return { queryId: '', projectId: '' };
    }
  };

  const normalizeProjectId = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return '';
    if (/^\d+$/.test(trimmed)) return trimmed;
    return trimmed.toLowerCase();
  };

  const buildQueryUrl = (projectId: string, qid: string) => {
    const connector = connectors.find((item) => item.id === connectorId);
    const baseUrl = connector?.config_json?.base_url?.replace(/\/$/, '');
    const normalizedProject = normalizeProjectId(projectId);
    if (!baseUrl || !normalizedProject || !qid) return '';
    return `${baseUrl}/projects/${normalizedProject}/issues?query_id=${qid}`;
  };

  const handleGenerate = async () => {
    let nextQueryId = queryId.trim();
    let nextProjectIds = projectIds.trim();
    if (queryUrl.trim()) {
      const parsed = parseQueryUrl(queryUrl);
      if (!nextQueryId && parsed.queryId) nextQueryId = parsed.queryId;
      if (!nextProjectIds && parsed.projectId) nextProjectIds = parsed.projectId;
    }
    if (!nextProjectIds && queriesProjectId) {
      nextProjectIds = queriesProjectId;
    }

    if (!connectorId || !startDate || !endDate || (!nextProjectIds && !nextQueryId)) {
      setError('Preencha conector, periodo e projetos ou query.');
      return;
    }
    setLoading(true);
    setError(null);
    pushToast({ title: 'Relatorio em geracao', description: 'Aguarde a conclusao.', tone: 'info' });
    try {
      const payload = {
        connector_id: connectorId,
        project_ids: nextProjectIds
          .split(',')
          .map((item) => normalizeProjectId(item))
          .filter(Boolean),
        query_id: nextQueryId || undefined,
        start_date: startDate,
        end_date: endDate,
        status_id: statusId || undefined,
      };
      const generated = await generateRedmineReport(payload);
      const detail = await getReport(generated.id, { page: 1, page_size: 10, q: query || undefined });
      setReport(detail);
      setPage(1);
      pushToast({ title: 'Relatorio concluido', description: 'Dados carregados com sucesso.', tone: 'success' });
    } catch (err) {
      setError('Falha ao gerar relatorio.');
      pushToast({ title: 'Falha ao gerar relatorio', description: 'Verifique os filtros e tente novamente.', tone: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (nextPage: number) => {
    if (!report) return;
    const detail = await getReport(report.report.id, { page: nextPage, page_size: report.page_size, q: query || undefined });
    setReport(detail);
    setPage(nextPage);
  };

  const handleLoadQueries = async () => {
    if (!connectorId) return;
    setLoadingQueries(true);
    try {
      const primaryProject = projectIds
        .split(',')
        .map((item) => normalizeProjectId(item))
        .filter(Boolean)[0];
      const data = await listRedmineQueries(connectorId, primaryProject);
      setQueries(data);
      setQueriesProjectId(primaryProject || '');
      if (!data.length) {
        pushToast({ title: 'Nenhuma query encontrada', description: 'Verifique o projeto selecionado.', tone: 'info' });
      }
    } catch (err) {
      const message =
        (err as any)?.response?.data?.detail ||
        (err as any)?.message ||
        'Falha ao carregar queries do Redmine.';
      setError(String(message));
      pushToast({ title: 'Erro ao carregar consultas', description: String(message), tone: 'error' });
    } finally {
      setLoadingQueries(false);
    }
  };

  const handleParseUrl = () => {
    if (!queryUrl.trim()) return;
    const parsed = parseQueryUrl(queryUrl);
    if (!parsed.queryId && !parsed.projectId) {
      setError('URL invalida para extracao de query_id.');
      return;
    }
    if (parsed.queryId) setQueryId(parsed.queryId);
    if (parsed.projectId && !projectIds.trim()) setProjectIds(parsed.projectId);
  };

  const handleExport = async () => {
    if (!report) return;
    const response = await exportReportCsv(report.report.id);
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `report-${report.report.id}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleExportPdf = async () => {
    if (!report) return;
    const response = await exportReportPdf(report.report.id);
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `report-${report.report.id}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <AppShell>
      <Topbar title="Relatorio Redmine" subtitle="Gere relatorios consolidados e exporte para CSV ou PDF." />

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Conector</label>
            <select
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={connectorId ?? ''}
              onChange={(e) => {
                const nextId = Number(e.target.value);
                setConnectorId(nextId);
              }}
            >
              {connectors.map((connector) => (
                <option key={connector.id} value={connector.id}>
                  {connector.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Projetos (IDs)</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              placeholder="asm-dem ou 1,2,3"
              value={projectIds}
              onChange={(e) => setProjectIds(e.target.value)}
            />
            <span className="text-xs text-slate-500">Preenchido automaticamente a partir do conector selecionado.</span>
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Inicio</label>
            <input
              type="date"
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Fim</label>
            <input
              type="date"
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Status</label>
            <select
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={statusId}
              onChange={(e) => setStatusId(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="open">Abertos</option>
              <option value="closed">Fechados</option>
            </select>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Query ID</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              placeholder="8117"
              value={queryId}
              onChange={(e) => setQueryId(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2 md:col-span-2">
            <label className="text-sm font-semibold text-slate-700">URL da Query</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              placeholder="https://redmine.../projects/asm-dem/issues?query_id=8117"
              value={queryUrl}
              onChange={(e) => setQueryUrl(e.target.value)}
              onBlur={handleParseUrl}
            />
            <span className="text-xs text-slate-500">Ao sair do campo, a URL tenta preencher Query ID e Projeto.</span>
          </div>
        </div>
        <div className="mt-4 flex flex-col gap-2 min-w-0">
          <label className="text-sm font-semibold text-slate-700">Consultas salvas no Redmine</label>
          <div className="flex flex-col gap-2 md:flex-row md:items-center min-w-0">
            <select
              className="flex-1 min-w-0 rounded-lg border border-slate-200 px-3 py-2 truncate"
              value={queryId}
              onChange={(e) => {
                const nextId = e.target.value;
                setQueryId(nextId);
                if (queriesProjectId) {
                  setProjectIds(queriesProjectId);
                }
                if (nextId) {
                  const primaryProject =
                    projectIds
                      .split(',')
                      .map((item) => normalizeProjectId(item))
                      .filter(Boolean)[0] || queriesProjectId;
                  const built = buildQueryUrl(primaryProject, nextId);
                  if (built) setQueryUrl(built);
                  if (!primaryProject) {
                    pushToast({
                      title: 'Informe o projeto',
                      description: 'Para usar consulta salva, preencha o Projeto (ID/identificador).',
                      tone: 'info',
                    });
                  }
                }
              }}
              title={queries.find((item) => String(item.id) === String(queryId))?.name || ''}
            >
              <option value="">Selecione</option>
              {queries.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleLoadQueries}
              className="whitespace-nowrap rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700"
              disabled={loadingQueries || !connectorId}
            >
              {loadingQueries ? 'Carregando...' : 'Carregar'}
            </button>
          </div>
          <span className="text-xs text-slate-500">
            Escolha uma consulta salva ou preencha Projeto + Query ID. Nao precisa preencher os dois.
          </span>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={handleGenerate}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white shadow-lg shadow-blue-200 hover:bg-primary-dark"
            disabled={loading}
          >
            <Play size={16} />
            {loading ? 'Gerando...' : 'Gerar relatorio'}
          </button>
          {report && (
            <>
              <button
                onClick={handleExport}
                className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                <Download size={16} />
                Exportar CSV
              </button>
              <button
                onClick={handleExportPdf}
                className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                <Download size={16} />
                Exportar PDF
              </button>
            </>
          )}
          <div className="flex-1" />
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Buscar..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSearch(1);
              }
            }}
          />
        </div>
        {loading && <p className="mt-3 text-xs font-semibold text-blue-600">Gerando relatorio, aguarde...</p>}
      </section>

      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {!report && !error && <StateBlock tone="empty" title="Nenhum relatorio gerado" description="Preencha os filtros e gere o relatorio." />}

      {report && (
        <section className="flex flex-col gap-4">
          <Table
            columns={[
              { key: 'cliente', label: 'Cliente' },
              { key: 'sistema', label: 'Sistema' },
              { key: 'entrega', label: 'Entrega' },
              { key: 'source_ref', label: 'source_ref' },
              { key: 'source_url', label: 'source_url' },
            ]}
            data={report.rows}
            emptyMessage="Nenhum registro encontrado para o periodo."
          />
          <div className="flex items-center justify-between text-sm text-slate-500">
            <span>
              Pagina {report.page} de {Math.max(1, Math.ceil(report.total / report.page_size))}
            </span>
            <div className="flex gap-2">
              <button
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => handleSearch(page - 1)}
              >
                Anterior
              </button>
              <button
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 disabled:opacity-50"
                disabled={page >= Math.max(1, Math.ceil(report.total / report.page_size))}
                onClick={() => handleSearch(page + 1)}
              >
                Proxima
              </button>
            </div>
          </div>
        </section>
      )}
      <Toasts items={toasts} />
    </AppShell>
  );
};

export default ReportsRedminePage;
