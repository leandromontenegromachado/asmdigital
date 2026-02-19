import React, { useEffect, useState } from 'react';
import { Play, Plus, Save, Trash2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { listConnectors, Connector } from '../api/connectors';
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
  schedule_cron: string;
  is_enabled: boolean;
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
  schedule_cron: '',
  is_enabled: true,
};

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const templateToForm = (template: PromptReportTemplate): FormState => ({
  name: template.name,
  connector_id: String(template.connector_id),
  prompt_text: template.prompt_text,
  project_ids: Array.isArray(template.params_json?.project_ids) ? template.params_json.project_ids.join(', ') : '',
  status_id: template.params_json?.status_id || '',
  query_id: template.params_json?.query_id || '',
  start_date: template.params_json?.start_date || '',
  end_date: template.params_json?.end_date || '',
  schedule_cron: template.schedule_cron || '',
  is_enabled: template.is_enabled,
});

const PromptReportsPage: React.FC = () => {
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
    setSelectedId(null);
    setForm({
      ...defaultForm,
      connector_id: connectors[0] ? String(connectors[0].id) : '',
    });
    setRuns([]);
    setRunPromptOverride('');
    setInfo(null);
    setError(null);
  };

  const buildPayload = () => ({
    name: form.name.trim(),
    connector_id: Number(form.connector_id),
    prompt_text: form.prompt_text.trim(),
    params_json: {
      project_ids: form.project_ids
        .split(',')
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean),
      status_id: form.status_id.trim() || null,
      query_id: form.query_id.trim() || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    },
    schedule_cron: form.schedule_cron.trim() || null,
    is_enabled: form.is_enabled,
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
      const result = await runPromptReportTemplate(selectedId, runPromptOverride.trim() || undefined);
      setInfo(`Relatório executado com sucesso. ID: ${result.report_id}`);
      await loadData();
      await loadRuns(selectedId);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao executar template.');
    } finally {
      setRunning(false);
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Relatórios por Linguagem Natural"
        subtitle="Crie prompts reutilizáveis, execute sob demanda e configure agendamento com CRON."
      />

      {loading && <StateBlock tone="info" title="Carregando" description="Buscando templates e conectores..." />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {info && <StateBlock tone="success" title="Sucesso" description={info} />}

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
                  <p className="text-xs text-slate-500">Última execução: {formatDate(item.last_run_at)}</p>
                  <p className="text-xs text-slate-500">Próxima: {formatDate(item.next_run_at)}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm xl:col-span-2">
            <h2 className="text-base font-bold text-slate-800 mb-4">
              {selectedId ? `Editar template #${selectedId}` : 'Novo template'}
            </h2>
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
                  onChange={(e) => setForm((prev) => ({ ...prev, connector_id: e.target.value }))}
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
                <label className="text-xs font-semibold text-slate-700">Prompt</label>
                <textarea
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  rows={4}
                  value={form.prompt_text}
                  onChange={(e) => setForm((prev) => ({ ...prev, prompt_text: e.target.value }))}
                  placeholder="Ex.: gerar relatório dos últimos 30 dias para projetos: asm-dem, asm-app com status fechado"
                />
                <p className="text-xs text-slate-500">
                  Entende expressões como: "últimos 30 dias", "este mês", "status fechado", "query_id 1234", "projetos: x, y".
                </p>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Projetos padrão (IDs)</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.project_ids}
                  onChange={(e) => setForm((prev) => ({ ...prev, project_ids: e.target.value }))}
                  placeholder="asm-dem, asm-app"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Query padrão</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.query_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, query_id: e.target.value }))}
                  placeholder="8117"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Status padrão</label>
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
                <label className="text-xs font-semibold text-slate-700">Agendamento CRON</label>
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2 font-mono"
                  value={form.schedule_cron}
                  onChange={(e) => setForm((prev) => ({ ...prev, schedule_cron: e.target.value }))}
                  placeholder="0 8 * * 1"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Data início padrão</label>
                <input
                  type="date"
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.start_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, start_date: e.target.value }))}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-slate-700">Data fim padrão</label>
                <input
                  type="date"
                  className="rounded-lg border border-slate-200 px-3 py-2"
                  value={form.end_date}
                  onChange={(e) => setForm((prev) => ({ ...prev, end_date: e.target.value }))}
                />
              </div>
            </div>

            <div className="mt-4 flex items-center gap-2">
              <input
                id="template-enabled"
                type="checkbox"
                checked={form.is_enabled}
                onChange={(e) => setForm((prev) => ({ ...prev, is_enabled: e.target.checked }))}
              />
              <label htmlFor="template-enabled" className="text-sm text-slate-700">
                Template habilitado para execução agendada
              </label>
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
                placeholder="Opcional: sobrescreva o prompt apenas para esta execução."
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
          <h2 className="text-base font-bold text-slate-800 mb-4">Últimas execuções</h2>
          {runs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma execução registrada.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold">Relatório ID</th>
                    <th className="px-4 py-2 text-left font-semibold">Tipo</th>
                    <th className="px-4 py-2 text-left font-semibold">Status</th>
                    <th className="px-4 py-2 text-left font-semibold">Gerado em</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-slate-100">
                      <td className="px-4 py-2 text-slate-800 font-semibold">#{run.id}</td>
                      <td className="px-4 py-2 text-slate-600">{run.type}</td>
                      <td className="px-4 py-2 text-slate-600">{run.status}</td>
                      <td className="px-4 py-2 text-slate-600">{formatDate(run.generated_at)}</td>
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
