import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  History,
  Loader2,
  Mic,
  MicOff,
  ExternalLink,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react';
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
  createdAt: string;
  response?: AssistantResponse;
};

type VoiceState = 'idle' | 'listening' | 'processing' | 'unsupported';

const examplePrompts = [
  'O que voce consegue fazer?',
  'Quais rotinas estao ativas?',
  'Rode o relatorio de demandas em aberto do Leandro.',
  'Envie notificacao para todos os responsaveis do ultimo relatorio.',
  'Resolva a pendencia 123 com comentario: tratado com a equipe.',
];

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR');
};

const humanizeKey = (value: string) =>
  value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());

const stringifyValue = (value: any) => {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Sim' : 'Nao';
  if (Array.isArray(value)) return value.map((item) => (typeof item === 'object' ? JSON.stringify(item) : String(item))).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const DataPanel: React.FC<{ value: Record<string, any>; compact?: boolean }> = ({ value, compact = false }) => {
  const data = value || {};
  const itemList = Array.isArray(data.items) ? data.items : null;
  const capabilities = Array.isArray(data.capabilities) ? data.capabilities : null;

  if (capabilities) {
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {capabilities.slice(0, 8).map((item: any) => (
          <div key={item.domain || item.label} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <p className="text-sm font-black text-slate-800">{item.label || item.domain}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{(item.actions || []).join(', ')}</p>
          </div>
        ))}
      </div>
    );
  }

  if (itemList) {
    return (
      <div className="space-y-2">
        {typeof data.total !== 'undefined' && (
          <p className="text-xs font-bold uppercase text-slate-500">Total: {data.total}</p>
        )}
        <div className="grid gap-2">
          {itemList.slice(0, compact ? 4 : 8).map((item: any, index: number) => (
            <div key={item.id || index} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(item).slice(0, 8).map(([key, rawValue]) => (
                  <div key={key} className="min-w-0">
                    <p className="text-[11px] font-black uppercase text-slate-400">{humanizeKey(key)}</p>
                    <p className="truncate text-sm font-semibold text-slate-800">{stringifyValue(rawValue)}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const entries = Object.entries(data).filter(([, item]) => item !== null && item !== undefined && item !== '');
  if (!entries.length) return <p className="text-sm text-slate-500">Nenhum dado estruturado retornado.</p>;

  return (
    <dl className="grid gap-2 md:grid-cols-2">
      {entries.slice(0, compact ? 6 : 12).map(([key, item]) => (
        <div key={key} className="min-w-0 rounded-lg border border-slate-200 bg-white px-3 py-2">
          <dt className="text-[11px] font-black uppercase text-slate-400">{humanizeKey(key)}</dt>
          <dd className="mt-1 break-words text-sm font-semibold text-slate-800">{stringifyValue(item)}</dd>
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
  const missing = response.missing_params || preview.missing_params || [];

  return (
    <div className="mt-4 w-full overflow-hidden rounded-xl border border-blue-200 bg-blue-50">
      <div className="grid gap-3 border-b border-blue-100 px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-blue-950">
            <ShieldCheck size={18} className="shrink-0" />
            <p className="text-sm font-black">Confirmacao necessaria</p>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-blue-900">
            {preview.impact || preview.summary || 'Revise os dados antes de executar esta acao.'}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
          <button
            onClick={() => onConfirm(response.confirmation_id as string, true)}
            disabled={busy || missing.length > 0}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-black text-white hover:bg-blue-600 disabled:opacity-60"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
            Confirmar
          </button>
          <button
            onClick={() => onConfirm(response.confirmation_id as string, false)}
            disabled={busy}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm font-black text-blue-900 hover:bg-blue-100 disabled:opacity-60"
          >
            <XCircle size={16} />
            Cancelar
          </button>
        </div>
      </div>
      <div className="p-4">
        <DataPanel value={params} compact />
        {missing.length > 0 && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>Faltam dados para confirmar: {missing.join(', ')}.</span>
          </div>
        )}
      </div>
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
      <div
        className={`${response?.requires_confirmation ? 'w-full max-w-4xl' : 'max-w-[94%] lg:max-w-[78%]'} rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? 'bg-primary text-white'
            : 'border border-slate-200 bg-white text-slate-800'
        }`}
      >
        {!isUser && response && (
          <div className="mb-2 flex flex-wrap gap-2">
            {response.domain && <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-500">{response.domain}</span>}
            {response.action && <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-500">{response.action}</span>}
            <span className={`rounded-full px-2 py-1 text-[11px] font-black ${response.success ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
              {response.success ? 'ok' : 'erro'}
            </span>
          </div>
        )}
        <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.text}</p>
        <p className={`mt-2 text-[11px] ${isUser ? 'text-blue-100' : 'text-slate-400'}`}>{formatDate(message.createdAt)}</p>

        {response && !response.requires_confirmation && Object.keys(response.data || {}).length > 0 && (
          <div className="mt-3 rounded-xl bg-slate-50 p-3">
            {response.data.report_url && (
              <a
                href={response.data.report_url}
                className="mb-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-black text-slate-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
              >
                <ExternalLink size={16} />
                Abrir relatorio
              </a>
            )}
            <DataPanel value={response.data} compact />
          </div>
        )}
        {response && response.errors?.length > 0 && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {response.errors.join(', ')}
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
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [history, setHistory] = useState<AssistantHistoryItem[]>([]);
  const [capabilities, setCapabilities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [busyConfirmation, setBusyConfirmation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const recognitionRef = useRef<any>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const recentActions = useMemo(() => history.slice(0, 8), [history]);
  const pendingCount = useMemo(
    () => messages.filter((item) => item.response?.requires_confirmation).length,
    [messages]
  );

  const loadPage = async () => {
    setLoading(true);
    setError(null);
    try {
      const [historyData, capabilityData] = await Promise.all([listAssistantHistory(), listAssistantCapabilities()]);
      setHistory(historyData);
      setCapabilities(capabilityData.capabilities || []);
      if (messages.length === 0 && historyData.length > 0) {
        setMessages(
          historyData
            .slice(0, 6)
            .reverse()
            .flatMap((item) => [
              {
                id: `history-user-${item.id}`,
                role: 'user' as const,
                text: item.text,
                createdAt: item.created_at,
              },
              {
                id: `history-assistant-${item.id}`,
                role: 'assistant' as const,
                text: item.response_message || 'Sem resposta registrada.',
                createdAt: item.created_at,
                response: {
                  success: item.success,
                  message: item.response_message || '',
                  intent: item.intent,
                  domain: item.domain,
                  action: item.action,
                  requires_confirmation: Boolean(item.raw_payload_json?.confirmation_id),
                  confirmation_id: item.raw_payload_json?.confirmation_id || null,
                  preview: item.raw_payload_json?.preview || {},
                  missing_params: item.raw_payload_json?.plan?.missing_params || [],
                  data: item.raw_payload_json?.result || {},
                  errors: item.raw_payload_json?.errors || [],
                },
              },
            ])
        );
      }
    } catch (err) {
      setError('Nao foi possivel carregar o assistente.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPage();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  const appendAssistantResponse = (response: AssistantResponse) => {
    setMessages((current) => [
      ...current,
      {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        text: response.message,
        createdAt: new Date().toISOString(),
        response,
      },
    ]);
  };

  const refreshHistory = async () => {
    try {
      setHistory(await listAssistantHistory());
    } catch {
      // History is secondary to the chat response.
    }
  };

  const handleClearScreen = () => {
    setMessages([]);
    setMessage('');
    setError(null);
    setBusyConfirmation(null);
  };

  const handleSendText = async (text: string) => {
    const cleanText = text.trim();
    if (!cleanText) return;
    setSending(true);
    setError(null);
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', text: cleanText, createdAt: new Date().toISOString() },
    ]);
    setMessage('');
    try {
      const response = await sendAssistantCommand(cleanText);
      appendAssistantResponse(response);
      await refreshHistory();
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
      await refreshHistory();
    } catch (err) {
      setError('Falha ao confirmar ou cancelar a acao.');
    } finally {
      setBusyConfirmation(null);
    }
  };

  const startVoiceInput = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceState('unsupported');
      setError('Reconhecimento de voz nao esta disponivel neste navegador.');
      return;
    }
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
      setVoiceState('idle');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => setVoiceState('listening');
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript || '';
      setMessage(transcript);
      setVoiceState('processing');
      setTimeout(() => setVoiceState('idle'), 350);
    };
    recognition.onerror = () => {
      setVoiceState('idle');
      setError('Nao consegui entender o audio. Tente novamente ou digite o comando.');
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setVoiceState((current) => (current === 'listening' ? 'idle' : current));
    };
    recognitionRef.current = recognition;
    recognition.start();
  };

  return (
    <AppShell>
      <Topbar
        title="Assistente"
        subtitle="Comandos operacionais com interpretacao, permissao e confirmacao antes de alterar dados."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleClearScreen}
              disabled={messages.length === 0}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Trash2 size={17} />
              Limpar tela
            </button>
            <button
              onClick={loadPage}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50"
            >
              <RefreshCw size={17} />
              Atualizar
            </button>
          </div>
        }
      />

      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {loading && <StateBlock tone="loading" title="Carregando assistente" description="Aguarde alguns segundos." />}

      {!loading && (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section className="flex h-[calc(100dvh-210px)] min-h-[420px] min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm sm:h-[calc(100dvh-190px)] lg:h-[calc(100dvh-170px)]">
            <div className="shrink-0 border-b border-slate-100 bg-white px-4 py-3 sm:px-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-primary">
                    <Sparkles size={24} />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-xl font-black text-slate-900">Central de comandos</h3>
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                      Consulte dados direto pelo chat. Acoes com impacto ficam pendentes ate voce confirmar.
                    </p>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <p className="text-base font-black text-slate-900">{messages.length}</p>
                    <p className="text-[11px] font-bold uppercase text-slate-500">mensagens</p>
                  </div>
                  <div className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2">
                    <p className="text-base font-black text-blue-700">{pendingCount}</p>
                    <p className="text-[11px] font-bold uppercase text-blue-600">confirmar</p>
                  </div>
                  <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2">
                    <p className="text-base font-black text-emerald-700">{capabilities.length}</p>
                    <p className="text-[11px] font-bold uppercase text-emerald-600">areas</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-slate-50/80 px-3 py-5 sm:px-5">
              {messages.length === 0 ? (
                <div className="mx-auto max-w-3xl rounded-2xl border border-dashed border-slate-300 bg-white p-5 text-center shadow-sm">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-blue-100 bg-blue-50 text-primary">
                    <Bot size={28} />
                  </div>
                  <h3 className="mt-4 text-lg font-black text-slate-900">Comece com um comando</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Use voz ou texto para pedir consultas, criar rotinas, resolver pendencias ou enviar notificacoes com confirmacao.
                  </p>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {examplePrompts.map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => setMessage(prompt)}
                        className="rounded-xl border border-slate-200 px-3 py-2 text-left text-sm font-bold text-slate-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
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
              {sending && (
                <div className="flex justify-start">
                  <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-600 shadow-sm">
                    <Loader2 size={16} className="animate-spin" />
                    Interpretando comando...
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="sticky bottom-0 z-10 shrink-0 border-t border-slate-100 bg-white/95 p-3 shadow-[0_-12px_28px_rgba(15,23,42,0.06)] backdrop-blur sm:p-4">
              <div className="flex flex-col gap-2.5">
                <div className="min-w-0 flex-1">
                  <textarea
                    className="max-h-36 min-h-16 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-primary focus:bg-white"
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                        handleSendText(message);
                      }
                    }}
                    placeholder="Digite ou fale um comando. Ex.: envie notificacao para todos os responsaveis do ultimo relatorio."
                  />
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                    <span>Ctrl+Enter envia. Acoes de escrita exigem confirmacao.</span>
                    {voiceState === 'unsupported' && <span className="font-bold text-amber-700">Voz indisponivel neste navegador.</span>}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2.5 sm:flex sm:items-center sm:justify-between">
                  <button
                    type="button"
                    onClick={startVoiceInput}
                    className={`inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-black shadow-sm transition sm:w-44 ${
                      voiceState === 'listening'
                        ? 'bg-red-600 text-white hover:bg-red-700'
                        : 'bg-slate-900 text-white hover:bg-slate-800'
                    }`}
                  >
                    {voiceState === 'listening' ? <MicOff size={20} /> : <Mic size={20} />}
                    {voiceState === 'listening' ? 'Ouvindo...' : 'Falar'}
                  </button>
                  <button
                    onClick={() => handleSendText(message)}
                    disabled={sending || !message.trim()}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-black text-white shadow-sm hover:bg-blue-600 disabled:opacity-60 sm:w-44"
                  >
                    {sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                    Enviar
                  </button>
                </div>
              </div>
            </div>
          </section>

          <aside className="grid min-w-0 gap-4 lg:grid-cols-2 xl:grid-cols-1">
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <History size={18} className="text-primary" />
                  <h3 className="text-lg font-black text-slate-900">Ultimas acoes</h3>
                </div>
                <Clock3 size={16} className="text-slate-400" />
              </div>
              <div className="mt-4 grid gap-3">
                {recentActions.length === 0 ? (
                  <p className="text-sm text-slate-500">Nenhum comando registrado.</p>
                ) : (
                  recentActions.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setMessage(item.text)}
                      className="rounded-xl border border-slate-200 p-3 text-left hover:border-blue-200 hover:bg-blue-50"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="line-clamp-2 text-sm font-bold text-slate-800">{item.text}</p>
                        <span className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-black ${item.success ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                          {item.success ? 'ok' : 'erro'}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">{item.domain || item.intent || '-'} - {formatDate(item.created_at)}</p>
                    </button>
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
                    <p className="mt-1 text-xs leading-5 text-slate-500">{(item.actions || []).join(', ')}</p>
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
