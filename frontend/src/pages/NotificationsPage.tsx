import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, Copy, Eye, Plus, RefreshCw, Save, Send, Trash2, X, XCircle } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { Automation, listAutomations } from '../api/automations';
import {
  NotificationHistory,
  NotificationRule,
  NotificationTemplate,
  NotificationTemplateVariables,
  approveNotification,
  cancelNotification,
  createNotificationRule,
  createNotificationTemplate,
  deleteNotificationRule,
  deleteNotificationTemplate,
  listNotificationRules,
  listNotificationTemplates,
  listNotificationTemplateVariables,
  listNotifications,
  retryNotification,
  updateNotificationRule,
  updateNotificationTemplate,
} from '../api/notifications';

const defaultTemplate = {
  id: null as number | null,
  name: 'Pendencia por responsavel',
  variable_automation_id: '',
  channel: 'email',
  subject: 'ASMDIGITAL - Pendencia da rotina {{nome_rotina}}',
  body: 'Ola, {{nome_responsavel}}.\n\nA rotina "{{nome_rotina}}" identificou uma pendencia relacionada ao projeto "{{nome_projeto}}".\n\nStatus: {{status}}\nDias em atraso: {{dias_atraso}}\nData da execucao: {{data_execucao}}\n\nAcao sugerida:\n{{acao_sugerida}}\n\nAcesse o relatorio completo em:\n{{link_relatorio}}',
  is_active: true,
};

const defaultRule = {
  id: null as number | null,
  automation_id: '',
  template_id: '',
  is_active: true,
  recipient_type: 'responsavel',
  preferred_channel: 'email',
  fallback_channel: 'internal',
  send_condition: '',
  requires_approval: false,
  notify_manager: false,
};

const channelLabel: Record<string, string> = {
  email: 'Email',
  teams: 'Teams',
  internal: 'Interna',
};

const statusStyles: Record<string, string> = {
  enviado: 'bg-emerald-100 text-emerald-700',
  simulado: 'bg-amber-100 text-amber-700',
  erro: 'bg-red-100 text-red-700',
  pendente: 'bg-slate-100 text-slate-700',
  aguardando_aprovacao: 'bg-blue-100 text-blue-700',
  cancelado: 'bg-slate-200 text-slate-600',
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '-';
  return new Date(value).toLocaleString('pt-BR');
};

const canRetryNotification = (item: NotificationHistory) =>
  item.status === 'erro' || (item.status === 'simulado' && Boolean(item.error));

const templateVariables = [
  { key: 'nome_destinatario', label: 'Nome de quem recebe' },
  { key: 'nome_responsavel', label: 'Responsavel do resultado' },
  { key: 'email', label: 'Email do destinatario' },
  { key: 'nome_rotina', label: 'Nome da rotina' },
  { key: 'data_execucao', label: 'Data da execucao' },
  { key: 'link_relatorio', label: 'Link do relatorio' },
  { key: 'link_demanda', label: 'Link direto da demanda' },
  { key: 'demanda_id', label: 'ID da demanda' },
  { key: 'nome_projeto', label: 'Projeto/entrega' },
  { key: 'project_id', label: 'ID do projeto' },
  { key: 'status', label: 'Status do item' },
  { key: 'dias_atraso', label: 'Dias em atraso' },
  { key: 'acao_sugerida', label: 'Acao sugerida' },
  { key: 'subject', label: 'Titulo/demanda Redmine' },
  { key: 'assigned_to', label: 'Atribuido para Redmine' },
  { key: 'due_date', label: 'Data prevista Redmine' },
  { key: 'updated_on', label: 'Alterado em Redmine' },
];

const NotificationsPage: React.FC = () => {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [history, setHistory] = useState<NotificationHistory[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);
  const [historyHasNext, setHistoryHasNext] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  const [selectedNotification, setSelectedNotification] = useState<NotificationHistory | null>(null);
  const [discoveredVariables, setDiscoveredVariables] = useState<NotificationTemplateVariables | null>(null);
  const [variablesLoading, setVariablesLoading] = useState(false);
  const [templateEditorOpen, setTemplateEditorOpen] = useState(false);
  const [ruleEditorOpen, setRuleEditorOpen] = useState(false);
  const [variableAutomationId, setVariableAutomationId] = useState('');
  const [templateForm, setTemplateForm] = useState({ ...defaultTemplate });
  const [ruleForm, setRuleForm] = useState({ ...defaultRule });
  const templateBodyRef = useRef<HTMLTextAreaElement | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.id === templateForm.id) || null,
    [templates, templateForm.id],
  );

  const selectedRule = useMemo(
    () => rules.find((item) => item.id === ruleForm.id) || null,
    [rules, ruleForm.id],
  );

  const pendingApprovalCount = history.filter((item) => item.status === 'aguardando_aprovacao').length;
  const errorCount = history.filter((item) => item.status === 'erro').length;
  const sentCount = history.filter((item) => ['enviado', 'simulado'].includes(item.status)).length;
  const activeAutomationId = Number(variableAutomationId || ruleForm.automation_id || 0);
  const mergedTemplateVariables = useMemo(() => {
    const keys = new Set(templateVariables.map((item) => item.key));
    (discoveredVariables?.variables || []).forEach((key) => keys.add(key));
    return Array.from(keys).sort((left, right) => left.localeCompare(right));
  }, [discoveredVariables]);

  const load = async (page = historyPage, pageSize = historyPageSize) => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      const [automationData, templateData, ruleData, historyData] = await Promise.all([
        listAutomations(),
        listNotificationTemplates(),
        listNotificationRules(),
        listNotifications({ limit: pageSize + 1, offset }),
      ]);
      setAutomations(automationData);
      setTemplates(templateData);
      setRules(ruleData);
      setHistory(historyData.slice(0, pageSize));
      setHistoryHasNext(historyData.length > pageSize);
    } catch {
      setError('Nao foi possivel carregar notificacoes.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [historyPage, historyPageSize]);

  useEffect(() => {
    let active = true;
    if (!activeAutomationId) {
      setDiscoveredVariables(null);
      return;
    }
    setVariablesLoading(true);
    listNotificationTemplateVariables(activeAutomationId)
      .then((data) => {
        if (active) setDiscoveredVariables(data);
      })
      .catch(() => {
        if (active) setDiscoveredVariables(null);
      })
      .finally(() => {
        if (active) setVariablesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activeAutomationId]);

  const clearTemplate = () => {
    setTemplateForm({ ...defaultTemplate, id: null });
    setVariableAutomationId('');
    setTemplateEditorOpen(true);
  };

  const editTemplate = (template: NotificationTemplate) => {
    const mappingAutomationId = template.variable_automation_id ? String(template.variable_automation_id) : '';
    setTemplateForm({
      id: template.id,
      name: template.name,
      variable_automation_id: mappingAutomationId,
      channel: template.channel,
      subject: template.subject || '',
      body: template.body,
      is_active: template.is_active,
    });
    setVariableAutomationId(mappingAutomationId);
    setTemplateEditorOpen(true);
  };

  const duplicateTemplate = (template: NotificationTemplate) => {
    const mappingAutomationId = template.variable_automation_id ? String(template.variable_automation_id) : '';
    setTemplateForm({
      id: null,
      name: `${template.name} - copia`,
      variable_automation_id: mappingAutomationId,
      channel: template.channel,
      subject: template.subject || '',
      body: template.body,
      is_active: template.is_active,
    });
    setVariableAutomationId(mappingAutomationId);
    setTemplateEditorOpen(true);
  };

  const insertTemplateVariable = (key: string) => {
    const token = `{{${key}}}`;
    const textarea = templateBodyRef.current;
    if (!textarea) {
      setTemplateForm((current) => ({ ...current, body: `${current.body}${token}` }));
      return;
    }
    const start = textarea.selectionStart ?? templateForm.body.length;
    const end = textarea.selectionEnd ?? templateForm.body.length;
    const nextBody = `${templateForm.body.slice(0, start)}${token}${templateForm.body.slice(end)}`;
    setTemplateForm({ ...templateForm, body: nextBody });
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const saveTemplate = async () => {
    setError(null);
    setNotice(null);
    try {
      const payload = {
        name: templateForm.name.trim(),
        variable_automation_id: variableAutomationId ? Number(variableAutomationId) : null,
        channel: templateForm.channel,
        subject: templateForm.subject || null,
        body: templateForm.body,
        is_active: templateForm.is_active,
      };
      if (!payload.name || !payload.body.trim()) {
        setError('Informe nome e corpo do template.');
        return;
      }
      let saved: NotificationTemplate;
      if (templateForm.id) {
        saved = await updateNotificationTemplate(templateForm.id, payload);
      } else {
        saved = await createNotificationTemplate(payload);
      }
      setTemplateForm({
        id: saved.id,
        name: saved.name,
        variable_automation_id: saved.variable_automation_id ? String(saved.variable_automation_id) : '',
        channel: saved.channel,
        subject: saved.subject || '',
        body: saved.body,
        is_active: saved.is_active,
      });
      setVariableAutomationId(saved.variable_automation_id ? String(saved.variable_automation_id) : '');
      setNotice(`Template "${saved.name}" salvo.`);
      await load();
      setTemplateEditorOpen(false);
    } catch {
      setError('Falha ao salvar template.');
    }
  };

  const removeTemplate = async (template: NotificationTemplate) => {
    setError(null);
    try {
      await deleteNotificationTemplate(template.id);
      if (templateForm.id === template.id) {
        clearTemplate();
      }
      await load();
    } catch {
      setError('Falha ao excluir template. Verifique se ele esta vinculado a alguma regra.');
    }
  };

  const clearRule = () => {
    setRuleForm({ ...defaultRule, id: null });
    setRuleEditorOpen(true);
  };

  const editRule = (rule: NotificationRule) => {
    setRuleForm({
      id: rule.id,
      automation_id: String(rule.automation_id),
      template_id: rule.template_id ? String(rule.template_id) : '',
      is_active: rule.is_active,
      recipient_type: rule.recipient_type,
      preferred_channel: rule.preferred_channel,
      fallback_channel: rule.fallback_channel || '',
      send_condition: rule.send_condition || '',
      requires_approval: rule.requires_approval,
      notify_manager: rule.notify_manager,
    });
    setVariableAutomationId(String(rule.automation_id));
    setRuleEditorOpen(true);
  };

  const saveRule = async () => {
    setError(null);
    try {
      if (!ruleForm.automation_id) {
        setError('Selecione uma rotina para a regra.');
        return;
      }
      const payload = {
        automation_id: Number(ruleForm.automation_id),
        template_id: ruleForm.template_id ? Number(ruleForm.template_id) : null,
        is_active: ruleForm.is_active,
        send_condition: ruleForm.send_condition || null,
        recipient_type: ruleForm.recipient_type,
        preferred_channel: ruleForm.preferred_channel,
        fallback_channel: ruleForm.fallback_channel || null,
        requires_approval: ruleForm.requires_approval,
        notify_manager: ruleForm.notify_manager,
        manager_condition: null,
        params_json: {},
      };
      if (ruleForm.id) {
        await updateNotificationRule(ruleForm.id, payload);
      } else {
        await createNotificationRule(payload);
      }
      clearRule();
      await load();
      setRuleEditorOpen(false);
    } catch {
      setError('Falha ao salvar regra.');
    }
  };

  const removeRule = async (rule: NotificationRule) => {
    setError(null);
    try {
      await deleteNotificationRule(rule.id);
      if (ruleForm.id === rule.id) {
        clearRule();
      }
      await load();
    } catch {
      setError('Falha ao excluir regra.');
    }
  };

  const retry = async (id: number) => {
    setError(null);
    setNotice(null);
    setRetryingId(id);
    try {
      const result = await retryNotification(id);
      await load();
      if (result.status === 'enviado') {
        setNotice(`Notificacao #${id} enviada com sucesso.`);
      } else if (result.status === 'simulado') {
        setNotice(`Notificacao #${id} reprocessada em modo simulado.`);
      } else if (result.status === 'erro') {
        setError(`Reenvio da notificacao #${id} falhou: ${result.error || 'erro nao informado'}`);
      } else {
        setNotice(`Notificacao #${id} reprocessada com status ${result.status}.`);
      }
    } catch {
      setError('Falha ao reenviar notificacao.');
    } finally {
      setRetryingId(null);
    }
  };

  const approve = async (id: number) => {
    setError(null);
    setNotice(null);
    setApprovingId(id);
    try {
      const result = await approveNotification(id);
      await load();
      if (result.status === 'enviado') {
        setNotice(`Notificacao #${id} aprovada e enviada.`);
      } else if (result.status === 'erro') {
        setError(`Aprovacao da notificacao #${id} falhou: ${result.error || 'erro nao informado'}`);
      } else {
        setNotice(`Notificacao #${id} aprovada com status ${result.status}.`);
      }
    } catch {
      setError('Falha ao aprovar envio.');
    } finally {
      setApprovingId(null);
    }
  };

  const cancel = async (id: number) => {
    setError(null);
    setNotice(null);
    setCancelingId(id);
    try {
      await cancelNotification(id);
      await load();
      setNotice(`Notificacao #${id} cancelada.`);
    } catch {
      setError('Falha ao cancelar envio.');
    } finally {
      setCancelingId(null);
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Notificacoes inteligentes"
        subtitle="Crie templates reutilizaveis, vincule regras por rotina e acompanhe os envios."
      />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
          {notice}
        </div>
      )}

      <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:min-w-[760px]">
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Templates</p>
            <p className="mt-2 text-2xl font-black text-slate-900">{templates.length}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">Regras</p>
            <p className="mt-2 text-2xl font-black text-slate-900">{rules.length}</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-600">Enviadas</p>
            <p className="mt-2 text-2xl font-black text-emerald-900">{sentCount}</p>
          </div>
          <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-4 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-wide text-blue-600">Aprovacao</p>
            <p className="mt-2 text-2xl font-black text-blue-900">{pendingApprovalCount}</p>
            {errorCount > 0 && <p className="mt-1 text-xs font-semibold text-red-600">{errorCount} com erro</p>}
          </div>
        </div>
        <button
          onClick={() => load()}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 sm:w-auto"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      <section className="grid grid-cols-1 gap-5">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">1. Templates salvos</h2>
              <p className="text-sm text-slate-500">Mensagens reutilizaveis por regras diferentes.</p>
            </div>
            <button
              onClick={clearTemplate}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white"
              title="Novo template"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          <div className="max-h-[520px] divide-y divide-slate-100 overflow-y-auto">
            {templates.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhum template criado.</p>}
            {templates.map((template) => (
              <article key={template.id} className={`p-4 transition ${selectedTemplate?.id === template.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="break-words text-sm font-bold text-slate-900">{template.name}</h3>
                    <p className="mt-1 text-xs text-slate-500">
                      {channelLabel[template.channel] || template.channel} · {template.is_active ? 'Ativo' : 'Inativo'}
                    </p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => editTemplate(template)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-white">
                    Editar
                  </button>
                  <button onClick={() => duplicateTemplate(template)} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-white">
                    <Copy className="h-3.5 w-3.5" />
                    Duplicar
                  </button>
                  <button onClick={() => removeTemplate(template)} className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5" />
                    Excluir
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {templateForm.id ? `Editar template #${templateForm.id}` : 'Novo template'}
              </h2>
              <p className="text-sm text-slate-500">Depois de salvar, use este template em uma regra por rotina.</p>
            </div>
            <button onClick={saveTemplate} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-white hover:bg-primary-dark sm:w-auto">
              <Save className="h-4 w-4" />
              Salvar template
            </button>
          </div>
          <div className="mt-5 space-y-4">
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Nome do template"
              value={templateForm.name}
              onChange={(event) => setTemplateForm({ ...templateForm, name: event.target.value })}
            />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
              <select
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={templateForm.channel}
                onChange={(event) => setTemplateForm({ ...templateForm, channel: event.target.value })}
              >
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
              <input
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="Assunto"
                value={templateForm.subject || ''}
                onChange={(event) => setTemplateForm({ ...templateForm, subject: event.target.value })}
              />
            </div>
            <textarea
              ref={templateBodyRef}
              className="h-64 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm sm:h-72"
              value={templateForm.body}
              onChange={(event) => setTemplateForm({ ...templateForm, body: event.target.value })}
            />
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Variaveis disponiveis</p>
              <p className="mt-1 text-xs text-slate-500">
                Clique para inserir no texto. Selecione uma rotina na regra para carregar campos reais das ultimas execucoes.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {mergedTemplateVariables.map((key) => {
                  const known = templateVariables.find((item) => item.key === key);
                  const sample = discoveredVariables?.samples?.[key];
                  const title = known?.label || (sample !== undefined ? `Exemplo: ${String(sample).slice(0, 120)}` : 'Campo detectado no resultado');
                  return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => insertTemplateVariable(key)}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 hover:border-primary hover:text-primary"
                    title={title}
                  >
                    {`{{${key}}}`}
                  </button>
                  );
                })}
              </div>
              <div className="mt-3 text-xs text-slate-500">
                {variablesLoading && 'Buscando variaveis da rotina...'}
                {!variablesLoading && activeAutomationId > 0 && discoveredVariables && (
                  <span>
                    {discoveredVariables.source_run_ids.length > 0
                      ? `Campos detectados nas execucoes: ${discoveredVariables.source_run_ids.join(', ')}.`
                      : 'Ainda nao ha execucoes com resultado estruturado para esta rotina.'}
                  </span>
                )}
                {!activeAutomationId && 'Nenhuma rotina selecionada na regra atual.'}
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <input
                type="checkbox"
                checked={templateForm.is_active}
                onChange={(event) => setTemplateForm({ ...templateForm, is_active: event.target.checked })}
              />
              Template ativo
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              Como funciona: o sistema substitui cada <code>{'{{variavel}}'}</code> usando os dados da rotina e da linha do relatorio.
              Exemplo Redmine: <code>{'{{subject}}'}</code> mostra o titulo da demanda e <code>{'{{assigned_to}}'}</code> mostra o atribuido para.
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 grid grid-cols-1 gap-5">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-lg font-bold text-slate-900">2. Regras por rotina</h2>
              <p className="text-sm text-slate-500">Escolha quando e para quem enviar.</p>
            </div>
            <button
              onClick={clearRule}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white"
              title="Nova regra"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          <div className="max-h-[520px] divide-y divide-slate-100 overflow-y-auto">
            {rules.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhuma regra criada.</p>}
            {rules.map((rule) => (
              <article key={rule.id} className={`p-4 transition ${selectedRule?.id === rule.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}>
                <h3 className="break-words text-sm font-bold text-slate-900">{rule.automation_name || `Rotina #${rule.automation_id}`}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Template: {rule.template_name || 'Padrao'} · Canal: {channelLabel[rule.preferred_channel] || rule.preferred_channel}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Destino: {rule.recipient_type} · Condicao: {rule.send_condition || 'sempre'}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button onClick={() => editRule(rule)} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-white">
                    Editar
                  </button>
                  <button onClick={() => removeRule(rule)} className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-bold text-red-600 hover:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5" />
                    Excluir
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {ruleForm.id ? `Editar regra #${ruleForm.id}` : 'Nova regra'}
              </h2>
              <p className="text-sm text-slate-500">Vincule uma rotina a um template e defina os canais.</p>
            </div>
            <button onClick={saveRule} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-white hover:bg-primary-dark sm:w-auto">
              <Save className="h-4 w-4" />
              Salvar regra
            </button>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Rotina
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={ruleForm.automation_id}
                onChange={(event) => setRuleForm({ ...ruleForm, automation_id: event.target.value })}
              >
                <option value="">Selecione uma rotina</option>
                {automations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Template
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={ruleForm.template_id}
                onChange={(event) => setRuleForm({ ...ruleForm, template_id: event.target.value })}
              >
                <option value="">Template padrao</option>
                {templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Destinatario
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={ruleForm.recipient_type}
                onChange={(event) => setRuleForm({ ...ruleForm, recipient_type: event.target.value })}
              >
                <option value="responsavel">Responsavel do resultado</option>
                <option value="gestor">Gestor do responsavel</option>
                <option value="funcionario_fixo">Funcionario fixo</option>
              </select>
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Condicao
              <input
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                placeholder="sempre, deve_notificar, status_atrasado"
                value={ruleForm.send_condition}
                onChange={(event) => setRuleForm({ ...ruleForm, send_condition: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Canal preferencial
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={ruleForm.preferred_channel}
                onChange={(event) => setRuleForm({ ...ruleForm, preferred_channel: event.target.value })}
              >
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
            </label>
            <label className="space-y-1 text-sm font-semibold text-slate-700">
              Canal fallback
              <select
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                value={ruleForm.fallback_channel}
                onChange={(event) => setRuleForm({ ...ruleForm, fallback_channel: event.target.value })}
              >
                <option value="">Sem fallback</option>
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <input type="checkbox" checked={ruleForm.is_active} onChange={(event) => setRuleForm({ ...ruleForm, is_active: event.target.checked })} />
              Regra ativa
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <input type="checkbox" checked={ruleForm.requires_approval} onChange={(event) => setRuleForm({ ...ruleForm, requires_approval: event.target.checked })} />
              Exige aprovacao
            </label>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <input type="checkbox" checked={ruleForm.notify_manager} onChange={(event) => setRuleForm({ ...ruleForm, notify_manager: event.target.checked })} />
              Tambem notificar gestor do responsavel
            </label>
          </div>
        </div>
      </section>

      <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">3. Historico de notificacoes</h2>
            <p className="text-sm text-slate-500">Ultimos registros de envio, simulacao e erro.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-bold">
            <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-700">{pendingApprovalCount} aguardando aprovacao nesta pagina</span>
            <span className="rounded-full bg-red-100 px-3 py-1 text-red-700">{errorCount} com erro nesta pagina</span>
            <select
              className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-bold text-slate-600"
              value={historyPageSize}
              onChange={(event) => {
                setHistoryPageSize(Number(event.target.value));
                setHistoryPage(1);
              }}
            >
              <option value={10}>10 por pagina</option>
              <option value={25}>25 por pagina</option>
              <option value={50}>50 por pagina</option>
            </select>
          </div>
        </div>

        <div className="divide-y divide-slate-100 md:hidden">
          {history.map((item) => (
            <article key={item.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="break-words text-sm font-bold text-slate-900">{item.automation_name || '-'}</h3>
                  <p className="mt-1 text-xs text-slate-500">{formatDateTime(item.sent_at || item.data_envio)}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-bold ${statusStyles[item.status] || 'bg-slate-100 text-slate-700'}`}>
                  {item.status}
                </span>
              </div>
              <div className="mt-3 rounded-xl bg-slate-50 p-3">
                <p className="text-xs font-bold uppercase text-slate-400">Funcionario</p>
                <p className="mt-1 break-words text-sm font-semibold text-slate-800">{item.employee_name || '-'}</p>
                <p className="break-words text-xs text-slate-500">{item.recipient || '-'}</p>
              </div>
              <div className="mt-3">
                <p className="break-words text-sm font-bold text-slate-800">{item.subject || '-'}</p>
                <p className={`mt-1 line-clamp-3 break-words text-xs ${item.status === 'erro' || item.status === 'simulado' ? 'text-red-600' : 'text-slate-500'}`}>
                  {item.error || item.message || '-'}
                </p>
                <p className="mt-2 text-xs font-semibold text-slate-500">
                  Tentativas: {item.attempts || 0}
                </p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={() => setSelectedNotification(item)}
                  className="inline-flex flex-1 items-center justify-center gap-1 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700"
                >
                  <Eye className="h-4 w-4" />
                  Detalhes
                </button>
                {item.status === 'aguardando_aprovacao' && (
                  <>
                    <button
                      onClick={() => approve(item.id)}
                      disabled={approvingId === item.id || cancelingId === item.id}
                      className="inline-flex flex-1 items-center justify-center gap-1 rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {approvingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      {approvingId === item.id ? 'Aprovando...' : 'Aprovar'}
                    </button>
                    <button
                      onClick={() => cancel(item.id)}
                      disabled={approvingId === item.id || cancelingId === item.id}
                      className="inline-flex flex-1 items-center justify-center gap-1 rounded-xl border border-red-200 px-3 py-2 text-xs font-bold text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {cancelingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                      {cancelingId === item.id ? 'Cancelando...' : 'Cancelar'}
                    </button>
                  </>
                )}
                {canRetryNotification(item) && (
                  <button
                    onClick={() => retry(item.id)}
                    disabled={retryingId === item.id}
                    className="inline-flex w-full items-center justify-center gap-1 rounded-xl bg-cyan-700 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {retryingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    {retryingId === item.id ? 'Reenviando...' : 'Reenviar'}
                  </button>
                )}
              </div>
            </article>
          ))}
          {history.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-500">Nenhuma notificacao registrada.</p>}
        </div>

        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-[980px] table-fixed text-sm">
            <colgroup>
              <col className="w-[24%]" />
              <col className="w-[24%]" />
              <col className="w-[16%]" />
              <col className="w-[24%]" />
              <col className="w-[12%]" />
            </colgroup>
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-5 py-3 text-left">Origem</th>
                <th className="px-5 py-3 text-left">Destinatário</th>
                <th className="px-5 py-3 text-left">Envio</th>
                <th className="px-5 py-3 text-left">Mensagem</th>
                <th className="px-5 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id} className="border-t border-slate-100 align-top transition hover:bg-slate-50/80">
                  <td className="px-5 py-4">
                    <div className="line-clamp-2 font-bold text-slate-900">{item.automation_name || '-'}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                      <span>#{item.id}</span>
                      {item.execution_id && <span>Execução #{item.execution_id}</span>}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="line-clamp-2 font-bold text-slate-900">{item.employee_name || '-'}</div>
                    <div className="mt-1 truncate text-xs text-slate-500">{item.recipient || '-'}</div>
                    <div className="mt-2 inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
                      {channelLabel[item.channel] || item.channel}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className={`rounded-full px-2 py-1 text-xs font-bold ${statusStyles[item.status] || 'bg-slate-100 text-slate-700'}`}>
                      {item.status}
                    </span>
                    <div className="mt-2 text-xs text-slate-500">{formatDateTime(item.sent_at || item.data_envio)}</div>
                    <div className="mt-1 text-xs text-slate-500">Tentativas: {item.attempts || 0}</div>
                    {item.simulation && <div className="mt-1 text-xs font-semibold text-amber-700">simulação</div>}
                  </td>
                  <td className="px-5 py-4">
                    <div className="line-clamp-2 font-bold text-slate-900">{item.subject || '-'}</div>
                    <div className={`mt-1 line-clamp-3 text-xs leading-5 ${item.status === 'erro' || item.status === 'simulado' ? 'text-red-600' : 'text-slate-500'}`}>
                      {item.error || item.message || '-'}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex flex-col items-stretch gap-2">
                    <button
                      onClick={() => setSelectedNotification(item)}
                      className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-white"
                    >
                      <Eye className="h-4 w-4" />
                      Detalhes
                    </button>
                    {item.status === 'aguardando_aprovacao' && (
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => approve(item.id)}
                          disabled={approvingId === item.id || cancelingId === item.id}
                          className="inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {approvingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                          {approvingId === item.id ? 'Aprovando...' : 'Aprovar'}
                        </button>
                        <button
                          onClick={() => cancel(item.id)}
                          disabled={approvingId === item.id || cancelingId === item.id}
                          className="inline-flex items-center justify-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-xs font-bold text-red-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {cancelingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                          {cancelingId === item.id ? 'Cancelando...' : 'Cancelar'}
                        </button>
                      </div>
                    )}
                    {canRetryNotification(item) && (
                      <button
                        onClick={() => retry(item.id)}
                        disabled={retryingId === item.id}
                        className="inline-flex items-center justify-center gap-1 rounded-lg bg-cyan-700 px-3 py-2 text-xs font-bold text-white disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {retryingId === item.id ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                        {retryingId === item.id ? 'Reenviando...' : 'Reenviar'}
                      </button>
                    )}
                    </div>
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">Nenhuma notificacao registrada.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold text-slate-500">
            Pagina {historyPage} {history.length > 0 && `- exibindo ${history.length} registro${history.length === 1 ? '' : 's'}`}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setHistoryPage((page) => Math.max(1, page - 1))}
              disabled={historyPage === 1 || loading}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Anterior
            </button>
            <button
              onClick={() => setHistoryPage((page) => page + 1)}
              disabled={!historyHasNext || loading}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Proxima
            </button>
          </div>
        </div>
      </section>

      {templateEditorOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 sm:items-center sm:p-4">
          <div className="flex max-h-[94vh] w-full flex-col overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:max-w-5xl sm:rounded-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                  {templateForm.id ? `Template #${templateForm.id}` : 'Novo template'}
                </p>
                <h3 className="mt-1 text-xl font-black text-slate-900">
                  {templateForm.id ? 'Editar template' : 'Criar template'}
                </h3>
              </div>
              <button
                onClick={() => setTemplateEditorOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
                aria-label="Fechar template"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="space-y-4 p-5">
                <label className="block text-sm font-bold text-slate-700">
                  Nome
                  <input
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    placeholder="Nome do template"
                    value={templateForm.name}
                    onChange={(event) => setTemplateForm({ ...templateForm, name: event.target.value })}
                  />
                </label>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <label className="block text-sm font-bold text-slate-700">
                    Canal
                    <select
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                      value={templateForm.channel}
                      onChange={(event) => setTemplateForm({ ...templateForm, channel: event.target.value })}
                    >
                      <option value="email">Email</option>
                      <option value="teams">Teams</option>
                      <option value="internal">Interna</option>
                    </select>
                  </label>
                  <label className="block text-sm font-bold text-slate-700">
                    Assunto
                    <input
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                      placeholder="Assunto"
                      value={templateForm.subject || ''}
                      onChange={(event) => setTemplateForm({ ...templateForm, subject: event.target.value })}
                    />
                  </label>
                </div>
                <label className="block text-sm font-bold text-slate-700">
                  Texto
                  <textarea
                    ref={templateBodyRef}
                    className="mt-1 h-[360px] w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm leading-6"
                    value={templateForm.body}
                    onChange={(event) => setTemplateForm({ ...templateForm, body: event.target.value })}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                  <input
                    type="checkbox"
                    checked={templateForm.is_active}
                    onChange={(event) => setTemplateForm({ ...templateForm, is_active: event.target.checked })}
                  />
                  Template ativo
                </label>
              </div>

              <aside className="border-t border-slate-100 bg-slate-50 p-5 lg:border-l lg:border-t-0">
                <label className="block text-sm font-bold text-slate-700">
                  Rotina para mapear variáveis
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-normal"
                    value={variableAutomationId}
                    onChange={(event) => {
                      setVariableAutomationId(event.target.value);
                      setTemplateForm({ ...templateForm, variable_automation_id: event.target.value });
                    }}
                  >
                    <option value="">Escolha uma rotina</option>
                    {automations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Variáveis</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Clique para inserir no ponto atual do texto.
                  </p>
                  <div className="mt-3 flex max-h-72 flex-wrap gap-2 overflow-y-auto pr-1">
                    {mergedTemplateVariables.map((key) => {
                      const known = templateVariables.find((item) => item.key === key);
                      const sample = discoveredVariables?.samples?.[key];
                      const title = known?.label || (sample !== undefined ? `Exemplo: ${String(sample).slice(0, 120)}` : 'Campo detectado no resultado');
                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() => insertTemplateVariable(key)}
                          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 hover:border-primary hover:text-primary"
                          title={title}
                        >
                          {`{{${key}}}`}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    {variablesLoading && 'Buscando variáveis da rotina...'}
                    {!variablesLoading && activeAutomationId > 0 && discoveredVariables?.source_run_ids.length
                      ? `Detectado nas execuções: ${discoveredVariables.source_run_ids.join(', ')}.`
                      : null}
                    {!variablesLoading && activeAutomationId > 0 && discoveredVariables && discoveredVariables.source_run_ids.length === 0
                      ? 'Ainda não há execução com resultado estruturado.'
                      : null}
                    {!activeAutomationId && 'Selecione uma rotina para sugerir campos reais.'}
                  </p>
                </div>
                <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-3 text-xs text-blue-800">
                  Campos fixos sempre disponíveis: <code>{'{{nome_rotina}}'}</code>, <code>{'{{data_execucao}}'}</code>, <code>{'{{link_relatorio}}'}</code>.
                  Campos do resultado podem ser usados pelo nome exato, inclusive aninhados como <code>{'{{cliente.nome}}'}</code>.
                </div>
              </aside>
            </div>

            <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-slate-100 bg-white px-5 py-4 sm:flex-row sm:justify-end">
              <button
                onClick={() => setTemplateEditorOpen(false)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                onClick={saveTemplate}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark"
              >
                <Save className="h-4 w-4" />
                {templateForm.id ? 'Salvar alterações' : 'Criar template'}
              </button>
            </div>
          </div>
        </div>
      )}

      {ruleEditorOpen && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 sm:items-center sm:p-4">
          <div className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:max-w-4xl sm:rounded-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                  {ruleForm.id ? `Regra #${ruleForm.id}` : 'Nova regra'}
                </p>
                <h3 className="mt-1 text-xl font-black text-slate-900">
                  {ruleForm.id ? 'Editar regra' : 'Criar regra'}
                </h3>
              </div>
              <button
                onClick={() => setRuleEditorOpen(false)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
                aria-label="Fechar regra"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Rotina
                  <select
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    value={ruleForm.automation_id}
                    onChange={(event) => {
                      setRuleForm({ ...ruleForm, automation_id: event.target.value });
                      setVariableAutomationId(event.target.value);
                    }}
                  >
                    <option value="">Selecione uma rotina</option>
                    {automations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Template
                  <select
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    value={ruleForm.template_id}
                    onChange={(event) => setRuleForm({ ...ruleForm, template_id: event.target.value })}
                  >
                    <option value="">Template padrão</option>
                    {templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Destinatário
                  <select
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    value={ruleForm.recipient_type}
                    onChange={(event) => setRuleForm({ ...ruleForm, recipient_type: event.target.value })}
                  >
                    <option value="responsavel">Responsável do resultado</option>
                    <option value="gestor">Gestor do responsável</option>
                    <option value="funcionario_fixo">Funcionário fixo</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Condição
                  <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    placeholder="sempre, deve_notificar, status_atrasado"
                    value={ruleForm.send_condition}
                    onChange={(event) => setRuleForm({ ...ruleForm, send_condition: event.target.value })}
                  />
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Canal preferencial
                  <select
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    value={ruleForm.preferred_channel}
                    onChange={(event) => setRuleForm({ ...ruleForm, preferred_channel: event.target.value })}
                  >
                    <option value="email">Email</option>
                    <option value="teams">Teams</option>
                    <option value="internal">Interna</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Canal fallback
                  <select
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal"
                    value={ruleForm.fallback_channel}
                    onChange={(event) => setRuleForm({ ...ruleForm, fallback_channel: event.target.value })}
                  >
                    <option value="">Sem fallback</option>
                    <option value="email">Email</option>
                    <option value="teams">Teams</option>
                    <option value="internal">Interna</option>
                  </select>
                </label>
              </div>
              <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
                <label className="rounded-xl border border-slate-200 p-3 text-sm font-semibold text-slate-700">
                  <input type="checkbox" checked={ruleForm.is_active} onChange={(event) => setRuleForm({ ...ruleForm, is_active: event.target.checked })} />
                  <span className="ml-2">Regra ativa</span>
                </label>
                <label className="rounded-xl border border-slate-200 p-3 text-sm font-semibold text-slate-700">
                  <input type="checkbox" checked={ruleForm.requires_approval} onChange={(event) => setRuleForm({ ...ruleForm, requires_approval: event.target.checked })} />
                  <span className="ml-2">Exige aprovação</span>
                </label>
                <label className="rounded-xl border border-slate-200 p-3 text-sm font-semibold text-slate-700">
                  <input type="checkbox" checked={ruleForm.notify_manager} onChange={(event) => setRuleForm({ ...ruleForm, notify_manager: event.target.checked })} />
                  <span className="ml-2">Avisar gestor também</span>
                </label>
              </div>
            </div>

            <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-slate-100 bg-white px-5 py-4 sm:flex-row sm:justify-end">
              <button
                onClick={() => setRuleEditorOpen(false)}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </button>
              <button
                onClick={saveRule}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark"
              >
                <Save className="h-4 w-4" />
                {ruleForm.id ? 'Salvar alterações' : 'Criar regra'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedNotification && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 sm:items-center sm:p-4">
          <div className="max-h-[92vh] w-full overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:max-w-3xl sm:rounded-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                  Notificacao #{selectedNotification.id}
                </p>
                <h3 className="mt-1 text-xl font-black text-slate-900">Detalhes do envio</h3>
              </div>
              <button
                onClick={() => setSelectedNotification(null)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50"
                aria-label="Fechar detalhes"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="max-h-[calc(92vh-76px)] overflow-y-auto px-5 py-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Rotina</p>
                  <p className="mt-1 break-words text-sm font-semibold text-slate-800">{selectedNotification.automation_name || '-'}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Funcionario</p>
                  <p className="mt-1 break-words text-sm font-semibold text-slate-800">{selectedNotification.employee_name || '-'}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Destinatario</p>
                  <p className="mt-1 break-words text-sm font-semibold text-slate-800">{selectedNotification.recipient || '-'}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Canal</p>
                  <p className="mt-1 text-sm font-semibold text-slate-800">{channelLabel[selectedNotification.channel] || selectedNotification.channel}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Status</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-1 text-xs font-bold ${statusStyles[selectedNotification.status] || 'bg-slate-100 text-slate-700'}`}>
                      {selectedNotification.status}
                    </span>
                    {selectedNotification.simulation && <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-700">simulacao</span>}
                  </div>
                </div>
                <div className="rounded-xl bg-slate-50 p-3">
                  <p className="text-xs font-bold uppercase text-slate-400">Envio</p>
                  <p className="mt-1 text-sm font-semibold text-slate-800">{formatDateTime(selectedNotification.sent_at || selectedNotification.data_envio)}</p>
                  <p className="mt-1 text-xs text-slate-500">Tentativas: {selectedNotification.attempts || 0}</p>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-bold uppercase text-slate-400">Assunto</p>
                <p className="mt-2 break-words text-sm font-bold text-slate-900">{selectedNotification.subject || '-'}</p>
              </div>

              <div className="mt-4 rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-bold uppercase text-slate-400">Texto enviado</p>
                <pre className="mt-3 max-h-80 whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-sm leading-6 text-slate-50">
                  {selectedNotification.message || '-'}
                </pre>
              </div>

              {selectedNotification.error && (
                <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
                  <p className="text-xs font-bold uppercase text-red-500">Erro</p>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm font-semibold text-red-700">{selectedNotification.error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default NotificationsPage;
