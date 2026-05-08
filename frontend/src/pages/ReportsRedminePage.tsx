import React, { useEffect, useState } from 'react';
import { Download, Play } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { Table } from '../components/Table';
import { Toasts, ToastItem } from '../components/Toasts';
import { listConnectors, listRedmineQueries, Connector, RedmineQuery } from '../api/connectors';
import { generateRedmineReport, getReport, exportReportCsv, exportReportPdf, ReportDetail } from '../api/reports';
import { runPromptReportTemplate } from '../api/promptReports';

const ReportsRedminePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [editablePrompt, setEditablePrompt] = useState('');
  const [rerunning, setRerunning] = useState(false);
  const reportIdParam = searchParams.get('report_id');
  const isViewingExistingReport = Boolean(reportIdParam);

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
    if (data.length && !connectorId && !isViewingExistingReport) {
      const redmineConnector = data.find((item) => item.type === 'redmine');
      setConnectorId((redmineConnector || data[0]).id);
    }
  };

  useEffect(() => {
    loadConnectors();
  }, []);

  useEffect(() => {
    const reportId = Number(reportIdParam);
    if (!reportIdParam || !Number.isFinite(reportId) || reportId <= 0) {
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    getReport(reportId, { page: 1, page_size: 10 })
      .then((detail) => {
        if (!active) return;
        setReport(detail);
        setPage(1);
        applyReportParams(detail);
        setEditablePrompt(String(detail.report.params_json?.prompt_used || ''));
        pushToast({ title: 'Relatorio carregado', description: `Exibindo relatorio #${reportId}.`, tone: 'success' });
      })
      .catch(() => {
        if (!active) return;
        setError(`Nao foi possivel carregar o relatorio #${reportId}.`);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [reportIdParam]);

  useEffect(() => {
    if (isViewingExistingReport) return;
    if (!connectorId || !connectors.length) return;
    const connectorProjects = getConnectorProjectIds(connectorId);
    if (!connectorProjects.length) return;
    const joined = connectorProjects.join(', ');
    setProjectIds(joined);
    setQueriesProjectId(normalizeProjectId(connectorProjects[0]));
  }, [connectorId, connectors, isViewingExistingReport]);

  useEffect(() => {
    if (!report || !connectors.length) return;
    applyReportParams(report);
  }, [connectors]);

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

  const buildQueryUrl = (_projectId: string, qid: string) => {
    const connector = connectors.find((item) => item.id === connectorId);
    const baseUrl = connector?.config_json?.base_url?.replace(/\/$/, '');
    if (!baseUrl || !qid) return '';
    return `${baseUrl}/issues?query_id=${qid}`;
  };

  const setQueryIdAndUrl = (value: string) => {
    setQueryId(value);
    const built = buildQueryUrl('', value.trim());
    setQueryUrl(built);
  };

  const applyReportParams = (detail: ReportDetail) => {
    const params = detail.report.params_json || {};
    const nextConnectorId = Number(params.connector_id);
    const nextProjects = Array.isArray(params.project_ids)
      ? params.project_ids.map((item: unknown) => String(item)).join(', ')
      : '';
    const nextQueryId = params.query_id ? String(params.query_id) : '';
    const nextStart = params.start_date ? String(params.start_date) : '';
    const nextEnd = params.end_date ? String(params.end_date) : '';
    const nextStatus = params.status_id ? String(params.status_id) : '';

    if (Number.isFinite(nextConnectorId) && nextConnectorId > 0) {
      setConnectorId(nextConnectorId);
    }
    setProjectIds(nextProjects);
    setQueriesProjectId(nextProjects.split(',').map((item) => normalizeProjectId(item)).filter(Boolean)[0] || '');
    setQueryId(nextQueryId);
    setStartDate(nextStart);
    setEndDate(nextEnd);
    setStatusId(nextStatus);
    setEditablePrompt(String(params.prompt_used || ''));

    const connector = connectors.find((item) => item.id === nextConnectorId);
    const baseUrl = connector?.config_json?.base_url?.replace(/\/$/, '');
    setQueryUrl(baseUrl && nextQueryId ? `${baseUrl}/issues?query_id=${nextQueryId}` : '');
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

  const handleRerunFromPrompt = async () => {
    if (!report) return;
    const templateId = Number(report.report.params_json?.template_id);
    const promptOverride = editablePrompt.trim();
    if (!Number.isFinite(templateId) || templateId <= 0) {
      setError('Este relatorio nao tem template vinculado para executar novamente.');
      return;
    }
    if (!promptOverride) {
      setError('Informe o prompt antes de executar novamente.');
      return;
    }

    setRerunning(true);
    setLoading(true);
    setError(null);
    pushToast({ title: 'Executando novamente', description: 'Gerando um novo relatorio com o prompt editado.', tone: 'info' });
    try {
      const result = await runPromptReportTemplate(templateId, promptOverride);
      const detail = await getReport(result.report_id, { page: 1, page_size: report.page_size || 10 });
      setReport(detail);
      setPage(1);
      applyReportParams(detail);
      setSearchParams({ report_id: String(result.report_id) });
      pushToast({ title: 'Novo relatorio gerado', description: `Relatorio #${result.report_id} carregado.`, tone: 'success' });
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Falha ao executar novamente com o prompt editado.';
      setError(String(detail));
      pushToast({ title: 'Falha ao executar novamente', description: String(detail), tone: 'error' });
    } finally {
      setRerunning(false);
      setLoading(false);
    }
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

  const hasRedmineDetails = Boolean(report?.rows.some((row) => row.raw_json));
  type ReportDisplayRow = ReportDetail['rows'][number] & {
    assunto: string;
    status_redmine: string;
    responsavel: string;
    data_prevista: string;
    alterado_em: string;
    dias_atraso: string | number;
    prioridade: string;
    tipo: string;
    autor: string;
    percentual_concluido: string | number;
  };
  const promptColumnMap: Record<string, { key: keyof ReportDisplayRow; label: string }> = {
    source_ref: { key: 'source_ref', label: 'ID' },
    subject: { key: 'assunto', label: 'Titulo' },
    assigned_to: { key: 'responsavel', label: 'Atribuido para' },
    due_date: { key: 'data_prevista', label: 'Data prevista' },
    days_overdue: { key: 'dias_atraso', label: 'Dias em atraso' },
    updated_on: { key: 'alterado_em', label: 'Alterado em' },
    status: { key: 'status_redmine', label: 'Status' },
    priority: { key: 'prioridade', label: 'Prioridade' },
    tracker: { key: 'tipo', label: 'Tipo' },
    author: { key: 'autor', label: 'Autor' },
    done_ratio: { key: 'percentual_concluido', label: '% concluido' },
  };
  const promptColumns = Array.isArray(report?.report.params_json?.prompt_options?.columns)
    ? report?.report.params_json?.prompt_options?.columns
        .map((item: any) => {
          const mapped = promptColumnMap[String(item?.key || '')];
          return mapped ? { ...mapped, label: String(item?.label || mapped.label) } : null;
        })
        .filter(Boolean)
    : null;
  const reportColumns: { key: keyof ReportDisplayRow; label: string }[] = hasRedmineDetails
    ? (promptColumns?.length ? promptColumns : [
        { key: 'source_ref', label: 'ID' },
        { key: 'assunto', label: 'Titulo' },
        { key: 'responsavel', label: 'Atribuido para' },
        { key: 'data_prevista', label: 'Data prevista' },
        { key: 'alterado_em', label: 'Alterado em' },
        { key: 'dias_atraso', label: 'Dias atraso' },
        { key: 'status_redmine', label: 'Status' },
      ])
    : [
        { key: 'cliente', label: 'Cliente' },
        { key: 'sistema', label: 'Sistema' },
        { key: 'entrega', label: 'Entrega' },
        { key: 'source_ref', label: 'source_ref' },
        { key: 'source_url', label: 'source_url' },
      ];
  const reportRows: ReportDisplayRow[] = (report?.rows || []).map((row) => ({
    ...row,
    assunto: row.raw_json?.subject || '',
    status_redmine: row.raw_json?.status || '',
    responsavel: row.raw_json?.assigned_to || '',
    data_prevista: row.raw_json?.due_date || '',
    alterado_em: row.raw_json?.updated_on || '',
    dias_atraso: row.raw_json?.days_overdue ?? '',
    prioridade: row.raw_json?.priority || '',
    tipo: row.raw_json?.tracker || '',
    autor: row.raw_json?.author || '',
    percentual_concluido: row.raw_json?.done_ratio ?? '',
  }));
  const reportParams = report?.report.params_json || {};
  const reportErrors = Array.isArray(reportParams.errors) ? reportParams.errors.filter(Boolean) : [];

  return (
    <AppShell>
      <Topbar
        title={isViewingExistingReport ? `Resultado do Relatorio #${report?.report.id || reportIdParam}` : 'Relatorio Redmine'}
        subtitle={isViewingExistingReport ? 'Resultado gerado a partir do prompt/template.' : 'Gere relatorios consolidados e exporte para CSV ou PDF.'}
      />

      {isViewingExistingReport && report && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Status</p>
              <p className="mt-1 text-sm font-bold text-slate-800">{report.report.status}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Projeto</p>
              <p className="mt-1 text-sm font-bold text-slate-800">
                {Array.isArray(reportParams.project_ids) ? reportParams.project_ids.join(', ') : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Query</p>
              <p className="mt-1 text-sm font-bold text-slate-800">{reportParams.query_id || '-'}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Periodo</p>
              <p className="mt-1 text-sm font-bold text-slate-800">
                {reportParams.start_date || '-'} a {reportParams.end_date || '-'}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500">Registros</p>
              <p className="mt-1 text-sm font-bold text-slate-800">{reportParams.records ?? report.total}</p>
            </div>
          </div>
          {reportParams.prompt_used && (
            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-slate-800">Prompt usado</p>
                <button
                  type="button"
                  onClick={handleRerunFromPrompt}
                  disabled={rerunning || loading}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-white hover:bg-primary-dark disabled:opacity-60"
                >
                  <Play size={14} />
                  {rerunning ? 'Executando...' : 'Executar novamente'}
                </button>
              </div>
              <textarea
                className="mt-2 min-h-44 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800"
                value={editablePrompt}
                onChange={(e) => setEditablePrompt(e.target.value)}
              />
              <p className="mt-2 text-xs text-slate-500">
                Altere o prompt e execute novamente para gerar um novo relatorio.
              </p>
            </div>
          )}
          {reportErrors.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <p className="font-semibold">Execucao concluida com avisos</p>
              <ul className="mt-1 list-disc pl-5">
                {reportErrors.map((item: string, index: number) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
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
          </div>
        </section>
      )}

      {!isViewingExistingReport && (
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
              onChange={(e) => setQueryIdAndUrl(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2 md:col-span-2">
            <label className="text-sm font-semibold text-slate-700">URL da Query</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              placeholder="https://redmine.../issues?query_id=8117"
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
                setQueryIdAndUrl(nextId);
                if (queriesProjectId) {
                  setProjectIds(queriesProjectId);
                }
                if (nextId) {
                  const primaryProject =
                    projectIds
                      .split(',')
                      .map((item) => normalizeProjectId(item))
                      .filter(Boolean)[0] || queriesProjectId;
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
      )}

      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {!report && !error && <StateBlock tone="empty" title="Nenhum relatorio gerado" description="Preencha os filtros e gere o relatorio." />}

      {report && (
        <section className="flex flex-col gap-4">
          <Table
            columns={reportColumns}
            data={reportRows}
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
