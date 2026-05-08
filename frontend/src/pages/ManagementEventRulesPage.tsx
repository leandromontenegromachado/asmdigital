import React, { useEffect, useMemo, useState } from 'react';
import { Plus, RefreshCw, Save, SlidersHorizontal, Trash2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import {
  ManagementEventRule,
  createManagementEventRule,
  deleteManagementEventRule,
  listManagementEventRules,
  updateManagementEventRule,
} from '../api/managementEventRules';

const defaultCondition = {
  event_type: { eq: 'ROUTINE_FAILED' },
};

const defaultAction = {
  type: 'create_pending_item',
};

const stringifyJson = (value: Record<string, unknown>) => JSON.stringify(value, null, 2);

const emptyForm = {
  id: null as number | null,
  name: '',
  description: '',
  is_active: true,
  priority: 100,
  condition_json: stringifyJson(defaultCondition),
  action_json: stringifyJson(defaultAction),
};

const ManagementEventRulesPage: React.FC = () => {
  const [rules, setRules] = useState<ManagementEventRule[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRule = useMemo(
    () => rules.find((rule) => rule.id === selectedId) || null,
    [rules, selectedId],
  );

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listManagementEventRules();
      setRules(data);
      if (!selectedId && data.length > 0) {
        selectRule(data[0]);
      }
    } catch {
      setError('Não foi possível carregar as regras gerenciais.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selectRule = (rule: ManagementEventRule) => {
    setSelectedId(rule.id);
    setForm({
      id: rule.id,
      name: rule.name,
      description: rule.description || '',
      is_active: rule.is_active,
      priority: rule.priority,
      condition_json: stringifyJson(rule.condition_json || {}),
      action_json: stringifyJson(rule.action_json || {}),
    });
  };

  const newRule = () => {
    setSelectedId(null);
    setForm({ ...emptyForm });
  };

  const parseJson = (label: string, value: string) => {
    try {
      const parsed = JSON.parse(value || '{}');
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('invalid');
      }
      return parsed as Record<string, unknown>;
    } catch {
      throw new Error(`${label} deve ser um JSON válido.`);
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        is_active: form.is_active,
        priority: Number(form.priority) || 100,
        condition_json: parseJson('Condição', form.condition_json),
        action_json: parseJson('Ação', form.action_json),
      };
      if (!payload.name) {
        setError('Informe o nome da regra.');
        return;
      }
      const saved = form.id
        ? await updateManagementEventRule(form.id, payload)
        : await createManagementEventRule(payload);
      await load();
      selectRule(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao salvar a regra.');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!form.id) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deleteManagementEventRule(form.id);
      newRule();
      await load();
    } catch {
      setError('Falha ao desativar a regra.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Regras Gerenciais"
        subtitle="Configure condições e ações para processar eventos gerenciais."
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Regras cadastradas</h2>
              <p className="text-sm text-slate-500">{rules.length} regra(s)</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={load}
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
                title="Atualizar"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                type="button"
                onClick={newRule}
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white hover:bg-primary-dark"
                title="Nova regra"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="max-h-[620px] divide-y divide-slate-100 overflow-y-auto">
            {rules.length === 0 && (
              <div className="p-5 text-sm text-slate-500">Nenhuma regra cadastrada.</div>
            )}
            {rules.map((rule) => (
              <button
                key={rule.id}
                type="button"
                onClick={() => selectRule(rule)}
                className={`w-full px-5 py-4 text-left transition-colors ${
                  selectedRule?.id === rule.id ? 'bg-blue-50' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-bold text-slate-900">{rule.name}</p>
                    <p className="mt-1 text-xs text-slate-500">Prioridade {rule.priority}</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${
                    rule.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
                  }`}>
                    {rule.is_active ? 'Ativa' : 'Inativa'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">{form.id ? `Editar regra #${form.id}` : 'Nova regra'}</h2>
              <p className="text-sm text-slate-500">Use JSON simples para condição e ação.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {form.id && (
                <button
                  type="button"
                  onClick={remove}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2 text-sm font-bold text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                  Desativar
                </button>
              )}
              <button
                type="button"
                onClick={save}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                Salvar regra
              </button>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Nome
              <input
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                placeholder="Ex.: Falha de rotina vira pendência"
              />
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Prioridade
              <input
                type="number"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={form.priority}
                onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })}
              />
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700 lg:col-span-2">
              Descrição
              <textarea
                className="h-20 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                placeholder="Explique quando a regra deve agir."
              />
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700 lg:col-span-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              Regra ativa
            </label>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <label className="space-y-2 text-sm font-semibold text-slate-700">
              Condition JSON
              <textarea
                className="h-72 w-full resize-y rounded-lg border border-slate-200 bg-slate-950 px-3 py-3 font-mono text-xs font-normal text-slate-50"
                value={form.condition_json}
                onChange={(event) => setForm({ ...form, condition_json: event.target.value })}
              />
            </label>
            <label className="space-y-2 text-sm font-semibold text-slate-700">
              Action JSON
              <textarea
                className="h-72 w-full resize-y rounded-lg border border-slate-200 bg-slate-950 px-3 py-3 font-mono text-xs font-normal text-slate-50"
                value={form.action_json}
                onChange={(event) => setForm({ ...form, action_json: event.target.value })}
              />
            </label>
          </div>

          <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <div className="mb-2 flex items-center gap-2 font-bold text-slate-800">
              <SlidersHorizontal className="h-4 w-4" />
              Exemplos aceitos
            </div>
            <p>Condição: <code>{'{"severity":{"eq":"critical"}}'}</code> ou <code>{'{"field":"payload_json.dias_atraso","op":"gte","value":5}'}</code></p>
            <p className="mt-1">Ação: <code>{'{"type":"create_pending_item"}'}</code>, <code>{'{"type":"mark_processed"}'}</code>, <code>{'{"type":"ignore"}'}</code> ou <code>{'{"type":"notify_responsible"}'}</code>.</p>
          </div>
        </section>
      </div>
    </AppShell>
  );
};

export default ManagementEventRulesPage;
