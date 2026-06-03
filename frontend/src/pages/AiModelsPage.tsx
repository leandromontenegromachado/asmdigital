import React, { useEffect, useMemo, useState } from 'react';
import { Bot, CheckCircle2, Cpu, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import {
  AiModel,
  AiModelAssignment,
  AiModelFeature,
  createAiModel,
  deleteAiModel,
  listAiModelAssignments,
  listAiModelFeatures,
  listAiModels,
  updateAiModel,
  updateAiModelAssignment,
} from '../api/aiModels';

const providers = [
  { value: 'google_gemini', label: 'Google Gemini', supported: true },
  { value: 'openrouter', label: 'OpenRouter', supported: true },
  { value: 'openai', label: 'OpenAI', supported: false },
  { value: 'azure_openai', label: 'Azure OpenAI', supported: false },
  { value: 'ollama', label: 'Local/Ollama', supported: false },
];

const emptyForm = {
  id: null as number | null,
  name: '',
  provider: 'google_gemini',
  model_id: '',
  description: '',
  api_key_env: 'FALA_AI_GEMINI_API_KEY',
  is_active: true,
  is_default: false,
};

const providerInfo = (provider: string) =>
  providers.find((item) => item.value === provider) || { value: provider, label: provider, supported: false };

const AiModelsPage: React.FC = () => {
  const [models, setModels] = useState<AiModel[]>([]);
  const [features, setFeatures] = useState<AiModelFeature[]>([]);
  const [assignments, setAssignments] = useState<AiModelAssignment[]>([]);
  const [form, setForm] = useState({ ...emptyForm });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const activeModels = useMemo(() => models.filter((model) => model.is_active), [models]);
  const assignmentsByFeature = useMemo(
    () => Object.fromEntries(assignments.map((item) => [item.feature_key, item])),
    [assignments],
  );

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelsData, featuresData, assignmentsData] = await Promise.all([
        listAiModels(),
        listAiModelFeatures(),
        listAiModelAssignments(),
      ]);
      setModels(modelsData);
      setFeatures(featuresData);
      setAssignments(assignmentsData);
    } catch {
      setError('Nao foi possivel carregar os modelos de IA.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selectModel = (model: AiModel) => {
    setForm({
      id: model.id,
      name: model.name,
      provider: model.provider,
      model_id: model.model_id,
      description: model.description || '',
      api_key_env: model.api_key_env || '',
      is_active: model.is_active,
      is_default: model.is_default,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const newModel = () => {
    setForm({ ...emptyForm });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const saveModel = async () => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload = {
        name: form.name.trim(),
        provider: form.provider,
        model_id: form.model_id.trim(),
        description: form.description.trim() || null,
        api_key_env: form.api_key_env.trim() || null,
        is_active: form.is_active,
        is_default: form.is_default,
      };
      if (!payload.name || !payload.model_id) {
        setError('Informe o nome e o identificador do modelo.');
        return;
      }
      const saved = form.id ? await updateAiModel(form.id, payload) : await createAiModel(payload);
      setNotice('Modelo salvo.');
      await load();
      selectModel(saved);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao salvar o modelo.');
    } finally {
      setSaving(false);
    }
  };

  const removeModel = async (model: AiModel) => {
    if (!window.confirm(`Excluir o modelo "${model.name}"?`)) return;
    setError(null);
    setNotice(null);
    try {
      await deleteAiModel(model.id);
      setNotice('Modelo excluido.');
      if (form.id === model.id) newModel();
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao excluir o modelo.');
    }
  };

  const setAssignment = async (featureKey: string, modelId: string) => {
    setError(null);
    setNotice(null);
    try {
      await updateAiModelAssignment(featureKey, Number(modelId));
      setNotice('Modelo da funcionalidade atualizado.');
      const data = await listAiModelAssignments();
      setAssignments(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao atualizar a funcionalidade.');
    }
  };

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-50">
        <Topbar
          title="Modelos de IA"
          subtitle="Cadastre os modelos disponiveis e escolha qual modelo cada funcionalidade deve usar."
          action={
            <button
              onClick={load}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
            >
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
              Atualizar
            </button>
          }
        />
        <main className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>}
          {notice && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-700">{notice}</div>}

          <section className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
            <div className="rounded-xl border border-slate-200 bg-white shadow-soft">
              <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-5">
                <div>
                  <h2 className="text-xl font-black text-slate-900">
                    {form.id ? 'Editar modelo' : 'Novo modelo'}
                  </h2>
                  <p className="text-sm text-slate-500">
                    O Gemini atual ja fica cadastrado pela migration.
                  </p>
                </div>
                <button
                  onClick={newModel}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
                >
                  <Plus size={16} />
                  Novo
                </button>
              </div>

              <div className="grid gap-4 p-5 md:grid-cols-2">
                <label className="flex flex-col gap-2 md:col-span-2">
                  <span className="text-sm font-bold text-slate-700">Nome</span>
                  <input
                    className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={form.name}
                    onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="Gemini 3 Flash Preview"
                  />
                </label>

                <label className="flex flex-col gap-2">
                  <span className="text-sm font-bold text-slate-700">Provedor</span>
                  <select
                    className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={form.provider}
                    onChange={(event) => {
                      const provider = event.target.value;
                      setForm((prev) => ({
                        ...prev,
                        provider,
                        api_key_env: provider === 'openrouter' ? 'OPENROUTER_API_KEY' : prev.api_key_env || 'FALA_AI_GEMINI_API_KEY',
                      }));
                    }}
                  >
                    {providers.map((provider) => (
                      <option key={provider.value} value={provider.value}>
                        {provider.label}{provider.supported ? '' : ' (preparado)'}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="flex flex-col gap-2">
                  <span className="text-sm font-bold text-slate-700">ID do modelo</span>
                  <input
                    className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={form.model_id}
                    onChange={(event) => setForm((prev) => ({ ...prev, model_id: event.target.value }))}
                    placeholder="gemini-3-flash-preview"
                  />
                </label>

                <label className="flex flex-col gap-2 md:col-span-2">
                  <span className="text-sm font-bold text-slate-700">Variavel de ambiente da chave</span>
                  <input
                    className="rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={form.api_key_env}
                    onChange={(event) => setForm((prev) => ({ ...prev, api_key_env: event.target.value }))}
                    placeholder={form.provider === 'openrouter' ? 'OPENROUTER_API_KEY' : 'FALA_AI_GEMINI_API_KEY'}
                  />
                  <span className="text-xs text-slate-500">
                    A chave continua segura no servidor; aqui fica apenas o nome da variavel.
                  </span>
                </label>

                <label className="flex flex-col gap-2 md:col-span-2">
                  <span className="text-sm font-bold text-slate-700">Descricao</span>
                  <textarea
                    className="min-h-24 rounded-lg border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={form.description}
                    onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                    placeholder="Uso recomendado, custo, limites ou observacoes."
                  />
                </label>

                <div className="flex flex-wrap gap-4 md:col-span-2">
                  <label className="inline-flex items-center gap-2 text-sm font-bold text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.is_active}
                      onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))}
                    />
                    Ativo
                  </label>
                  <label className="inline-flex items-center gap-2 text-sm font-bold text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.is_default}
                      onChange={(event) => setForm((prev) => ({ ...prev, is_default: event.target.checked }))}
                    />
                    Modelo padrao
                  </label>
                </div>

                <div className="flex flex-wrap gap-3 md:col-span-2">
                  <button
                    onClick={saveModel}
                    disabled={saving}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-blue-600 disabled:opacity-60"
                  >
                    <Save size={18} />
                    {saving ? 'Salvando...' : 'Salvar modelo'}
                  </button>
                  {form.id && (
                    <button
                      onClick={() => {
                        const model = models.find((item) => item.id === form.id);
                        if (model) removeModel(model);
                      }}
                      className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 px-5 py-3 text-sm font-bold text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={18} />
                      Excluir
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-soft">
              <div className="flex items-start gap-3">
                <div className="rounded-lg bg-blue-50 p-3 text-primary">
                  <Cpu size={22} />
                </div>
                <div>
                  <h2 className="text-xl font-black text-slate-900">Uso por funcionalidade</h2>
                  <p className="text-sm text-slate-500">
                    Escolha modelos diferentes para relatorios, avaliacao, ChefIA, assistente e orquestrador.
                  </p>
                </div>
              </div>

              <div className="mt-5 flex flex-col gap-4">
                {features.map((feature) => {
                  const assignment = assignmentsByFeature[feature.key];
                  return (
                    <div key={feature.key} className="rounded-lg border border-slate-200 p-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div>
                          <p className="font-black text-slate-900">{feature.label}</p>
                          <p className="text-xs text-slate-500">{feature.key}</p>
                        </div>
                        {assignment?.provider_supported && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-700">
                            <CheckCircle2 size={14} />
                            ativo
                          </span>
                        )}
                      </div>
                      <select
                        className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 outline-none focus:border-primary"
                        value={assignment?.model_id || ''}
                        onChange={(event) => setAssignment(feature.key, event.target.value)}
                      >
                        <option value="" disabled>Selecione um modelo</option>
                        {activeModels.map((model) => (
                          <option key={model.id} value={model.id}>
                            {model.name} - {model.model_id}
                          </option>
                        ))}
                      </select>
                      {assignment && (
                        <p className="mt-2 text-xs text-slate-500">
                          Usando {assignment.provider_label} / {assignment.external_model_id}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white shadow-soft">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 p-5">
              <div>
                <h2 className="text-xl font-black text-slate-900">Modelos cadastrados</h2>
                <p className="text-sm text-slate-500">Modelos ativos podem ser selecionados nas funcionalidades.</p>
              </div>
              <Bot className="text-primary" size={24} />
            </div>
            <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
              {models.map((model) => {
                const info = providerInfo(model.provider);
                return (
                  <article key={model.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-slate-400">{info.label}</p>
                        <h3 className="mt-1 text-lg font-black text-slate-900">{model.name}</h3>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        {model.is_default && <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold text-blue-700">padrao</span>}
                        <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${model.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                          {model.is_active ? 'ativo' : 'inativo'}
                        </span>
                      </div>
                    </div>
                    <p className="mt-3 break-all rounded-lg bg-slate-50 px-3 py-2 font-mono text-sm text-slate-700">
                      {model.model_id}
                    </p>
                    <p className="mt-3 line-clamp-3 min-h-12 text-sm text-slate-500">
                      {model.description || 'Sem descricao.'}
                    </p>
                    {!info.supported && (
                      <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
                        Provedor preparado para cadastro; os servicos atuais executam Google Gemini.
                      </p>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={() => selectModel(model)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => removeModel(model)}
                        className="rounded-lg border border-red-200 px-3 py-2 text-sm font-bold text-red-600 hover:bg-red-50"
                      >
                        Excluir
                      </button>
                    </div>
                  </article>
                );
              })}
              {!models.length && !loading && (
                <div className="rounded-lg border border-dashed border-slate-300 p-6 text-slate-500">
                  Nenhum modelo cadastrado.
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </AppShell>
  );
};

export default AiModelsPage;
