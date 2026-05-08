import React, { useEffect, useState } from 'react';
import { Copy, Play, Plus, Save, Trash2, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { listConnectors, listRedmineQueries, Connector, RedmineQuery } from '../api/connectors';
import {
  createPromptReportTemplate,
  deletePromptReportTemplate,
  listPromptReportRuns,
  listPromptReportTemplates,
  PromptReportTemplate,
  runPromptReportTemplate,
  updatePromptReportTemplate,
} from '../api/promptReports';
import { Report } from '../api/reports';

type FormState = {
  name: string;
  connector_id: string;
  prompt_text: string;
  project_ids: string;
  status_id: string;
  query_id: string;
  start_date: string;
  end_date: string;
  schedule_enabled: boolean;
  schedule_time: string;
  schedule_days: string[];
};

const defaultForm: FormState = {
  name: '',
  connector_id: '',
  prompt_text: '',
  project_ids: '',
  status_id: '',
  query_id: '',
  start_date: '',
  end_date: '',
  schedule_enabled: false,
  schedule_time: '08:00',
  schedule_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
};

const WEEK_DAYS = [
  { value: 'mon', legacy: '1', label: 'Seg' },
  { value: 'tue', legacy: '2', label: 'Ter' },
  { value: 'wed', legacy: '3', label: 'Qua' },
  { value: 'thu', legacy: '4', label: 'Qui' },
  { value: 'fri', legacy: '5', label: 'Sex' },
  { value: 'sat', legacy: '6', label: 'Sab' },
  { value: 'sun', legacy: '0', label: 'Dom' },
];

const SCHEDULE_PRESETS = [
  { label: 'Diário', days: WEEK_DAYS.map((item) => item.value) },
  { label: 'Dias úteis', days: ['mon', 'tue', 'wed', 'thu', 'fri'] },
  { label: 'Toda sexta', days: ['fri'] },
  { label: 'Fim de semana', days: ['sat', 'sun'] },
];

const normalizeScheduleDay = (day: string) => {
  const normalized = day.trim().toLowerCase();
  const legacy = WEEK_DAYS.find((item) => item.legacy === normalized || item.value === normalized);
  return legacy?.value || normalized;
};

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const parseSchedule = (cron?: string | null, isEnabled?: boolean) => {
  const fallback = {
    schedule_enabled: Boolean(isEnabled && cron),
    schedule_time: '08:00',
    schedule_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
  };
  if (!cron) return fallback;
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return fallback;
  const [minute, hour, , , days] = parts;
  const parsedHour = hour.padStart(2, '0');
  const parsedMinute = minute.padStart(2, '0');
  const scheduleDays = days === '*' ? WEEK_DAYS.map((item) => item.value) : days.split(',').map(normalizeScheduleDay).filter(Boolean);
  return {
    schedule_enabled: Boolean(isEnabled),
    schedule_time: `${parsedHour}:${parsedMinute}`,
    schedule_days: scheduleDays.length ? scheduleDays : fallback.schedule_days,
  };
};

const templateToForm = (template: PromptReportTemplate): FormState => {
  const schedule = parseSchedule(template.schedule_cron, template.is_enabled);
  return {
    name: template.name,
    connector_id: String(template.connector_id),
    prompt_text: template.prompt_text,
    project_ids: Array.isArray(template.params_json?.project_ids) ? template.params_json.project_ids.join(', ') : '',
    status_id: template.params_json?.status_id || '',
    query_id: template.params_json?.query_id || '',
    start_date: template.params_json?.start_date || '',
    end_date: template.params_json?.end_date || '',
    ...schedule,
  };
};

const isPlaceholderProject = (projectId: string) => {
  const normalized = projectId.trim().toLowerCase();
  return (
    !normalized ||
    ['opcional', 'optional', 'projetomodelo', 'projeto-modelo', 'projectmodel', 'project-model'].includes(normalized) ||
    normalized === 'padrao_do_conector' ||
    normalized === 'padrao-do-conector' ||
    /^projeto\d*$/.test(normalized) ||
    /^project\d*$/.test(normalized)
  );
};

const connectorProjectIds = (connector?: Connector) => {
  const raw = connector?.config_json?.project_ids;
  if (!Array.isArray(raw)) return '';
  return raw
    .map((item) => String(item).trim().toLowerCase())
    .filter((item) => !isPlaceholderProject(item))
    .join(', ');
};

const inferOutputItems = (brief: string) => {
  const lowered = brief.toLowerCase();
  const items: string[] = [];
  if (lowered.includes('resumo')) items.push('Resumo conforme solicitado no objetivo');
  if (lowered.includes('risco') || lowered.includes('bloqueio')) items.push('Riscos e bloqueios identificados nos dados retornados');
  if (lowered.includes('tabela') || lowered.includes('campos') || lowered.includes('liste') || lowered.includes('listar')) {
    items.push('Tabela com as colunas citadas no objetivo');
  }
  if (lowered.includes('ordene') || lowered.includes('ordenar')) items.push('Ordenacao conforme criterio descrito no objetivo');
  if (lowered.includes('acao') || lowered.includes('acao') || lowered.includes('recomend')) {
    items.push('Acoes recomendadas apenas quando derivadas dos dados');
  }
  return items.length ? items : ['Resultado direto conforme o objetivo descrito', 'Tabela com os campos relevantes citados no prompt'];
};

const inferRules = (brief: string) => {
  const lowered = brief.toLowerCase();
  const rules = [
    'Nao inventar campos fora do retorno do Redmine.',
    'Declarar quando houver dados incompletos.',
  ];
  if (lowered.includes('atras') || lowered.includes('vencid') || lowered.includes('data prevista menor')) {
    rules.push('Considerar atrasado quando a data prevista for menor que a data de hoje e a demanda nao estiver fechada.');
  }
  if (lowered.includes('ordene') || lowered.includes('ordenar')) {
    rules.push('Respeitar a ordenacao solicitada no objetivo.');
  }
  return rules;
};

const buildPromptMarkdown = (form: FormState, brief: string) => {
  const objective = brief.trim() || 'Gerar relatorio operacional com dados do Redmine para suporte a decisao.';
  const projects = form.project_ids
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  const projectLine = projects.length ? projects.join(', ') : '{{projetos_do_conector}}';

  let periodLine = 'este mes';
  if (form.start_date && form.end_date) {
    periodLine = `de ${form.start_date} a ${form.end_date}`;
  } else if (form.start_date) {
    periodLine = `a partir de ${form.start_date}`;
  }

  const statusText =
    form.status_id === 'open'
      ? 'abertos'
      : form.status_id === 'closed'
      ? 'fechados'
      : 'todos os status';

  const queryLine = form.query_id.trim() || 'opcional';
  const outputItems = inferOutputItems(objective).map((item) => `- ${item}`).join('\n');
  const rules = inferRules(objective).map((item) => `- ${item}`).join('\n');

  return `# Objetivo
${objective}

## Fonte
- conector_id: ${form.connector_id || '{{CONECTOR_ID}}'}
- origem: redmine_mcp

## Escopo
- projetos: ${projectLine}
- status: ${statusText}
- periodo: ${periodLine}
- query_id: ${queryLine}

## Saida esperada
${outputItems}

## Regras
${rules}`;
};

const buildScheduleCron = (form: FormState) => {
  if (!form.schedule_enabled) return null;
  const [hour = '8', minute = '0'] = form.schedule_time.split(':');
  const normalizedHour = String(Number(hour));
  const normalizedMinute = String(Number(minute));
  const selectedDays = WEEK_DAYS.map((item) => item.value).filter((day) => form.schedule_days.includes(day));
  const days = selectedDays.length === WEEK_DAYS.length ? '*' : selectedDays.join(',');
  return `${normalizedMinute} ${normalizedHour} * * ${days || '*'}`;
};

const PromptReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [templates, setTemplates] = useState<PromptReportTemplate[]>([]);
  const [runs, setRuns] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(defaultForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [runPromptOverride, setRunPromptOverride] = useState('');
  const [promptBrief, setPromptBrief] = useState('');
  const [savedQueries, setSavedQueries] = useState<RedmineQuery[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [connectorsData, templatesData] = await Promise.all([
        listConnectors(),
        listPromptReportTemplates(),
      ]);
      setConnectors(connectorsData);
      setTemplates(templatesData);
      if (!selectedId && templatesData.length) {
        setSelectedId(templatesData[0].id);
        setForm(templateToForm(templatesData[0]));
      } else if (!selectedId && !templatesData.length) {
        const redmineConnector = connectorsData.find((connector) => connector.type === 'redmine') || connectorsData[0];
        setForm((prev) => ({
          ...prev,
          connector_id: redmineConnector ? String(redmineConnector.id) : '',
          project_ids: connectorProjectIds(redmineConnector),
        }));
      }
      if (!templatesData.length) {
        setRuns([]);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao carregar dados.');
    } finally {
      setLoading(false);
    }
  };

  const loadRuns = async (templateId: number) => {
    try {
      const data = await listPromptReportRuns(templateId, 20);
      setRuns(data);
    } catch {
      setRuns([]);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    loadRuns(selectedId);
  }, [selectedId]);

  const selectTemplate = (template: PromptReportTemplate) => {
    setSelectedId(template.id);
    setForm(templateToForm(template));
    setInfo(null);
    setError(null);
  };

  const resetForm = () => {
    const redmineConnector = connectors.find((connector) => connector.type === 'redmine') || connectors[0];
    setSelectedId(null);
    setForm({
      ...defaultForm,
      connector_id: redmineConnector ? String(redmineConnector.id) : '',
      project_ids: connectorProjectIds(redmineConnector),
    });
    setRuns([]);
    setRunPromptOverride('');
    setPromptBrief('');
    setInfo(null);
    setError(null);
  };

  const primaryProjectId = () =>
    form.project_ids
      .split(',')
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean)[0] || '';

  const handleLoadSavedQueries = async () => {
    const connectorId = Number(form.connector_id);
    if (!connectorId) {
      setError('Selecione um conector Redmine antes de carregar consultas.');
      return;
    }
    const connector = connectors.find((item) => item.id === connectorId);
    if (connector?.type !== 'redmine') {
      setError('Consultas salvas estao disponiveis apenas para conectores Redmine.');
      return;
    }
    setLoadingQueries(true);
    setError(null);
    try {
      const data = await listRedmineQueries(connectorId, primaryProjectId() || undefined);
      setSavedQueries(data);
      setInfo(data.length ? `${data.length} consultas salvas carregadas.` : 'Nenhuma consulta salva encontrada para este projeto.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao carregar consultas salvas do Redmine.');
      setSavedQueries([]);
    } finally {
      setLoadingQueries(false);
    }
  };

  const handleSelectSavedQuery = (queryId: string) => {
    setForm((prev) => ({ ...prev, query_id: queryId }));
    const query = savedQueries.find((item) => String(item.id) === queryId);
    if (query) {
      setInfo(`Consulta selecionada: ${query.name}`);
    }
  };

  const handleGeneratePrompt = () => {
    const generated = buildPromptMarkdown(form, promptBrief.trim());
    setForm((prev) => ({ ...prev, prompt_text: generated }));
    setInfo('Prompt em Markdown gerado no template.');
  };

  const handleConnectorChange = (connectorId: string) => {
    const connector = connectors.find((item) => String(item.id) === connectorId);
    setForm((prev) => ({
      ...prev,
      connector_id: connectorId,
      project_ids: prev.project_ids.trim() ? prev.project_ids : connectorProjectIds(connector),
    }));
  };

  const toggleScheduleDay = (day: string) => {
    setForm((prev) => {
      const scheduleDays = prev.schedule_days.includes(day)
        ? prev.schedule_days.filter((item) => item !== day)
        : [...prev.schedule_days, day];
      return { ...prev, schedule_days: scheduleDays };
    });
  };

  const applySchedulePreset = (days: string[]) => {
    setForm((prev) => ({ ...prev, schedule_days: days }));
  };

  const handleCopyPrompt = async () => {
    if (!form.prompt_text.trim()) {
            setError('Nao ha prompt para copiar.');
      return;
    }
    try {
      await navigator.clipboard.writeText(form.prompt_text);
      setInfo('Prompt copiado para a area de transferencia.');
    } catch {
            setError('Nao foi possivel copiar o prompt.');
    }
  };

  const buildPayload = () => ({
    name: form.name.trim(),
    connector_id: Number(form.connector_id),
    prompt_text: form.prompt_text.trim(),
    params_json: {
      project_ids: form.project_ids
        .split(',')
        .map((item) => item.trim().toLowerCase())
        .filter((item) => !isPlaceholderProject(item)),
      status_id: form.status_id.trim() || null,
      query_id: form.query_id.trim() || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    },
    schedule_cron: buildScheduleCron(form),
    is_enabled: form.schedule_enabled,
  });

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const payload = buildPayload();
      if (!payload.name || !payload.prompt_text || !payload.connector_id) {
        setError('Preencha nome, conector e prompt.');
        return;
      }
      if (selectedId) {
        const updated = await updatePromptReportTemplate(selectedId, payload);
        setTemplates((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        setForm(templateToForm(updated));
        setInfo('Template atualizado.');
      } else {
        const created = await createPromptReportTemplate(payload);
        setTemplates((prev) => [created, ...prev]);
        setSelectedId(created.id);
        setForm(templateToForm(created));
        setInfo('Template criado.');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao salvar template.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      await deletePromptReportTemplate(selectedId);
      const next = templates.filter((item) => item.id !== selectedId);
      setTemplates(next);
      if (next.length) {
        setSelectedId(next[0].id);
        setForm(templateToForm(next[0]));
      } else {
        resetForm();
      }
      setInfo('Template removido.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao remover template.');
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    if (!selectedId) {
      setError('Selecione um template para executar.');
      return;
    }
    setRunning(true);
    setError(null);
    setInfo(null);
    try {
      const payload = buildPayload();
      // Sync current form data before running to avoid stale template params on backend.
      const synced = await updatePromptReportTemplate(selectedId, payload);
      setTemplates((prev) => prev.map((item) => (item.id === synced.id ? synced : item)));
      setForm(templateToForm(synced));

      const promptOverride = runPromptOverride.trim() || form.prompt_text.trim() || undefined;
      const result = await runPromptReportTemplate(selectedId, promptOverride);
            setInfo(`Relatorio executado com sucesso. ID: ${result.report_id}`);
      await loadData();
      await loadRuns(selectedId);
      navigate(`/reports/redmine-deliveries?report_id=${result.report_id}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Falha ao executar template.';
      if (String(detail).includes('project_ids or query_id')) {
                setError('Defina "Projetos padrao (IDs)" ou "Query padrao", salve e execute novamente.');
      } else {
        setError(detail);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <AppShell>
      <Topbar
                title="Relatorios por Linguagem Natural"
                subtitle="Crie prompts reutilizaveis e execute relatorios sob demanda."
      />

      {loading && <StateBlock tone="loading" title="Carregando" description="Buscando templates e conectores..." />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {info && <StateBlock tone="empty" title="Sucesso" description={info} />}

      {!loading && (
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-1">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-800">Templates salvos</h2>
              <button
                onClick={resetForm}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700"
              >
                <Plus size={14} />
                Novo
              </button>
            </div>
            <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
              {templates.length === 0 && (
                <p className="text-xs text-slate-500">Nenhum template cadastrado.</p>
              )}
              {templates.map((item) => (
                <button
                  key={item.id}
                  onClick={() => selectTemplate(item)}
                  className={`w-full rounded-lg border px-3 py-2 text-left ${
                    selectedId === item.id ? 'border-blue-400 bg-blue-50' : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-800">{item.name}</p>
                <p className="text-xs text-slate-500">Ultima execucao: {formatDate(item.last_run_at)}</p>
                {item.next_run_at && <p className="text-xs text-slate-500">Proxima: {formatDate(item.next_run_at)}</p>}
              </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm xl:col-span-2">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-slate-800">
                {selectedId ? `Editar template #${selectedId}` : 'Novo template'}
              </h2>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleGeneratePrompt}
                  className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700"
                >
                  <Wand2 size={14} />
                  Gerar prompt Markdown
                </button>
                <button
                  type="button"
                  onClick={handleCopyPrompt}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700"
                >
                  <Copy size={14} />
                  Copiar prompt
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Nome</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Ex.: Entregas fechadas mensal"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Conector</label>
                <select
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.connector_id}
                  onChange={(e) => handleConnectorChange(e.target.value)}
                >
                  <option value="">Selecione</option>
                  {connectors.map((connector) => (
                    <option key={connector.id} value={connector.id}>
                      {connector.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <label className="text-xs font-semibold text-slate-700">Assistente IA (brief)</label>
                <textarea
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  rows={2}
                  value={promptBrief}
                  onChange={(e) => setPromptBrief(e.target.value)}
                                    placeholder="Descreva o que voce precisa: ex. mostrar bloqueios e riscos dos projetos de integracao."
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleGeneratePrompt}
                    className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700"
                  >
                    <Wand2 size={14} />
                    Gerar prompt Markdown
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyPrompt}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700"
                  >
                    <Copy size={14} />
                    Copiar prompt
                  </button>
                </div>
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <label className="text-xs font-semibold text-slate-700">Prompt</label>
                <textarea
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  rows={4}
                  value={form.prompt_text}
                  onChange={(e) => setForm((prev) => ({ ...prev, prompt_text: e.target.value }))}
                                    placeholder="Ex.: gerar relatorio dos ultimos 30 dias para projetos: asm-dem, asm-app com status fechado"
                />
                <p className="text-xs text-slate-500">
                  Entende expressoes como: "ultimos 30 dias", "este mes", "status fechado", "query_id 1234", "projetos: x, y".
                </p>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Projetos padrao (IDs)</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.project_ids}
                  onChange={(e) => setForm((prev) => ({ ...prev, project_ids: e.target.value }))}
                  placeholder="asm-dem, asm-app"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Query padrao</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.query_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, query_id: e.target.value }))}
                  placeholder="8117"
                />
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <label className="text-xs font-semibold text-slate-700">Consultas salvas do Redmine</label>
                <div className="flex flex-col gap-2 md:flex-row">
                  <select
                    className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2"
                    value={form.query_id}
                    onChange={(e) => handleSelectSavedQuery(e.target.value)}
                  >
                    <option value="">Selecione uma consulta salva</option>
                    {savedQueries.map((query) => (
                      <option key={query.id} value={query.id}>
                        #{query.id} - {query.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={handleLoadSavedQueries}
                    disabled={loadingQueries || !form.connector_id}
                    className="whitespace-nowrap rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50"
                  >
                    {loadingQueries ? 'Carregando...' : 'Carregar consultas'}
                  </button>
                </div>
                <p className="text-xs text-slate-500">
                  Carrega as consultas do projeto informado em Projetos padrao e preenche Query padrao com o ID escolhido.
                </p>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Status padrao</label>
                <select
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.status_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, status_id: e.target.value }))}
                >
                  <option value="">Todos</option>
                  <option value="open">Abertos</option>
                  <option value="closed">Fechados</option>
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Data inicio padrao</label>
                <input
                  type="date"
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.start_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, start_date: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Data fim padrao</label>
                <input
                  type="date"
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.end_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, end_date: e.target.value }))}
                />
              </div>
            </div>

            <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2">
                <input
                  id="schedule-enabled"
                  type="checkbox"
                  checked={form.schedule_enabled}
                  onChange={(e) => setForm((prev) => ({ ...prev, schedule_enabled: e.target.checked }))}
                />
                <label htmlFor="schedule-enabled" className="text-sm font-bold text-slate-800">
                  Agendar execucao automatica
                </label>
              </div>

              {form.schedule_enabled && (
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="flex flex-col gap-2">
                    <label className="text-xs font-semibold text-slate-700">Hora</label>
                    <input
                      type="time"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2"
                      value={form.schedule_time}
                      onChange={(e) => setForm((prev) => ({ ...prev, schedule_time: e.target.value }))}
                    />
                  </div>
                  <div className="flex flex-col gap-2 md:col-span-2">
                    <label className="text-xs font-semibold text-slate-700">Dias que deve rodar</label>
                    <div className="flex flex-wrap gap-2">
                      {SCHEDULE_PRESETS.map((preset) => (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => applySchedulePreset(preset.days)}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {WEEK_DAYS.map((day) => (
                        <button
                          key={day.value}
                          type="button"
                          onClick={() => toggleScheduleDay(day.value)}
                          aria-pressed={form.schedule_days.includes(day.value)}
                          className={`min-w-[52px] rounded-lg border px-3 py-2 text-xs font-bold transition ${
                            form.schedule_days.includes(day.value)
                              ? 'border-blue-600 bg-blue-600 text-white shadow-sm'
                              : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
                          }`}
                        >
                          {day.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-xs text-slate-500">
                      Para rodar somente na sexta, clique em "Toda sexta" ou deixe apenas "Sex" marcado. O periodo do relatorio continua sendo definido nas datas inicio e fim acima.
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark disabled:opacity-60"
              >
                <Save size={16} />
                {saving ? 'Salvando...' : 'Salvar template'}
              </button>
              {selectedId && (
                <button
                  onClick={handleDelete}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-600"
                >
                  <Trash2 size={16} />
                  Excluir
                </button>
              )}
            </div>

            <div className="mt-8 border-t border-slate-100 pt-5">
              <h3 className="text-sm font-bold text-slate-800 mb-3">Executar sob demanda</h3>
              <textarea
                className="w-full rounded-lg border border-slate-200 px-3 py-2"
                rows={3}
                value={runPromptOverride}
                onChange={(e) => setRunPromptOverride(e.target.value)}
                                placeholder="Opcional: sobrescreva o prompt apenas para esta execucao."
              />
              <button
                onClick={handleRunNow}
                disabled={running || !selectedId}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-50"
              >
                <Play size={16} />
                {running ? 'Executando...' : 'Executar agora'}
              </button>
            </div>
          </div>
        </section>
      )}

      {!loading && selectedId && (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-800 mb-4">Ultimas execucoes</h2>
          {runs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma execucao registrada.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold">Relatorio ID</th>
                    <th className="px-4 py-2 text-left font-semibold">Tipo</th>
                    <th className="px-4 py-2 text-left font-semibold">Status</th>
                    <th className="px-4 py-2 text-left font-semibold">Gerado em</th>
                    <th className="px-4 py-2 text-left font-semibold">Acao</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-slate-100">
                      <td className="px-4 py-2 text-slate-800 font-semibold">#{run.id}</td>
                      <td className="px-4 py-2 text-slate-600">{run.type}</td>
                      <td className="px-4 py-2 text-slate-600">{run.status}</td>
                      <td className="px-4 py-2 text-slate-600">{formatDate(run.generated_at)}</td>
                      <td className="px-4 py-2">
                        <button
                          type="button"
                          onClick={() => navigate(`/reports/redmine-deliveries?report_id=${run.id}`)}
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Abrir relatorio
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </AppShell>
  );
};

export default PromptReportsPage;




