
import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, LayoutGrid, List, Play, Plus, RefreshCw, Save, Search, Settings2, Trash2, X } from 'lucide-react';

import { AppShell } from '../components/AppShell';
import {
  Automation,
  AutomationRun,
  createAutomation,
  listAutomations,
  listAutomationRuns,
  runAutomation,
  updateAutomation,
} from '../api/automations';
import { PromptReportTemplate, listPromptReportTemplates } from '../api/promptReports';

type ViewMode = 'grid' | 'list';
type StatusFilter = 'all' | 'enabled' | 'paused';
type TaskKind = 'redmine_report' | 'prompt_report' | 'azure_devops_board' | 'webhook_post' | 'sleep' | 'custom';

type TaskItem = {
  uid: string;
  type: TaskKind;
  report_id: string;
  connector_id: string;
  project_ids: string;
  start_date: string;
  end_date: string;
  status_id: string;
  query_id: string;
  template_id: string;
  prompt_override: string;
  azure_project: string;
  azure_team: string;
  azure_area_path: string;
  azure_iteration_path: string;
  azure_top: string;
  url: string;
  message: string;
  seconds: string;
  custom_line: string;
};

type EditForm = {
  id: number;
  name: string;
  schedule_cron: string;
  is_enabled: boolean;
  simulation: boolean;
  tasks: TaskItem[];
};

type CreateForm = {
  name: string;
  schedule_cron: string;
  is_enabled: boolean;
  simulation: boolean;
  tasks: TaskItem[];
};

type ValidationState = {
  formErrors: string[];
  taskErrors: Record<string, string[]>;
};

const TARGET_TEMPLATE_NAME = 'pendencias abertas semanais';

const formatDate = (value?: string | null) => {
  if (!value) return 'Nao agendada';
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const statusBadge = (automation: Automation) => (!automation.is_enabled ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800');
const statusLabel = (automation: Automation) => (automation.is_enabled ? 'Ativa' : 'Pausada');
const uid = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const normalizeText = (value: string) =>
  value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

const emptyTask = (type: TaskKind = 'redmine_report'): TaskItem => ({
  uid: uid(),
  type,
  report_id: '',
  connector_id: '',
  project_ids: '',
  start_date: '',
  end_date: '',
  status_id: '',
  query_id: '',
  template_id: '',
  prompt_override: '',
  azure_project: '',
  azure_team: '',
  azure_area_path: '',
  azure_iteration_path: '',
  azure_top: '200',
  url: '',
  message: '',
  seconds: '1',
  custom_line: '',
});

const parseKv = (value: string): Record<string, string> => {
  const out: Record<string, string> = {};
  for (const part of value.split(',')) {
    const item = part.trim();
    if (!item || !item.includes('=')) continue;
    const [key, ...rest] = item.split('=');
    out[key.trim().toLowerCase()] = rest.join('=').trim();
  }
  return out;
};

const lineToTask = (line: string): TaskItem => {
  const trimmed = line.trim();
  if (!trimmed) return emptyTask('custom');

  const [head, ...rest] = trimmed.split(':');
  const action = head.trim().toLowerCase();
  const arg = rest.join(':').trim();
  const kv = parseKv(arg);

  if (action === 'redmine_report') {
    return {
      ...emptyTask('redmine_report'),
      report_id: kv.report_id || '',
      template_id: kv.template_id || '',
      connector_id: kv.connector_id || '',
      project_ids: kv.project_ids || '',
      start_date: kv.start_date || '',
      end_date: kv.end_date || '',
      status_id: kv.status_id || '',
      query_id: kv.query_id || '',
    };
  }

  if (action === 'prompt_report') {
    return {
      ...emptyTask('prompt_report'),
      template_id: kv.template_id || (arg && !arg.includes('=') ? arg : ''),
      prompt_override: kv.prompt_override || '',
    };
  }

  if (action === 'azure_devops_board' || action === 'azure_snapshot' || action === 'azure_board_status') {
    return {
      ...emptyTask('azure_devops_board'),
      connector_id: kv.connector_id || '',
      azure_project: kv.project || '',
      azure_team: kv.team || '',
      azure_area_path: kv.area_path || '',
      azure_iteration_path: kv.iteration_path || '',
      azure_top: kv.top || '200',
    };
  }

  if (action === 'webhook_post') {
    return {
      ...emptyTask('webhook_post'),
      url: kv.url || '',
      message: kv.message || '',
    };
  }

  if (action === 'sleep' || action === 'wait' || action === 'delay') {
    return { ...emptyTask('sleep'), seconds: arg || '1' };
  }

  return { ...emptyTask('custom'), custom_line: trimmed };
};

const taskToLine = (task: TaskItem): string => {
  if (task.type === 'custom') return task.custom_line.trim();

  if (task.type === 'redmine_report') {
    const params: string[] = [];
    if (task.report_id.trim()) params.push(`report_id=${task.report_id.trim()}`);
    if (task.template_id.trim()) params.push(`template_id=${task.template_id.trim()}`);
    if (task.connector_id.trim()) params.push(`connector_id=${task.connector_id.trim()}`);
    if (task.project_ids.trim()) params.push(`project_ids=${task.project_ids.trim()}`);
    if (task.start_date.trim()) params.push(`start_date=${task.start_date.trim()}`);
    if (task.end_date.trim()) params.push(`end_date=${task.end_date.trim()}`);
    if (task.status_id.trim()) params.push(`status_id=${task.status_id.trim()}`);
    if (task.query_id.trim()) params.push(`query_id=${task.query_id.trim()}`);
    return params.length ? `redmine_report:${params.join(',')}` : 'redmine_report';
  }

  if (task.type === 'prompt_report') {
    const params: string[] = [];
    if (task.template_id.trim()) params.push(`template_id=${task.template_id.trim()}`);
    if (task.prompt_override.trim()) params.push(`prompt_override=${task.prompt_override.trim()}`);
    return params.length ? `prompt_report:${params.join(',')}` : 'prompt_report';
  }

  if (task.type === 'webhook_post') {
    const params: string[] = [];
    if (task.url.trim()) params.push(`url=${task.url.trim()}`);
    if (task.message.trim()) params.push(`message=${task.message.trim()}`);
    return params.length ? `webhook_post:${params.join(',')}` : 'webhook_post';
  }

  if (task.type === 'azure_devops_board') {
    const params: string[] = [];
    if (task.connector_id.trim()) params.push(`connector_id=${task.connector_id.trim()}`);
    if (task.azure_project.trim()) params.push(`project=${task.azure_project.trim()}`);
    if (task.azure_team.trim()) params.push(`team=${task.azure_team.trim()}`);
    if (task.azure_area_path.trim()) params.push(`area_path=${task.azure_area_path.trim()}`);
    if (task.azure_iteration_path.trim()) params.push(`iteration_path=${task.azure_iteration_path.trim()}`);
    if (task.azure_top.trim()) params.push(`top=${task.azure_top.trim()}`);
    return params.length ? `azure_devops_board:${params.join(',')}` : 'azure_devops_board';
  }

  return `sleep:${task.seconds.trim() || '1'}`;
};

const tasksFromParams = (tasks: unknown): TaskItem[] =>
  Array.isArray(tasks) ? tasks.filter((item): item is string => typeof item === 'string').map(lineToTask) : [];

const tasksToPayload = (tasks: TaskItem[]): string[] => tasks.map(taskToLine).map((line) => line.trim()).filter(Boolean);

const emptyValidation = (): ValidationState => ({ formErrors: [], taskErrors: {} });

const isValidCron = (value: string) => {
  const parts = value.trim().split(/\s+/);
  return parts.length === 5;
};

const isValidDateIso = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);

const validateRoutine = (name: string, scheduleCron: string, tasks: TaskItem[]): ValidationState => {
  const result: ValidationState = emptyValidation();

  if (!name.trim()) {
    result.formErrors.push('Nome da rotina e obrigatorio.');
  }

  if (scheduleCron.trim() && !isValidCron(scheduleCron)) {
    result.formErrors.push('CRON invalido. Use 5 campos, por exemplo: 0 8 * * 1');
  }

  if (tasks.length === 0) {
    result.formErrors.push('Adicione ao menos uma tarefa.');
  }

  for (const task of tasks) {
    const errors: string[] = [];

    if (task.type === 'redmine_report') {
      if (!task.template_id.trim() && !task.connector_id.trim()) {
        errors.push('Selecione um template salvo ou informe connector_id.');
      }
      if (task.template_id.trim() && !/^\d+$/.test(task.template_id.trim())) errors.push('template_id deve ser numerico.');
      if (task.connector_id.trim() && !/^\d+$/.test(task.connector_id.trim())) errors.push('connector_id deve ser numerico.');
      if (task.start_date.trim() && !isValidDateIso(task.start_date.trim())) errors.push('start_date deve ser YYYY-MM-DD.');
      if (task.end_date.trim() && !isValidDateIso(task.end_date.trim())) errors.push('end_date deve ser YYYY-MM-DD.');
    }

    if (task.type === 'prompt_report') {
      if (!task.template_id.trim()) errors.push('template_id e obrigatorio.');
      if (task.template_id.trim() && !/^\d+$/.test(task.template_id.trim())) errors.push('template_id deve ser numerico.');
    }

    if (task.type === 'azure_devops_board') {
      if (!task.connector_id.trim()) errors.push('connector_id do Azure DevOps e obrigatorio.');
      if (task.connector_id.trim() && !/^\d+$/.test(task.connector_id.trim())) errors.push('connector_id deve ser numerico.');
      if (task.azure_top.trim() && (!/^\d+$/.test(task.azure_top.trim()) || Number(task.azure_top.trim()) <= 0)) {
        errors.push('top deve ser inteiro positivo.');
      }
    }

    if (task.type === 'webhook_post') {
      if (!task.url.trim()) {
        errors.push('URL do webhook e obrigatoria.');
      } else {
        try {
          // eslint-disable-next-line no-new
          new URL(task.url.trim());
        } catch {
          errors.push('URL do webhook invalida.');
        }
      }
    }

    if (task.type === 'sleep') {
      const value = Number(task.seconds.trim());
      if (!task.seconds.trim()) errors.push('Segundos e obrigatorio.');
      if (!Number.isFinite(value) || value <= 0) errors.push('Segundos deve ser maior que zero.');
    }

    if (task.type === 'custom' && !task.custom_line.trim()) {
      errors.push('Linha custom nao pode ser vazia.');
    }

    if (errors.length > 0) {
      result.taskErrors[task.uid] = errors;
    }
  }

  return result;
};

type TaskEditorProps = {
  tasks: TaskItem[];
  onChange: (tasks: TaskItem[]) => void;
  taskErrors: Record<string, string[]>;
  promptTemplatesCatalog: PromptReportTemplate[];
};

const TaskEditor: React.FC<TaskEditorProps> = ({ tasks, onChange, taskErrors, promptTemplatesCatalog }) => {
  const updateTask = (uidValue: string, patch: Partial<TaskItem>) => {
    onChange(tasks.map((item) => (item.uid === uidValue ? { ...item, ...patch } : item)));
  };

  const removeTask = (uidValue: string) => onChange(tasks.filter((item) => item.uid !== uidValue));

  const moveTask = (index: number, direction: -1 | 1) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= tasks.length) return;
    const draft = [...tasks];
    const [current] = draft.splice(index, 1);
    draft.splice(nextIndex, 0, current);
    onChange(draft);
  };

  const addTask = () => onChange([...tasks, emptyTask('redmine_report')]);

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="block text-xs font-semibold text-gray-700">Tarefas da rotina</label>
        <button type="button" onClick={addTask} className="rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-700">
          + Adicionar tarefa
        </button>
      </div>

      <div className="space-y-3">
        {tasks.length === 0 && <div className="rounded-lg border border-dashed border-gray-300 p-3 text-xs text-gray-500">Nenhuma tarefa configurada.</div>}

        {tasks.map((task, index) => {
          const errors = taskErrors[task.uid] || [];
          return (
          <div key={task.uid} className={`rounded-lg border bg-gray-50 p-3 ${errors.length ? 'border-red-300' : 'border-gray-200'}`}>
            <div className="mb-2 flex items-center justify-between gap-2">
              <select
                className="w-full rounded-lg border border-gray-300 bg-white px-2 py-1.5 text-sm sm:w-64"
                value={task.type}
                onChange={(e) => updateTask(task.uid, { type: e.target.value as TaskKind })}
              >
                <option value="redmine_report">Relatorio Redmine</option>
                <option value="prompt_report">Prompt Report</option>
                <option value="azure_devops_board">Azure DevOps Quadro</option>
                <option value="webhook_post">Webhook</option>
                <option value="sleep">Sleep</option>
                <option value="custom">Custom</option>
              </select>

              <div className="flex items-center gap-1">
                <button type="button" onClick={() => moveTask(index, -1)} className="rounded border border-gray-300 p-1 text-gray-600 hover:bg-white" title="Subir">
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => moveTask(index, 1)} className="rounded border border-gray-300 p-1 text-gray-600 hover:bg-white" title="Descer">
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
                <button type="button" onClick={() => removeTask(task.uid)} className="rounded border border-red-200 p-1 text-red-600 hover:bg-red-50" title="Remover">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {task.type === 'redmine_report' && (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <select
                  className="rounded border border-gray-300 px-2 py-1.5 text-sm sm:col-span-2"
                  value={task.template_id}
                  onChange={(e) => updateTask(task.uid, { template_id: e.target.value })}
                >
                  <option value="">Selecionar template salvo (opcional)</option>
                  {promptTemplatesCatalog.map((template) => (
                    <option key={template.id} value={String(template.id)}>
                      #{template.id} - {template.name}
                    </option>
                  ))}
                </select>
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="connector_id" value={task.connector_id} onChange={(e) => updateTask(task.uid, { connector_id: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="project_ids (ex: asm-dem,abc)" value={task.project_ids} onChange={(e) => updateTask(task.uid, { project_ids: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="start_date YYYY-MM-DD" value={task.start_date} onChange={(e) => updateTask(task.uid, { start_date: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="end_date YYYY-MM-DD" value={task.end_date} onChange={(e) => updateTask(task.uid, { end_date: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="status_id (opcional)" value={task.status_id} onChange={(e) => updateTask(task.uid, { status_id: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="query_id (opcional)" value={task.query_id} onChange={(e) => updateTask(task.uid, { query_id: e.target.value })} />
              </div>
            )}

            {task.type === 'prompt_report' && (
              <div className="grid grid-cols-1 gap-2">
                <select
                  className="rounded border border-gray-300 px-2 py-1.5 text-sm"
                  value={task.template_id}
                  onChange={(e) => updateTask(task.uid, { template_id: e.target.value })}
                >
                  <option value="">Selecionar template salvo</option>
                  {promptTemplatesCatalog.map((template) => (
                    <option key={template.id} value={String(template.id)}>
                      #{template.id} - {template.name}
                    </option>
                  ))}
                </select>
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="prompt_override (opcional)" value={task.prompt_override} onChange={(e) => updateTask(task.uid, { prompt_override: e.target.value })} />
              </div>
            )}

            {task.type === 'azure_devops_board' && (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="connector_id Azure" value={task.connector_id} onChange={(e) => updateTask(task.uid, { connector_id: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="project (opcional)" value={task.azure_project} onChange={(e) => updateTask(task.uid, { azure_project: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="team (opcional)" value={task.azure_team} onChange={(e) => updateTask(task.uid, { azure_team: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="top (padrao 200)" value={task.azure_top} onChange={(e) => updateTask(task.uid, { azure_top: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm sm:col-span-2" placeholder="area_path (opcional)" value={task.azure_area_path} onChange={(e) => updateTask(task.uid, { azure_area_path: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm sm:col-span-2" placeholder="iteration_path (opcional)" value={task.azure_iteration_path} onChange={(e) => updateTask(task.uid, { azure_iteration_path: e.target.value })} />
              </div>
            )}

            {task.type === 'webhook_post' && (
              <div className="grid grid-cols-1 gap-2">
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="url" value={task.url} onChange={(e) => updateTask(task.uid, { url: e.target.value })} />
                <input className="rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="message (opcional)" value={task.message} onChange={(e) => updateTask(task.uid, { message: e.target.value })} />
              </div>
            )}

            {task.type === 'sleep' && (
              <input className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm" placeholder="segundos" value={task.seconds} onChange={(e) => updateTask(task.uid, { seconds: e.target.value })} />
            )}

            {task.type === 'custom' && (
              <input className="w-full rounded border border-gray-300 px-2 py-1.5 font-mono text-sm" placeholder="linha livre da tarefa" value={task.custom_line} onChange={(e) => updateTask(task.uid, { custom_line: e.target.value })} />
            )}
            {errors.length > 0 && (
              <div className="mt-2 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                {errors.join(' ')}
              </div>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
};

const RoutinesPage: React.FC = () => {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [promptTemplatesCatalog, setPromptTemplatesCatalog] = useState<PromptReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>({
    name: '',
    schedule_cron: '',
    is_enabled: true,
    simulation: true,
    tasks: [emptyTask('redmine_report')],
  });
  const [createValidation, setCreateValidation] = useState<ValidationState>(emptyValidation());
  const [editValidation, setEditValidation] = useState<ValidationState>(emptyValidation());
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null);

  const loadData = async () => {
    setError(null);
    const [automationsData, runsData, templatesData] = await Promise.all([
      listAutomations(),
      listAutomationRuns(),
      listPromptReportTemplates(),
    ]);
    setAutomations(automationsData);
    setRuns(runsData);
    setPromptTemplatesCatalog(templatesData);
  };

  useEffect(() => {
    const bootstrap = async () => {
      setLoading(true);
      setError(null);
      try {
        await loadData();
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Falha ao carregar rotinas.');
      } finally {
        setLoading(false);
      }
    };
    bootstrap();
  }, []);

  const filteredAutomations = useMemo(() => {
    const q = search.trim().toLowerCase();
    return automations.filter((item) => {
      const matchesSearch = !q || item.name.toLowerCase().includes(q) || item.key.toLowerCase().includes(q);
      const matchesStatus = statusFilter === 'all' || (statusFilter === 'enabled' && item.is_enabled) || (statusFilter === 'paused' && !item.is_enabled);
      return matchesSearch && matchesStatus;
    });
  }, [automations, search, statusFilter]);

  const filteredTemplatesCatalog = useMemo(
    () =>
      promptTemplatesCatalog.filter((template) =>
        normalizeText(template.name).includes(TARGET_TEMPLATE_NAME),
      ),
    [promptTemplatesCatalog],
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await loadData();
      setInfo('Dados atualizados.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao atualizar dados.');
    } finally {
      setRefreshing(false);
    }
  };

  const handleRunNow = async (automation: Automation) => {
    setRunningId(automation.id);
    setError(null);
    setInfo(null);
    try {
      const simulation = Boolean(automation.params_json?.simulation ?? true);
      await runAutomation(automation.id, simulation);
      await loadData();
      setInfo(`Rotina executada: ${automation.name}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao executar rotina.');
    } finally {
      setRunningId(null);
    }
  };

  const openEditModal = (automation: Automation) => {
    setEditForm({
      id: automation.id,
      name: automation.name,
      schedule_cron: automation.schedule_cron || '',
      is_enabled: automation.is_enabled,
      simulation: Boolean(automation.params_json?.simulation ?? true),
      tasks: tasksFromParams(automation.params_json?.tasks),
    });
    setEditValidation(emptyValidation());
    setEditOpen(true);
  };

  const handleOpenCreate = () => {
    setCreateForm({
      name: '',
      schedule_cron: '',
      is_enabled: true,
      simulation: true,
      tasks: [emptyTask('redmine_report')],
    });
    setCreateValidation(emptyValidation());
    setCreateOpen(true);
  };

  const handleCreateRoutine = async () => {
    const validation = validateRoutine(createForm.name, createForm.schedule_cron, createForm.tasks);
    setCreateValidation(validation);
    if (validation.formErrors.length > 0 || Object.keys(validation.taskErrors).length > 0) {
      setError('Corrija os erros de validacao antes de salvar.');
      return;
    }

    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const created = await createAutomation({
        name: createForm.name.trim(),
        schedule_cron: createForm.schedule_cron.trim() || null,
        is_enabled: createForm.is_enabled,
        params_json: {
          simulation: createForm.simulation,
          tasks: tasksToPayload(createForm.tasks),
        },
      });
      setAutomations((prev) => [...prev, created].sort((a, b) => a.id - b.id));
      setCreateOpen(false);
      setInfo(`Rotina criada: ${created.name}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao criar rotina.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editForm) return;
    const validation = validateRoutine(editForm.name, editForm.schedule_cron, editForm.tasks);
    setEditValidation(validation);
    if (validation.formErrors.length > 0 || Object.keys(validation.taskErrors).length > 0) {
      setError('Corrija os erros de validacao antes de salvar.');
      return;
    }

    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const updated = await updateAutomation(editForm.id, {
        name: editForm.name.trim(),
        schedule_cron: editForm.schedule_cron.trim() || null,
        is_enabled: editForm.is_enabled,
        params_json: {
          simulation: editForm.simulation,
          tasks: tasksToPayload(editForm.tasks),
        },
      });
      setAutomations((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEditOpen(false);
      setEditForm(null);
      setInfo('Rotina atualizada com sucesso.');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao salvar rotina.');
    } finally {
      setSaving(false);
    }
  };

  const handleQuickToggle = async (automation: Automation) => {
    setError(null);
    setInfo(null);
    try {
      const updated = await updateAutomation(automation.id, { is_enabled: !automation.is_enabled });
      setAutomations((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setInfo(`Rotina ${updated.is_enabled ? 'ativada' : 'pausada'}: ${updated.name}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao alterar status da rotina.');
    }
  };

  return (
    <AppShell>
      <div className="w-full">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">Gestao de Rotinas</h1>
            <p className="mt-1 text-gray-500">Gerencie agendamento, estado e execucoes das automacoes do sistema.</p>
          </div>
          <div className="flex gap-2">
            <button onClick={handleOpenCreate} className="inline-flex items-center justify-center rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-cyan-700"><Plus className="mr-2 h-4 w-4" />Nova rotina</button>
            <button onClick={handleRefresh} disabled={refreshing} className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"><RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />{refreshing ? 'Atualizando...' : 'Atualizar'}</button>
          </div>
        </div>

        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        {info && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{info}</div>}

        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:w-96">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3"><Search className="h-5 w-5 text-gray-400" /></div>
            <input type="text" className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm leading-5 placeholder-gray-400 shadow-sm focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500" placeholder="Buscar por nome ou chave..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="flex w-full items-center gap-3 sm:w-auto">
            <select className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-700 shadow-sm focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 sm:w-48" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}>
              <option value="all">Todos os status</option>
              <option value="enabled">Ativas</option>
              <option value="paused">Pausadas</option>
            </select>
            <div className="flex gap-1 rounded-lg border border-gray-300 bg-white p-1 shadow-sm">
              <button onClick={() => setViewMode('grid')} className={`rounded-md p-1.5 ${viewMode === 'grid' ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}><LayoutGrid className="h-5 w-5" /></button>
              <button onClick={() => setViewMode('list')} className={`rounded-md p-1.5 ${viewMode === 'list' ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}><List className="h-5 w-5" /></button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500 shadow-sm">Carregando rotinas...</div>
        ) : (
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3' : 'flex flex-col gap-4'}>
            {filteredAutomations.map((automation) => (
              <article key={automation.id} className="flex h-full flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
                <div className="flex items-start justify-between p-5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">{automation.key}</p>
                    <h3 className="mt-1 text-lg font-bold text-gray-900">{automation.name}</h3>
                    <span className={`mt-2 inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusBadge(automation)}`}>{statusLabel(automation)}</span>
                  </div>
                  <button onClick={() => openEditModal(automation)} className="rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-50 hover:text-gray-700"><Settings2 className="h-4 w-4" /></button>
                </div>
                <div className="flex-grow border-y border-gray-100 bg-gray-50 px-5 py-3 text-sm">
                  <div className="flex items-center justify-between py-1"><span className="text-gray-500">Ultima execucao</span><span className="font-medium text-gray-700">{formatDate(automation.last_run_at)}</span></div>
                  <div className="flex items-center justify-between py-1"><span className="text-gray-500">Proxima execucao</span><span className="font-medium text-gray-700">{formatDate(automation.next_run_at)}</span></div>
                  <div className="flex items-center justify-between py-1"><span className="text-gray-500">CRON</span><code className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">{automation.schedule_cron || 'manual'}</code></div>
                  <div className="flex items-center justify-between py-1"><span className="text-gray-500">Tarefas</span><span className="font-medium text-gray-700">{Array.isArray(automation.params_json?.tasks) ? automation.params_json.tasks.length : 0}</span></div>
                </div>
                <div className="mt-auto flex gap-2 p-5">
                  <button onClick={() => handleRunNow(automation)} disabled={runningId === automation.id} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-600 disabled:opacity-60"><Play className="h-4 w-4" />{runningId === automation.id ? 'Executando...' : 'Executar'}</button>
                  <button onClick={() => handleQuickToggle(automation)} className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50">{automation.is_enabled ? 'Pausar' : 'Ativar'}</button>
                </div>
              </article>
            ))}

            {filteredAutomations.length === 0 && <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">Nenhuma rotina encontrada para os filtros aplicados.</div>}
          </div>
        )}

        <section className="mt-10 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2 className="text-lg font-bold text-gray-900">Ultimas execucoes</h2>
            <p className="text-sm text-gray-500">Historico das 50 execucoes mais recentes.</p>
          </div>
          {runs.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">Nenhuma execucao registrada.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600"><tr><th className="px-6 py-3 text-left font-semibold">Rotina</th><th className="px-6 py-3 text-left font-semibold">Status</th><th className="px-6 py-3 text-left font-semibold">Inicio</th><th className="px-6 py-3 text-left font-semibold">Fim</th><th className="px-6 py-3 text-left font-semibold">Resumo</th></tr></thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-gray-100">
                      <td className="px-6 py-3 font-medium text-gray-700">{run.automation_name}</td>
                      <td className="px-6 py-3"><span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${run.status === 'success' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{run.status}</span></td>
                      <td className="px-6 py-3 text-gray-500">{new Date(run.started_at).toLocaleString('pt-BR')}</td>
                      <td className="px-6 py-3 text-gray-500">{run.finished_at ? new Date(run.finished_at).toLocaleString('pt-BR') : '-'}</td>
                      <td className="px-6 py-3"><button onClick={() => setSelectedRun(run)} className="font-semibold text-cyan-600 hover:text-cyan-700">{run.summary_json?.message || 'Ver detalhes'}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {editOpen && editForm && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-end justify-center px-4 pb-20 pt-4 text-center sm:block sm:p-0">
            <div className="fixed inset-0" aria-hidden="true"><div className="absolute inset-0 bg-gray-500 opacity-75" onClick={() => setEditOpen(false)}></div></div>
            <span className="hidden sm:inline-block sm:h-screen sm:align-middle" aria-hidden="true">&#8203;</span>
            <div className="inline-block transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl sm:align-middle sm:p-6">
              <div className="absolute right-0 top-0 pr-4 pt-4"><button className="rounded-md bg-white text-gray-400 hover:text-gray-500" onClick={() => setEditOpen(false)}><X className="h-5 w-5" /></button></div>
              <h3 className="text-lg font-bold text-gray-900">Editar rotina</h3>
              <p className="mt-1 text-sm text-gray-500">Altere nome, agendamento e tarefas.</p>
              <div className="mt-4 space-y-4">
                {editValidation.formErrors.length > 0 && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {editValidation.formErrors.join(' ')}
                  </div>
                )}
                <div><label className="mb-1 block text-xs font-semibold text-gray-700">Nome</label><input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={editForm.name} onChange={(e) => setEditForm((prev) => (prev ? { ...prev, name: e.target.value } : prev))} /></div>
                <div><label className="mb-1 block text-xs font-semibold text-gray-700">CRON</label><input className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm" value={editForm.schedule_cron} onChange={(e) => setEditForm((prev) => (prev ? { ...prev, schedule_cron: e.target.value } : prev))} placeholder="0 8 * * 1" /><p className="mt-1 text-xs text-gray-500">Deixe vazio para execucao apenas manual.</p></div>
                <div className="flex items-center gap-2"><input id="enabled-routine" type="checkbox" checked={editForm.is_enabled} onChange={(e) => setEditForm((prev) => (prev ? { ...prev, is_enabled: e.target.checked } : prev))} /><label htmlFor="enabled-routine" className="text-sm text-gray-700">Rotina habilitada</label></div>
                <div className="flex items-center gap-2"><input id="simulation-routine" type="checkbox" checked={editForm.simulation} onChange={(e) => setEditForm((prev) => (prev ? { ...prev, simulation: e.target.checked } : prev))} /><label htmlFor="simulation-routine" className="text-sm text-gray-700">Executar em modo simulacao</label></div>
                <TaskEditor
                  tasks={editForm.tasks}
                  onChange={(tasks) => setEditForm((prev) => (prev ? { ...prev, tasks } : prev))}
                  taskErrors={editValidation.taskErrors}
                  promptTemplatesCatalog={filteredTemplatesCatalog}
                />
              </div>
              <div className="mt-6 flex justify-end gap-3"><button onClick={() => setEditOpen(false)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">Cancelar</button><button onClick={handleSaveEdit} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60"><Save className="h-4 w-4" />{saving ? 'Salvando...' : 'Salvar'}</button></div>
            </div>
          </div>
        </div>
      )}

      {createOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-end justify-center px-4 pb-20 pt-4 text-center sm:block sm:p-0">
            <div className="fixed inset-0" aria-hidden="true"><div className="absolute inset-0 bg-gray-500 opacity-75" onClick={() => setCreateOpen(false)}></div></div>
            <span className="hidden sm:inline-block sm:h-screen sm:align-middle" aria-hidden="true">&#8203;</span>
            <div className="inline-block transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl sm:align-middle sm:p-6">
              <div className="absolute right-0 top-0 pr-4 pt-4"><button className="rounded-md bg-white text-gray-400 hover:text-gray-500" onClick={() => setCreateOpen(false)}><X className="h-5 w-5" /></button></div>
              <h3 className="text-lg font-bold text-gray-900">Nova rotina</h3>
              <p className="mt-1 text-sm text-gray-500">Crie uma rotina com agendamento e tarefas.</p>
              <div className="mt-4 space-y-4">
                {createValidation.formErrors.length > 0 && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {createValidation.formErrors.join(' ')}
                  </div>
                )}
                <div><label className="mb-1 block text-xs font-semibold text-gray-700">Nome</label><input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" value={createForm.name} onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))} /></div>
                <div><label className="mb-1 block text-xs font-semibold text-gray-700">CRON</label><input className="w-full rounded-lg border border-gray-300 px-3 py-2 font-mono text-sm" value={createForm.schedule_cron} onChange={(e) => setCreateForm((prev) => ({ ...prev, schedule_cron: e.target.value }))} placeholder="0 8 * * 1" /><p className="mt-1 text-xs text-gray-500">Deixe vazio para execucao apenas manual.</p></div>
                <div className="flex items-center gap-2"><input id="enabled-create-routine" type="checkbox" checked={createForm.is_enabled} onChange={(e) => setCreateForm((prev) => ({ ...prev, is_enabled: e.target.checked }))} /><label htmlFor="enabled-create-routine" className="text-sm text-gray-700">Rotina habilitada</label></div>
                <div className="flex items-center gap-2"><input id="simulation-create-routine" type="checkbox" checked={createForm.simulation} onChange={(e) => setCreateForm((prev) => ({ ...prev, simulation: e.target.checked }))} /><label htmlFor="simulation-create-routine" className="text-sm text-gray-700">Executar em modo simulacao</label></div>
                <TaskEditor
                  tasks={createForm.tasks}
                  onChange={(tasks) => setCreateForm((prev) => ({ ...prev, tasks }))}
                  taskErrors={createValidation.taskErrors}
                  promptTemplatesCatalog={filteredTemplatesCatalog}
                />
              </div>
              <div className="mt-6 flex justify-end gap-3"><button onClick={() => setCreateOpen(false)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">Cancelar</button><button onClick={handleCreateRoutine} disabled={saving} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60"><Save className="h-4 w-4" />{saving ? 'Salvando...' : 'Criar'}</button></div>
            </div>
          </div>
        </div>
      )}

      {selectedRun && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-end justify-center px-4 pb-20 pt-4 text-center sm:block sm:p-0">
            <div className="fixed inset-0" aria-hidden="true"><div className="absolute inset-0 bg-gray-500 opacity-75" onClick={() => setSelectedRun(null)}></div></div>
            <span className="hidden sm:inline-block sm:h-screen sm:align-middle" aria-hidden="true">&#8203;</span>
            <div className="inline-block transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:align-middle sm:p-6">
              <div className="absolute right-0 top-0 pr-4 pt-4"><button className="rounded-md bg-white text-gray-400 hover:text-gray-500" onClick={() => setSelectedRun(null)}><X className="h-5 w-5" /></button></div>
              <h3 className="text-lg font-bold text-gray-900">Execucao: {selectedRun.automation_name}</h3>
              <div className="mt-3 space-y-1 text-sm text-gray-600"><p>Status: <span className="font-semibold text-gray-800">{selectedRun.status}</span></p><p>Inicio: {new Date(selectedRun.started_at).toLocaleString('pt-BR')}</p><p>Fim: {selectedRun.finished_at ? new Date(selectedRun.finished_at).toLocaleString('pt-BR') : '-'}</p></div>
              <div className="mt-4"><h4 className="mb-2 text-sm font-bold text-gray-700">Resumo</h4><pre className="whitespace-pre-wrap rounded border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700">{JSON.stringify(selectedRun.summary_json, null, 2)}</pre></div>
              {selectedRun.error_text && <div className="mt-4"><h4 className="mb-2 text-sm font-bold text-red-600">Erro</h4><pre className="whitespace-pre-wrap rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">{selectedRun.error_text}</pre></div>}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default RoutinesPage;
