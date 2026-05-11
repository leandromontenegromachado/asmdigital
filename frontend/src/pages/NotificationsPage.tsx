import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Copy, Plus, RefreshCw, Save, Send, Trash2, XCircle } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { Automation, listAutomations } from '../api/automations';
import {
  NotificationHistory,
  NotificationRule,
  NotificationTemplate,
  approveNotification,
  cancelNotification,
  createNotificationRule,
  createNotificationTemplate,
  deleteNotificationRule,
  deleteNotificationTemplate,
  listNotificationRules,
  listNotificationTemplates,
  listNotifications,
  retryNotification,
  updateNotificationRule,
  updateNotificationTemplate,
} from '../api/notifications';

const defaultTemplate = {
  id: null as number | null,
  name: 'Pendencia por responsavel',
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

const NotificationsPage: React.FC = () => {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [history, setHistory] = useState<NotificationHistory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [templateForm, setTemplateForm] = useState({ ...defaultTemplate });
  const [ruleForm, setRuleForm] = useState({ ...defaultRule });

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.id === templateForm.id) || null,
    [templates, templateForm.id],
  );

  const selectedRule = useMemo(
    () => rules.find((item) => item.id === ruleForm.id) || null,
    [rules, ruleForm.id],
  );

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [automationData, templateData, ruleData, historyData] = await Promise.all([
        listAutomations(),
        listNotificationTemplates(),
        listNotificationRules(),
        listNotifications(),
      ]);
      setAutomations(automationData);
      setTemplates(templateData);
      setRules(ruleData);
      setHistory(historyData);
    } catch {
      setError('Nao foi possivel carregar notificacoes.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const clearTemplate = () => {
    setTemplateForm({ ...defaultTemplate, id: null });
  };

  const editTemplate = (template: NotificationTemplate) => {
    setTemplateForm({
      id: template.id,
      name: template.name,
      channel: template.channel,
      subject: template.subject || '',
      body: template.body,
      is_active: template.is_active,
    });
  };

  const duplicateTemplate = (template: NotificationTemplate) => {
    setTemplateForm({
      id: null,
      name: `${template.name} - copia`,
      channel: template.channel,
      subject: template.subject || '',
      body: template.body,
      is_active: template.is_active,
    });
  };

  const saveTemplate = async () => {
    setError(null);
    try {
      const payload = {
        name: templateForm.name.trim(),
        channel: templateForm.channel,
        subject: templateForm.subject || null,
        body: templateForm.body,
        is_active: templateForm.is_active,
      };
      if (!payload.name || !payload.body.trim()) {
        setError('Informe nome e corpo do template.');
        return;
      }
      if (templateForm.id) {
        await updateNotificationTemplate(templateForm.id, payload);
      } else {
        await createNotificationTemplate(payload);
      }
      clearTemplate();
      await load();
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
    try {
      await retryNotification(id);
      await load();
    } catch {
      setError('Falha ao reenviar notificacao.');
    }
  };

  const approve = async (id: number) => {
    setError(null);
    try {
      await approveNotification(id);
      await load();
    } catch {
      setError('Falha ao aprovar envio.');
    }
  };

  const cancel = async (id: number) => {
    setError(null);
    try {
      await cancelNotification(id);
      await load();
    } catch {
      setError('Falha ao cancelar envio.');
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

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-bold uppercase text-slate-400">Templates</p>
            <p className="text-2xl font-black text-slate-900">{templates.length}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-bold uppercase text-slate-400">Regras</p>
            <p className="text-2xl font-black text-slate-900">{rules.length}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <p className="text-xs font-bold uppercase text-slate-400">Historico</p>
            <p className="text-2xl font-black text-slate-900">{history.length}</p>
          </div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 shadow-sm">
            <p className="text-xs font-bold uppercase text-blue-500">Aguardando aprovacao</p>
            <p className="text-2xl font-black text-blue-900">{history.filter((item) => item.status === 'aguardando_aprovacao').length}</p>
          </div>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Atualizar
        </button>
      </div>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
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
              <article key={template.id} className={`p-4 ${selectedTemplate?.id === template.id ? 'bg-blue-50' : ''}`}>
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

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {templateForm.id ? `Editar template #${templateForm.id}` : 'Novo template'}
              </h2>
              <p className="text-sm text-slate-500">Depois de salvar, use este template em uma regra por rotina.</p>
            </div>
            <button onClick={saveTemplate} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark">
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
              className="h-72 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm"
              value={templateForm.body}
              onChange={(event) => setTemplateForm({ ...templateForm, body: event.target.value })}
            />
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
              <input
                type="checkbox"
                checked={templateForm.is_active}
                onChange={(event) => setTemplateForm({ ...templateForm, is_active: event.target.checked })}
              />
              Template ativo
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              Variaveis comuns: <code>{'{{nome_responsavel}}'}</code>, <code>{'{{nome_rotina}}'}</code>, <code>{'{{nome_projeto}}'}</code>, <code>{'{{status}}'}</code>, <code>{'{{dias_atraso}}'}</code>, <code>{'{{link_relatorio}}'}</code>.
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
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
              <article key={rule.id} className={`p-4 ${selectedRule?.id === rule.id ? 'bg-blue-50' : ''}`}>
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

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                {ruleForm.id ? `Editar regra #${ruleForm.id}` : 'Nova regra'}
              </h2>
              <p className="text-sm text-slate-500">Vincule uma rotina a um template e defina os canais.</p>
            </div>
            <button onClick={saveRule} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white hover:bg-primary-dark">
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
              Notificar gestor tambem
            </label>
          </div>
        </div>
      </section>

      <section className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="text-lg font-bold text-slate-900">3. Historico de notificacoes</h2>
          <p className="text-sm text-slate-500">Ultimos registros de envio, simulacao e erro.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 text-left">Rotina</th>
                <th className="px-4 py-3 text-left">Funcionario</th>
                <th className="px-4 py-3 text-left">Canal</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Enviado em</th>
                <th className="px-4 py-3 text-left">Assunto / mensagem</th>
                <th className="px-4 py-3 text-left">Acao</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id} className="border-t border-slate-100">
                  <td className="px-4 py-3">{item.automation_name || '-'}</td>
                  <td className="px-4 py-3">
                    <div>{item.employee_name || '-'}</div>
                    <div className="text-xs text-slate-500">{item.recipient || '-'}</div>
                  </td>
                  <td className="px-4 py-3">{channelLabel[item.channel] || item.channel}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs font-bold ${statusStyles[item.status] || 'bg-slate-100 text-slate-700'}`}>
                      {item.status}
                    </span>
                    {item.simulation && <div className="mt-1 text-xs text-amber-700">simulacao</div>}
                  </td>
                  <td className="px-4 py-3">{formatDateTime(item.sent_at || item.data_envio)}</td>
                  <td className="max-w-xl px-4 py-3">
                    <div className="font-semibold text-slate-800">{item.subject || '-'}</div>
                    <div className={`mt-1 line-clamp-2 text-xs ${item.status === 'erro' || item.status === 'simulado' ? 'text-red-600' : 'text-slate-500'}`}>
                      {item.error || item.message || '-'}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {item.status === 'aguardando_aprovacao' && (
                      <div className="flex flex-wrap gap-2">
                        <button onClick={() => approve(item.id)} className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                          <CheckCircle2 className="h-4 w-4" />
                          Aprovar envio
                        </button>
                        <button onClick={() => cancel(item.id)} className="inline-flex items-center gap-1 font-semibold text-red-700">
                          <XCircle className="h-4 w-4" />
                          Cancelar
                        </button>
                      </div>
                    )}
                    {item.status === 'erro' && (
                      <button onClick={() => retry(item.id)} className="inline-flex items-center gap-1 font-semibold text-cyan-700">
                        <Send className="h-4 w-4" />
                        Reenviar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {history.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">Nenhuma notificacao registrada.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
};

export default NotificationsPage;
