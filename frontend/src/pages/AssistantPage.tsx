import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock,
  Link as LinkIcon,
  MessageSquareText,
  RefreshCw,
  Send,
  Smartphone,
  XCircle,
} from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import {
  AssistantAction,
  bindCurrentTelegramChat,
  cancelAssistantAction,
  confirmAssistantAction,
  listAssistantActions,
  sendAssistantMessage,
} from '../api/assistant';
import { me } from '../api/auth';

const statusStyles: Record<string, string> = {
  needs_confirmation: 'bg-blue-100 text-blue-700',
  needs_input: 'bg-amber-100 text-amber-700',
  completed: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-slate-100 text-slate-600',
  error: 'bg-red-100 text-red-700',
};

const statusLabel: Record<string, string> = {
  needs_confirmation: 'aguardando confirmacao',
  needs_input: 'faltam dados',
  completed: 'concluida',
  cancelled: 'cancelada',
  error: 'erro',
};

const examplePrompts = [
  'Agende uma reuniao na proxima quarta de manha com Leandro Machado sobre demandas atrasadas.',
  'Marque uma conversa amanha a tarde com Alessandra Nunes sobre a avaliacao do setor.',
  'Agenda uma reuniao de 1 hora sexta com Anderson Machado para revisar pendencias.',
];

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR');
};

const getActionTitle = (action: AssistantAction) => {
  const payload = action.payload_json || {};
  return payload.title || (action.action_type === 'schedule_meeting' ? 'Agendamento de reuniao' : action.action_type);
};

const getParticipantsSummary = (action: AssistantAction) => {
  const participants = action.payload_json?.participants || [];
  if (!participants.length) return '-';
  return participants
    .slice(0, 2)
    .map((participant: any) => participant.name || participant.email || 'Participante')
    .join(', ') + (participants.length > 2 ? ` +${participants.length - 2}` : '');
};

const ActionCard: React.FC<{
  action: AssistantAction;
  compact?: boolean;
  busyActionId: number | null;
  onConfirm: (action: AssistantAction) => void;
  onCancel: (action: AssistantAction) => void;
}> = ({ action, compact = false, busyActionId, onConfirm, onCancel }) => {
  const payload = action.payload_json || {};
  const result = action.result_json || {};
  const participants = payload.participants || [];
  const slots = payload.suggested_slots || [];
  const canAct = ['needs_confirmation', 'needs_input'].includes(action.status);

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-black uppercase tracking-wide text-slate-500">
              {action.action_type}
            </span>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-black ${statusStyles[action.status] || 'bg-slate-100 text-slate-600'}`}>
              {statusLabel[action.status] || action.status}
            </span>
          </div>
          <h3 className="mt-3 break-words text-lg font-black text-slate-900">{getActionTitle(action)}</h3>
          <p className="mt-1 text-xs text-slate-500">Criada em {formatDate(action.created_at)}</p>
        </div>
        {canAct && (
          <div className="flex shrink-0 gap-2">
            <button
              onClick={() => onConfirm(action)}
              disabled={busyActionId === action.id || action.status === 'needs_input'}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-bold text-white hover:bg-blue-600 disabled:opacity-50"
            >
              <CheckCircle2 size={16} />
              Confirmar
            </button>
            <button
              onClick={() => onCancel(action)}
              disabled={busyActionId === action.id}
              className="inline-flex items-center justify-center rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              title="Cancelar"
            >
              <XCircle size={16} />
            </button>
          </div>
        )}
      </div>

      {!compact && (
        <div className="mt-4 grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-xl bg-slate-50 p-4">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
              <CalendarDays size={16} />
              Data
            </div>
            <p className="mt-2 text-sm text-slate-600">{payload.date || 'Data nao informada'}</p>
            <p className="mt-1 text-xs text-slate-500">{payload.duration_minutes || 30} minutos</p>
          </div>

          <div className="rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-bold text-slate-700">Participantes</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {participants.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhum participante identificado.</p>
              ) : (
                participants.map((participant: any, index: number) => (
                  <div key={`${participant.email || participant.name}-${index}`} className="rounded-lg bg-white px-3 py-2">
                    <p className="break-words text-sm font-bold text-slate-800">{participant.name || 'Participante'}</p>
                    <p className={`break-all text-xs ${participant.email ? 'text-slate-500' : 'text-red-600'}`}>
                      {participant.email || 'Email nao encontrado'}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {slots.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-3">
          {slots.slice(0, 3).map((slot: any, index: number) => (
            <div key={`${slot.start}-${index}`} className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-900">
              <div className="flex items-center gap-2 font-bold">
                <Clock size={15} />
                Opcao {index + 1}
              </div>
              <p className="mt-1 text-xs">{slot.start || '-'} ate {slot.end || '-'}</p>
            </div>
          ))}
        </div>
      )}

      {result.error && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {String(result.error)}
        </div>
      )}
      {result.meeting_url && (
        <a
          href={result.meeting_url}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-primary hover:bg-slate-50"
        >
          <LinkIcon size={16} />
          Abrir reuniao
        </a>
      )}
    </article>
  );
};

const ActionsTable: React.FC<{
  actions: AssistantAction[];
  busyActionId: number | null;
  onConfirm: (action: AssistantAction) => void;
  onCancel: (action: AssistantAction) => void;
}> = ({ actions, busyActionId, onConfirm, onCancel }) => {
  if (actions.length === 0) {
    return <StateBlock title="Nenhuma acao registrada" description="Envie um pedido no chat para comecar." />;
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <div className="hidden overflow-x-auto lg:block">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3 text-left font-black">Acao</th>
              <th className="px-4 py-3 text-left font-black">Status</th>
              <th className="px-4 py-3 text-left font-black">Data</th>
              <th className="px-4 py-3 text-left font-black">Participantes</th>
              <th className="px-4 py-3 text-right font-black">Comandos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {actions.map((action) => {
              const canAct = ['needs_confirmation', 'needs_input'].includes(action.status);
              return (
                <tr key={action.id} className="hover:bg-slate-50">
                  <td className="max-w-sm px-4 py-4">
                    <p className="truncate font-black text-slate-900">{getActionTitle(action)}</p>
                    <p className="mt-1 text-xs text-slate-500">{action.action_type}</p>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-black ${statusStyles[action.status] || 'bg-slate-100 text-slate-600'}`}>
                      {statusLabel[action.status] || action.status}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-slate-600">{formatDate(action.created_at)}</td>
                  <td className="max-w-xs px-4 py-4">
                    <p className="truncate text-slate-700">{getParticipantsSummary(action)}</p>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex justify-end gap-2">
                      {canAct ? (
                        <>
                          <button
                            onClick={() => onConfirm(action)}
                            disabled={busyActionId === action.id || action.status === 'needs_input'}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-black text-white hover:bg-blue-600 disabled:opacity-50"
                          >
                            <CheckCircle2 size={15} />
                            Confirmar
                          </button>
                          <button
                            onClick={() => onCancel(action)}
                            disabled={busyActionId === action.id}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-black text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                          >
                            <XCircle size={15} />
                            Cancelar
                          </button>
                        </>
                      ) : action.result_json?.meeting_url ? (
                        <a
                          href={action.result_json.meeting_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-black text-primary hover:bg-slate-50"
                        >
                          <LinkIcon size={15} />
                          Abrir
                        </a>
                      ) : (
                        <span className="text-xs font-semibold text-slate-400">-</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 bg-white p-3 lg:hidden">
        {actions.map((action) => {
          const canAct = ['needs_confirmation', 'needs_input'].includes(action.status);
          return (
            <article key={action.id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words font-black text-slate-900">{getActionTitle(action)}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatDate(action.created_at)}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-black ${statusStyles[action.status] || 'bg-slate-100 text-slate-600'}`}>
                  {statusLabel[action.status] || action.status}
                </span>
              </div>
              <p className="mt-3 text-sm text-slate-600">{getParticipantsSummary(action)}</p>
              {canAct && (
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <button
                    onClick={() => onConfirm(action)}
                    disabled={busyActionId === action.id || action.status === 'needs_input'}
                    className="rounded-lg bg-primary px-3 py-2 text-xs font-black text-white disabled:opacity-50"
                  >
                    Confirmar
                  </button>
                  <button
                    onClick={() => onCancel(action)}
                    disabled={busyActionId === action.id}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-black text-slate-700 disabled:opacity-50"
                  >
                    Cancelar
                  </button>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
};

const AssistantPage: React.FC = () => {
  const [message, setMessage] = useState(examplePrompts[0]);
  const [reply, setReply] = useState('');
  const [latestAction, setLatestAction] = useState<AssistantAction | null>(null);
  const [actions, setActions] = useState<AssistantAction[]>([]);
  const [chatId, setChatId] = useState('');
  const [telegramUsername, setTelegramUsername] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [busyActionId, setBusyActionId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pendingActions = useMemo(
    () => actions.filter((action) => ['needs_confirmation', 'needs_input'].includes(action.status)),
    [actions]
  );

  const completedCount = useMemo(
    () => actions.filter((action) => action.status === 'completed').length,
    [actions]
  );

  const loadActionsOnly = async () => {
    const data = await listAssistantActions();
    setActions(data);
  };

  const loadPage = async () => {
    setLoading(true);
    setError(null);
    try {
      const [currentUser, actionData] = await Promise.all([me(), listAssistantActions()]);
      setChatId(currentUser.telegram_chat_id || '');
      setTelegramUsername(currentUser.telegram_username || '');
      setActions(actionData);
    } catch (err) {
      setError('Nao foi possivel carregar o assistente.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPage();
  }, []);

  const handleSend = async () => {
    if (!message.trim()) return;
    setSending(true);
    setNotice(null);
    setError(null);
    try {
      const response = await sendAssistantMessage(message.trim());
      setReply(response.reply);
      setLatestAction(response.action || null);
      await loadActionsOnly();
    } catch (err) {
      setError('Falha ao conversar com o assistente.');
    } finally {
      setSending(false);
    }
  };

  const handleBindTelegram = async () => {
    if (!chatId.trim()) {
      setError('Informe o chat_id exibido pelo bot do Telegram.');
      return;
    }
    setNotice(null);
    setError(null);
    try {
      await bindCurrentTelegramChat(chatId.trim(), telegramUsername.trim() || undefined);
      setNotice('Telegram vinculado ao usuario atual.');
    } catch (err) {
      setError('Falha ao vincular o Telegram.');
    }
  };

  const handleConfirm = async (action: AssistantAction) => {
    setBusyActionId(action.id);
    setNotice(null);
    setError(null);
    try {
      const result = await confirmAssistantAction(action.id);
      setNotice(result.status === 'completed' ? 'Acao confirmada.' : `Acao atualizada: ${result.status}`);
      await loadActionsOnly();
    } catch (err) {
      setError('Falha ao confirmar a acao.');
    } finally {
      setBusyActionId(null);
    }
  };

  const handleCancel = async (action: AssistantAction) => {
    setBusyActionId(action.id);
    setNotice(null);
    setError(null);
    try {
      await cancelAssistantAction(action.id);
      setNotice('Acao cancelada.');
      await loadActionsOnly();
    } catch (err) {
      setError('Falha ao cancelar a acao.');
    } finally {
      setBusyActionId(null);
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Assistente de Gestao"
        subtitle="Agende reunioes por texto, confirme antes de enviar e conecte o mesmo fluxo ao Telegram."
        action={
          <button
            onClick={loadPage}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <RefreshCw size={18} />
            Atualizar
          </button>
        }
      />

      {notice && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-700">{notice}</div>}
      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {loading && <StateBlock tone="loading" title="Carregando assistente" description="Aguarde alguns segundos." />}

      {!loading && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.75fr)]">
          <section className="flex min-w-0 flex-col gap-6">
            <div className="rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 p-5">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="rounded-2xl bg-blue-50 p-3 text-primary">
                      <MessageSquareText size={24} />
                    </div>
                    <div>
                      <h3 className="text-2xl font-black text-slate-900">Pedido em linguagem natural</h3>
                      <p className="mt-1 text-sm text-slate-500">
                        O sistema interpreta o texto, localiza participantes no cadastro e pede confirmacao.
                      </p>
                    </div>
                  </div>
                  <span className="w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                    IA: Assistente de Gestao
                  </span>
                </div>
              </div>

              <div className="p-5">
                <textarea
                  className="min-h-36 w-full resize-y rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-base text-slate-900 outline-none transition focus:border-primary focus:bg-white"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="Ex.: agenda uma reuniao na proxima quarta de manha com Alessandra e Anderson sobre demandas atrasadas."
                />

                <div className="mt-4 flex flex-wrap gap-2">
                  {examplePrompts.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => setMessage(prompt)}
                      className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>

                <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-slate-500">
                    Nada e enviado sem confirmacao. No Telegram, o mesmo fluxo responde pedindo confirmacao.
                  </p>
                  <button
                    onClick={handleSend}
                    disabled={sending || !message.trim()}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-black text-white shadow-lg shadow-blue-100 hover:bg-blue-600 disabled:opacity-60"
                  >
                    <Send size={18} />
                    {sending ? 'Interpretando...' : 'Enviar pedido'}
                  </button>
                </div>

                {reply && (
                  <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-xs font-black uppercase tracking-wide text-slate-400">Resposta do assistente</p>
                    <pre className="mt-2 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-slate-700">{reply}</pre>
                  </div>
                )}
              </div>
            </div>

            {latestAction && (
              <div className="flex flex-col gap-3">
                <h3 className="text-xl font-black text-slate-900">Acao gerada agora</h3>
                <ActionCard action={latestAction} busyActionId={busyActionId} onConfirm={handleConfirm} onCancel={handleCancel} />
              </div>
            )}

            <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-col gap-2 border-b border-slate-100 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-xl font-black text-slate-900">Historico de acoes</h3>
                  <p className="text-sm text-slate-500">Pedidos criados pelo chat interno ou Telegram.</p>
                </div>
                <span className="w-fit rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-primary">
                  {pendingActions.length} pendentes
                </span>
              </div>
              <div className="p-5">
                <ActionsTable
                  actions={actions}
                  busyActionId={busyActionId}
                  onConfirm={handleConfirm}
                  onCancel={handleCancel}
                />
              </div>
            </section>
          </section>

          <aside className="flex min-w-0 flex-col gap-6">
            <section className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-bold text-slate-500">Acoes</p>
                <p className="mt-2 text-3xl font-black text-slate-900">{actions.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-bold text-slate-500">Pendentes</p>
                <p className="mt-2 text-3xl font-black text-blue-600">{pendingActions.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-bold text-slate-500">Concluidas</p>
                <p className="mt-2 text-3xl font-black text-emerald-600">{completedCount}</p>
              </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-600">
                  <Smartphone size={24} />
                </div>
                <div>
                  <h3 className="text-xl font-black text-slate-900">Telegram</h3>
                  <p className="mt-1 text-sm text-slate-500">Vincule seu chat ao usuario logado.</p>
                </div>
              </div>

              <div className="mt-5 flex flex-col gap-3">
                <label className="flex flex-col gap-2">
                  <span className="text-sm font-bold text-slate-700">Chat ID</span>
                  <input
                    className="rounded-xl border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={chatId}
                    onChange={(event) => setChatId(event.target.value)}
                    placeholder="Ex.: 123456789"
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <span className="text-sm font-bold text-slate-700">Username</span>
                  <input
                    className="rounded-xl border border-slate-200 px-4 py-3 text-slate-900 outline-none focus:border-primary"
                    value={telegramUsername}
                    onChange={(event) => setTelegramUsername(event.target.value)}
                    placeholder="Opcional"
                  />
                </label>
                <button
                  onClick={handleBindTelegram}
                  className="rounded-xl bg-slate-900 px-4 py-3 text-sm font-black text-white hover:bg-slate-800"
                >
                  Salvar vinculo
                </button>
                <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                  Envie <span className="font-bold">/start</span> para o bot. Ele retorna o chat_id que deve ser colado aqui.
                </div>
              </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="rounded-2xl bg-blue-50 p-3 text-primary">
                  <Bot size={24} />
                </div>
                <div>
                  <h3 className="text-xl font-black text-slate-900">Como a IA entra</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Primeiro o sistema tenta entender pedidos simples localmente. Se precisar interpretar melhor o texto,
                    usa o modelo configurado em Modelos IA para a funcionalidade Assistente de Gestao.
                  </p>
                </div>
              </div>
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
};

export default AssistantPage;
