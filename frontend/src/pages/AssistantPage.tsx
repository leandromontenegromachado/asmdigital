import React, { useEffect, useMemo, useState } from 'react';
import { Bot, CheckCircle2, History, Loader2, RefreshCw, Send, XCircle } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import {
  AssistantHistoryItem,
  AssistantResponse,
  confirmAssistantConfirmation,
  listAssistantCapabilities,
  listAssistantHistory,
  sendAssistantCommand,
} from '../api/assistant';

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  response?: AssistantResponse;
};

const examplePrompts = [
  'Quais rotinas estao ativas?',
  'Crie uma rotina toda sexta as 9h para listar demandas atrasadas.',
  'Cadastre Joao Silva como funcionario do setor ASM com e-mail joao@empresa.com.',
  'Resolva a pendencia 123 com comentario: tratado com a equipe.',
  'O que voce consegue fazer?',
];

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR');
};

const JsonGrid: React.FC<{ value: Record<string, any> }> = ({ value }) => {
  const entries = Object.entries(value || {}).filter(([, item]) => item !== null && item !== undefined && item !== '');
  if (!entries.length) return <p className="text-sm text-slate-500">Nenhum parametro identificado.</p>;
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {entries.map(([key, item]) => (
        <div key={key} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <dt className="text-[11px] font-black uppercase text-slate-400">{key}</dt>
          <dd className="mt-1 break-words text-sm font-semibold text-slate-800">
            {typeof item === 'object' ? JSON.stringify(item) : String(item)}
          </dd>
        </div>
      ))}
    </dl>
  );
};

const ConfirmationCard: React.FC<{
  response: AssistantResponse;
  busy: boolean;
  onConfirm: (confirmationId: string, confirmed: boolean) => void;
}> = ({ response, busy, onConfirm }) => {
  if (!response.requires_confirmation || !response.confirmation_id) return null;
  const preview = response.preview || {};
  const params = preview.params || response.data || {};
  return (
    <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-black text-blue-950">Confirmacao necessaria</p>
          <p className="mt-1 text-sm leading-6 text-blue-900">
            {preview.impact || preview.summary || 'Revise os dados antes de executar.'}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => onConfirm(response.confirmation_id as string, true)}
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-black text-white hover:bg-blue-600 disabled:opacity-60"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            Confirmar
          </button>
          <button
            onClick={() => onConfirm(response.confirmation_id as string, false)}
            disabled={busy}
            className="inline-flex items-center justify-center rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm font-black text-blue-900 hover:bg-blue-100 disabled:opacity-60"
            title="Cancelar"
          >
            <XCircle size={16} />
          </button>
        </div>
      </div>
      <div className="mt-4">
        <JsonGrid value={params} />
      </div>
      {response.missing_params?.length > 0 && (
        <p className="mt-3 text-sm font-bold text-amber-700">Faltam: {response.missing_params.join(', ')}</p>
      )}
    </div>
  );
};

const AssistantBubble: React.FC<{
  message: ChatMessage;
  busyConfirmation: string | null;
  onConfirm: (confirmationId: string, confirmed: boolean) => void;
}> = ({ message, busyConfirmation, onConfirm }) => {
  const isUser = message.role === 'user';
  const response = message.response;
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[92%] rounded-2xl px-4 py-3 shadow-sm ${isUser ? 'bg-primary text-white' : 'border border-slate-200 bg-white text-slate-800'}`}>
        {!isUser && response && (
          <div className="mb-2 flex flex-wrap gap-2">
            {response.domain && <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-500">{response.domain}</span>}
            {response.action && <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-500">{response.action}</span>}
            <span className={`rounded-full px-2 py-1 text-[11px] font-black ${response.success ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
              {response.success ? 'ok' : 'erro'}
            </span>
          </div>
        )}
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">{message.text}</pre>
        {response && !response.requires_confirmation && Object.keys(response.data || {}).length > 0 && (
          <div className="mt-3 rounded-xl bg-slate-50 p-3">
            <JsonGrid value={response.data} />
          </div>
        )}
        {response && (
          <ConfirmationCard
            response={response}
            busy={busyConfirmation === response.confirmation_id}
            onConfirm={onConfirm}
          />
        )}
      </div>
    </div>
  );
};

const AssistantPage: React.FC = () => {
  const [message, setMessage] = useState(examplePrompts[0]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<AssistantHistoryItem[]>([]);
  const [capabilities, setCapabilities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [busyConfirmation, setBusyConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recentActions = useMemo(() => history.slice(0, 8), [history]);

  const loadPage = async () => {
    setLoading(true);
    setError(null);
    try {
      const [historyData, capabilityData] = await Promise.all([listAssistantHistory(), listAssistantCapabilities()]);
      setHistory(historyData);
      setCapabilities(capabilityData.capabilities || []);
    } catch (err) {
      setError('Nao foi possivel carregar o assistente.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPage();
  }, []);

  const appendAssistantResponse = (response: AssistantResponse) => {
    setMessages((current) => [
      ...current,
      {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        text: response.message,
        response,
      },
    ]);
  };

  const handleSend = async () => {
    const text = message.trim();
    if (!text) return;
    setSending(true);
    setError(null);
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', text }]);
    setMessage('');
    try {
      const response = await sendAssistantCommand(text);
      appendAssistantResponse(response);
      const historyData = await listAssistantHistory();
      setHistory(historyData);
    } catch (err) {
      setError('Falha ao conversar com o assistente.');
    } finally {
      setSending(false);
    }
  };

  const handleConfirm = async (confirmationId: string, confirmed: boolean) => {
    setBusyConfirmation(confirmationId);
    setError(null);
    try {
      const response = await confirmAssistantConfirmation(confirmationId, confirmed);
      appendAssistantResponse(response);
      const historyData = await listAssistantHistory();
      setHistory(historyData);
    } catch (err) {
      setError('Falha ao confirmar ou cancelar a acao.');
    } finally {
      setBusyConfirmation(null);
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Assistente"
        subtitle="Operacoes por linguagem natural com validacao, permissao e confirmacao antes de alterar dados."
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

      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {loading && <StateBlock tone="loading" title="Carregando assistente" description="Aguarde alguns segundos." />}

      {!loading && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section className="flex min-h-[680px] min-w-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
              <div className="rounded-xl bg-blue-50 p-2 text-primary">
                <Bot size={22} />
              </div>
              <div>
                <h3 className="text-lg font-black text-slate-900">Chat operacional</h3>
                <p className="text-sm text-slate-500">Consultas respondem direto; alteracoes viram cards de confirmacao.</p>
              </div>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto bg-slate-50 px-5 py-5">
              {messages.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-300 bg-white p-5">
                  <p className="text-sm font-bold text-slate-700">Experimente um comando</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {examplePrompts.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => setMessage(prompt)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs font-bold text-slate-600 hover:bg-slate-50"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((item) => (
                  <AssistantBubble
                    key={item.id}
                    message={item}
                    busyConfirmation={busyConfirmation}
                    onConfirm={handleConfirm}
                  />
                ))
              )}
            </div>

            <div className="border-t border-slate-100 p-4">
              <div className="flex flex-col gap-3 sm:flex-row">
                <textarea
                  className="min-h-20 flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none focus:border-primary focus:bg-white"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="Digite um pedido. Ex.: envie notificacao para todos os responsaveis do ultimo relatorio."
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !message.trim()}
                  className="inline-flex min-w-36 items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-black text-white hover:bg-blue-600 disabled:opacity-60"
                >
                  {sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                  Enviar
                </button>
              </div>
            </div>
          </section>

          <aside className="flex min-w-0 flex-col gap-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <History size={18} className="text-primary" />
                <h3 className="text-lg font-black text-slate-900">Ultimas acoes</h3>
              </div>
              <div className="mt-4 grid gap-3">
                {recentActions.length === 0 ? (
                  <p className="text-sm text-slate-500">Nenhum comando registrado.</p>
                ) : (
                  recentActions.map((item) => (
                    <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="line-clamp-2 text-sm font-bold text-slate-800">{item.text}</p>
                        <span className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-black ${item.success ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                          {item.success ? 'ok' : 'erro'}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">{item.domain || item.intent || '-'} · {formatDate(item.created_at)}</p>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-lg font-black text-slate-900">Capacidades</h3>
              <div className="mt-4 grid gap-2">
                {capabilities.slice(0, 12).map((item) => (
                  <div key={item.domain} className="rounded-xl bg-slate-50 px-3 py-2">
                    <p className="text-sm font-black text-slate-800">{item.label}</p>
                    <p className="mt-1 text-xs text-slate-500">{(item.actions || []).join(', ')}</p>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
};

export default AssistantPage;
