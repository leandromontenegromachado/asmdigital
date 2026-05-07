import React, { useEffect, useState } from 'react';
import { Save, Send } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { Automation, listAutomations } from '../api/automations';
import {
  NotificationHistory,
  NotificationRule,
  NotificationTemplate,
  createNotificationRule,
  createNotificationTemplate,
  listNotificationRules,
  listNotificationTemplates,
  listNotifications,
  retryNotification,
} from '../api/notifications';

const defaultTemplate = {
  name: 'Pendência por responsável',
  channel: 'email',
  subject: 'ASMDIGITAL - Pendência da rotina {{nome_rotina}}',
  body: 'Olá, {{nome_responsavel}}.\n\nA rotina "{{nome_rotina}}" identificou uma pendência relacionada ao projeto "{{nome_projeto}}".\n\nStatus: {{status}}\nDias em atraso: {{dias_atraso}}\nData da execução: {{data_execucao}}\n\nAção sugerida:\n{{acao_sugerida}}\n\nAcesse o relatório completo em:\n{{link_relatorio}}',
  is_active: true,
};

const NotificationsPage: React.FC = () => {
  const [automations, setAutomations] = useState<Automation[]>([]);
  const [templates, setTemplates] = useState<NotificationTemplate[]>([]);
  const [rules, setRules] = useState<NotificationRule[]>([]);
  const [history, setHistory] = useState<NotificationHistory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [templateForm, setTemplateForm] = useState({ ...defaultTemplate });
  const [ruleForm, setRuleForm] = useState({
    automation_id: '',
    template_id: '',
    recipient_type: 'responsavel',
    preferred_channel: 'email',
    fallback_channel: 'internal',
    send_condition: '',
    requires_approval: false,
    notify_manager: false,
  });

  const load = async () => {
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
      setError('Não foi possível carregar notificações.');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveTemplate = async () => {
    try {
      await createNotificationTemplate(templateForm);
      setTemplateForm({ ...defaultTemplate });
      await load();
    } catch {
      setError('Falha ao salvar template.');
    }
  };

  const saveRule = async () => {
    try {
      await createNotificationRule({
        automation_id: Number(ruleForm.automation_id),
        template_id: ruleForm.template_id ? Number(ruleForm.template_id) : null,
        is_active: true,
        send_condition: ruleForm.send_condition || null,
        recipient_type: ruleForm.recipient_type,
        preferred_channel: ruleForm.preferred_channel,
        fallback_channel: ruleForm.fallback_channel || null,
        requires_approval: ruleForm.requires_approval,
        notify_manager: ruleForm.notify_manager,
        manager_condition: null,
        params_json: {},
      });
      await load();
    } catch {
      setError('Falha ao salvar regra.');
    }
  };

  const retry = async (id: number) => {
    await retryNotification(id);
    await load();
  };

  return (
    <AppShell>
      <Topbar title="Notificações inteligentes" subtitle="Configure regras, templates e consulte o histórico das rotinas acionáveis." />
      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-lg font-bold text-slate-900">Template de mensagem</h2>
          <div className="space-y-3">
            <input className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Nome" value={templateForm.name} onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })} />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={templateForm.channel} onChange={(e) => setTemplateForm({ ...templateForm, channel: e.target.value })}>
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Assunto" value={templateForm.subject} onChange={(e) => setTemplateForm({ ...templateForm, subject: e.target.value })} />
            </div>
            <textarea className="h-48 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm" value={templateForm.body} onChange={(e) => setTemplateForm({ ...templateForm, body: e.target.value })} />
            <button onClick={saveTemplate} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-bold text-white"><Save className="h-4 w-4" />Salvar template</button>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 text-lg font-bold text-slate-900">Regra por rotina</h2>
          <div className="space-y-3">
            <select className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={ruleForm.automation_id} onChange={(e) => setRuleForm({ ...ruleForm, automation_id: e.target.value })}>
              <option value="">Selecione a rotina</option>
              {automations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <select className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={ruleForm.template_id} onChange={(e) => setRuleForm({ ...ruleForm, template_id: e.target.value })}>
              <option value="">Template padrão</option>
              {templates.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={ruleForm.recipient_type} onChange={(e) => setRuleForm({ ...ruleForm, recipient_type: e.target.value })}>
                <option value="responsavel">Responsável do resultado</option>
                <option value="gestor">Gestor do responsável</option>
                <option value="funcionario_fixo">Funcionário fixo</option>
              </select>
              <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Condição: sempre, deve_notificar, status_atrasado" value={ruleForm.send_condition} onChange={(e) => setRuleForm({ ...ruleForm, send_condition: e.target.value })} />
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={ruleForm.preferred_channel} onChange={(e) => setRuleForm({ ...ruleForm, preferred_channel: e.target.value })}>
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
              <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={ruleForm.fallback_channel} onChange={(e) => setRuleForm({ ...ruleForm, fallback_channel: e.target.value })}>
                <option value="">Sem fallback</option>
                <option value="email">Email</option>
                <option value="teams">Teams</option>
                <option value="internal">Interna</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ruleForm.requires_approval} onChange={(e) => setRuleForm({ ...ruleForm, requires_approval: e.target.checked })} />Exige aprovação</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ruleForm.notify_manager} onChange={(e) => setRuleForm({ ...ruleForm, notify_manager: e.target.checked })} />Notificar gestor também</label>
            <button onClick={saveRule} disabled={!ruleForm.automation_id} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50"><Save className="h-4 w-4" />Salvar regra</button>
          </div>
        </section>
      </div>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-lg font-bold text-slate-900">Regras ativas</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {rules.map((rule) => (
            <div key={rule.id} className="rounded-lg border border-slate-200 p-3 text-sm">
              <div className="font-bold">{rule.automation_name}</div>
              <div className="text-slate-500">Destinatário: {rule.recipient_type} · Canal: {rule.preferred_channel} · Fallback: {rule.fallback_channel || '-'}</div>
              <div className="text-slate-500">Template: {rule.template_name || 'Padrão'} · Condição: {rule.send_condition || 'sempre'}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="text-lg font-bold text-slate-900">Histórico de notificações</h2>
        </div>
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-600"><tr><th className="px-4 py-3 text-left">Rotina</th><th className="px-4 py-3 text-left">Funcionário</th><th className="px-4 py-3 text-left">Canal</th><th className="px-4 py-3 text-left">Status</th><th className="px-4 py-3 text-left">Erro</th><th className="px-4 py-3 text-left">Ações</th></tr></thead>
          <tbody>
            {history.map((item) => (
              <tr key={item.id} className="border-t border-slate-100">
                <td className="px-4 py-3">{item.automation_name || '-'}</td>
                <td className="px-4 py-3"><div>{item.employee_name || '-'}</div><div className="text-xs text-slate-500">{item.recipient || '-'}</div></td>
                <td className="px-4 py-3">{item.channel}</td>
                <td className="px-4 py-3">{item.status}</td>
                <td className="px-4 py-3 text-red-600">{item.error || '-'}</td>
                <td className="px-4 py-3">{item.status === 'erro' && <button onClick={() => retry(item.id)} className="inline-flex items-center gap-1 font-semibold text-cyan-700"><Send className="h-4 w-4" />Reenviar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
};

export default NotificationsPage;
