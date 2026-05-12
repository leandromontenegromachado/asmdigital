import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import {
  createReminder,
  deleteReminder,
  FalaAiCheckin,
  FalaAiPollHistoryItem,
  FalaAiPollReport,
  FalaAiReminder,
  getBotReply,
  getLatestPollReport,
  getPollHistoryByDate,
  getPollHistory,
  listCheckins,
  listReminders,
  sendReminderNow,
  updateReminder,
} from '../api/falaAi';

const todayIso = () => new Date().toISOString().slice(0, 10);
const WEEKDAY_OPTIONS = [
  { value: 1, label: 'Seg' },
  { value: 2, label: 'Ter' },
  { value: 3, label: 'Qua' },
  { value: 4, label: 'Qui' },
  { value: 5, label: 'Sex' },
  { value: 6, label: 'Sab' },
  { value: 0, label: 'Dom' },
];

const ensureTimeHHMMSS = (value: string) => (value?.length === 5 ? `${value}:00` : value);
const toTimeInputValue = (value: string) => (value?.length >= 5 ? value.slice(0, 5) : value);
const formatWeekdays = (days: number[]) => WEEKDAY_OPTIONS.filter((item) => days.includes(item.value)).map((item) => item.label).join(', ');

const FalaAiPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [reminders, setReminders] = useState<FalaAiReminder[]>([]);
  const [checkins, setCheckins] = useState<FalaAiCheckin[]>([]);
  const [pollReport, setPollReport] = useState<FalaAiPollReport | null>(null);
  const [pollHistory, setPollHistory] = useState<FalaAiPollHistoryItem[]>([]);
  const [historyDate, setHistoryDate] = useState(todayIso());

  const [newMessage, setNewMessage] = useState('ChefIA: ja comecou o dia garantindo o basico?');
  const [newTime, setNewTime] = useState('09:00');
  const [newDays, setNewDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [editingReminderId, setEditingReminderId] = useState<number | null>(null);
  const [editMessage, setEditMessage] = useState('');
  const [editTime, setEditTime] = useState('09:00');
  const [editDays, setEditDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [botPrompt, setBotPrompt] = useState('bom dia time');
  const [botReply, setBotReply] = useState<string>('');

  const loadAdminData = async () => {
    try {
      const [remindersData, checkinsData] = await Promise.all([listReminders(), listCheckins()]);
      setReminders(remindersData);
      setCheckins(checkinsData);
      setAdminError(null);
    } catch {
      setAdminError('Dados administrativos disponiveis apenas para perfil administrador ou gerente.');
    }

    try {
      const [pollData, historyData] = await Promise.all([getLatestPollReport(), getPollHistory(20)]);
      setPollReport(pollData);
      setPollHistory(historyData);
    } catch {
      setPollReport(null);
      setPollHistory([]);
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    await loadAdminData();
    setLoading(false);
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreateReminder = async () => {
    if (!newMessage.trim()) return;
    if (newDays.length === 0) {
      setError('Selecione pelo menos um dia para o disparo.');
      return;
    }
    setError(null);
    setMessage(null);
    try {
      await createReminder({
        mensagem: newMessage.trim(),
        horario: ensureTimeHHMMSS(newTime),
        dias_semana: [...newDays].sort(),
        ativo: true,
      });
      setMessage('Lembrete criado com sucesso.');
      await loadAdminData();
    } catch {
      setError('Falha ao criar lembrete (requer administrador ou gerente).');
    }
  };

  const toggleDay = (days: number[], day: number) => {
    if (days.includes(day)) {
      return days.filter((item) => item !== day);
    }
    return [...days, day].sort();
  };

  const startEditReminder = (reminder: FalaAiReminder) => {
    setEditingReminderId(reminder.id);
    setEditMessage(reminder.mensagem);
    setEditTime(toTimeInputValue(reminder.horario));
    setEditDays([...(reminder.dias_semana || [1, 2, 3, 4, 5])].sort());
  };

  const cancelEditReminder = () => {
    setEditingReminderId(null);
    setEditMessage('');
    setEditTime('09:00');
    setEditDays([1, 2, 3, 4, 5]);
  };

  const saveEditReminder = async (reminderId: number) => {
    if (!editMessage.trim()) return;
    if (editDays.length === 0) {
      setError('Selecione pelo menos um dia para o disparo.');
      return;
    }
    try {
      await updateReminder(reminderId, {
        mensagem: editMessage.trim(),
        horario: ensureTimeHHMMSS(editTime),
        dias_semana: [...editDays].sort(),
      });
      setMessage('Lembrete atualizado com sucesso.');
      cancelEditReminder();
      await loadAdminData();
    } catch {
      setError('Falha ao editar lembrete.');
    }
  };

  const handleToggleReminder = async (reminder: FalaAiReminder) => {
    try {
      await updateReminder(reminder.id, { ativo: !reminder.ativo });
      await loadAdminData();
    } catch {
      setError('Falha ao atualizar lembrete.');
    }
  };

  const handleDeleteReminder = async (id: number) => {
    try {
      await deleteReminder(id);
      await loadAdminData();
    } catch {
      setError('Falha ao excluir lembrete.');
    }
  };

  const handleSendReminderNow = async (id: number) => {
    try {
      await sendReminderNow(id);
      setMessage('Lembrete enviado para fila.');
    } catch {
      setError('Falha ao enviar lembrete.');
    }
  };

  const handleReloadPoll = async () => {
    try {
      const [pollData, historyData] = await Promise.all([getLatestPollReport(), getPollHistory(20)]);
      setPollReport(pollData);
      setPollHistory(historyData);
    } catch {
      setError('Falha ao carregar enquete atual.');
    }
  };

  const handleFilterHistory = async () => {
    try {
      const historyData = await getPollHistoryByDate(historyDate, 100);
      setPollHistory(historyData);
    } catch {
      setError('Falha ao filtrar historico de enquetes.');
    }
  };

  const handleAskBot = async () => {
    if (!botPrompt.trim()) return;
    try {
      const response = await getBotReply(botPrompt.trim());
      setBotReply(response.resposta);
    } catch {
      setError('Falha ao consultar bot.');
    }
  };

  return (
    <AppShell>
      <Topbar
        title="ChefIA"
        subtitle="Assistente interno com respostas, lembretes e integracao com Teams."
      />

      {loading && <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">Carregando ChefIA...</div>}
      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {adminError && <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{adminError}</div>}

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-800">Bot de apoio</h2>
        <p className="text-xs text-slate-500">Tom amigavel e pronto para plug futuro de LLM.</p>
        <div className="mt-3 flex flex-col gap-2 md:flex-row">
          <input
            value={botPrompt}
            onChange={(e) => setBotPrompt(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Digite uma mensagem"
          />
          <button onClick={handleAskBot} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
            Perguntar
          </button>
        </div>
        {botReply && <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{botReply}</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold text-slate-800">Enquete atual (admin/gerente)</h2>
          <button onClick={handleReloadPoll} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">Atualizar</button>
        </div>
        {!pollReport ? (
          <p className="mt-2 text-xs text-slate-500">Nenhuma enquete enviada ainda.</p>
        ) : (
          <>
            <p className="mt-2 text-xs text-slate-500">
              Dispatch: {pollReport.dispatch_id} | Enviada em: {pollReport.sent_at ? new Date(pollReport.sent_at).toLocaleString('pt-BR') : '-'}
            </p>
            <p className="text-xs text-slate-500">
              {pollReport.checked_in_users.length} respostas | {pollReport.missing_users.length} pendentes
            </p>
            <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold text-emerald-700">Responderam</h3>
                <ul className="mt-2 space-y-1 text-sm">
                  {pollReport.checked_in_users.map((user) => (
                    <li key={user.user_id} className="rounded border border-emerald-100 bg-emerald-50 px-2 py-1">
                      {user.name} ({user.email})
                    </li>
                  ))}
                  {pollReport.checked_in_users.length === 0 && <li className="text-slate-500">Sem respostas ainda.</li>}
                </ul>
              </div>
              <div>
                <h3 className="text-xs font-semibold text-amber-700">Pendentes</h3>
                <ul className="mt-2 space-y-1 text-sm">
                  {pollReport.missing_users.map((user) => (
                    <li key={user.user_id} className="rounded border border-amber-100 bg-amber-50 px-2 py-1">
                      {user.name} ({user.email})
                    </li>
                  ))}
                  {pollReport.missing_users.length === 0 && <li className="text-slate-500">Todos responderam.</li>}
                </ul>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-bold text-slate-800">Historico de enquetes (admin/gerente)</h2>
          <div className="flex items-center gap-2">
            <input type="date" value={historyDate} onChange={(e) => setHistoryDate(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" />
            <button onClick={handleFilterHistory} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">Filtrar</button>
            <button onClick={handleReloadPoll} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">Limpar filtro</button>
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left">Data</th>
                <th className="px-3 py-2 text-left">Mensagem</th>
                <th className="px-3 py-2 text-left">Responderam</th>
                <th className="px-3 py-2 text-left">Pendentes</th>
                <th className="px-3 py-2 text-left">Dispatch</th>
              </tr>
            </thead>
            <tbody>
              {pollHistory.map((item) => (
                <tr key={item.dispatch_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{item.sent_at ? new Date(item.sent_at).toLocaleString('pt-BR') : '-'}</td>
                  <td className="px-3 py-2">{item.message || '-'}</td>
                  <td className="px-3 py-2">{item.checked_in_total}</td>
                  <td className="px-3 py-2">{item.missing_total}</td>
                  <td className="px-3 py-2">{item.dispatch_id}</td>
                </tr>
              ))}
              {pollHistory.length === 0 && (
                <tr>
                  <td className="px-3 py-2 text-slate-500" colSpan={5}>Nenhuma enquete historica registrada.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-800">Lembretes (admin/gerente)</h2>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-5">
          <input value={newMessage} onChange={(e) => setNewMessage(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm md:col-span-2" placeholder="Mensagem" />
          <input type="time" value={newTime} onChange={(e) => setNewTime(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" />
          <button onClick={handleCreateReminder} className="rounded-lg bg-primary px-3 py-2 text-sm font-bold text-white">Criar lembrete</button>
          <div className="md:col-span-5 flex flex-wrap gap-2">
            {WEEKDAY_OPTIONS.map((day) => (
              <button
                key={day.value}
                onClick={() => setNewDays((prev) => toggleDay(prev, day.value))}
                className={`rounded border px-2 py-1 text-xs ${newDays.includes(day.value) ? 'border-primary bg-blue-50 text-primary' : 'border-slate-200 text-slate-600'}`}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left">Horario</th>
                <th className="px-3 py-2 text-left">Dias</th>
                <th className="px-3 py-2 text-left">Mensagem</th>
                <th className="px-3 py-2 text-left">Ativo</th>
                <th className="px-3 py-2 text-left">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {reminders.map((item) => (
                <tr key={item.id} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    {editingReminderId === item.id ? (
                      <input
                        type="time"
                        value={editTime}
                        onChange={(e) => setEditTime(e.target.value)}
                        className="rounded border border-slate-200 px-2 py-1 text-xs"
                      />
                    ) : (
                      item.horario
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {editingReminderId === item.id ? (
                      <div className="flex flex-wrap gap-1">
                        {WEEKDAY_OPTIONS.map((day) => (
                          <button
                            key={day.value}
                            onClick={() => setEditDays((prev) => toggleDay(prev, day.value))}
                            className={`rounded border px-2 py-1 text-xs ${editDays.includes(day.value) ? 'border-primary bg-blue-50 text-primary' : 'border-slate-200 text-slate-600'}`}
                          >
                            {day.label}
                          </button>
                        ))}
                      </div>
                    ) : (
                      formatWeekdays(item.dias_semana || [])
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {editingReminderId === item.id ? (
                      <input
                        value={editMessage}
                        onChange={(e) => setEditMessage(e.target.value)}
                        className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                      />
                    ) : (
                      item.mensagem
                    )}
                  </td>
                  <td className="px-3 py-2">{item.ativo ? 'sim' : 'nao'}</td>
                  <td className="px-3 py-2 flex gap-2">
                    {editingReminderId === item.id ? (
                      <>
                        <button onClick={() => saveEditReminder(item.id)} className="rounded border border-emerald-200 px-2 py-1 text-xs text-emerald-700">Salvar</button>
                        <button onClick={cancelEditReminder} className="rounded border border-slate-200 px-2 py-1 text-xs">Cancelar</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => startEditReminder(item)} className="rounded border border-slate-200 px-2 py-1 text-xs">Editar</button>
                        <button onClick={() => handleToggleReminder(item)} className="rounded border border-slate-200 px-2 py-1 text-xs">{item.ativo ? 'Pausar' : 'Ativar'}</button>
                        <button onClick={() => handleSendReminderNow(item.id)} className="rounded border border-slate-200 px-2 py-1 text-xs">Enviar agora</button>
                      </>
                    )}
                    <button onClick={() => handleDeleteReminder(item.id)} className="rounded border border-red-200 px-2 py-1 text-xs text-red-700">Excluir</button>
                  </td>
                </tr>
              ))}
              {reminders.length === 0 && (
                <tr>
                  <td className="px-3 py-2 text-slate-500" colSpan={5}>Nenhum lembrete configurado.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-800">Ultimas respostas (admin/gerente)</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Usuario</th>
                <th className="px-3 py-2 text-left">Tipo</th>
                <th className="px-3 py-2 text-left">Origem</th>
                <th className="px-3 py-2 text-left">Data</th>
              </tr>
            </thead>
            <tbody>
              {checkins.map((item) => (
                <tr key={item.id} className="border-t border-slate-100">
                  <td className="px-3 py-2">{item.id}</td>
                  <td className="px-3 py-2">{item.user_id}</td>
                  <td className="px-3 py-2">{item.tipo}</td>
                  <td className="px-3 py-2">{item.origem}</td>
                  <td className="px-3 py-2">{new Date(item.created_at).toLocaleString('pt-BR')}</td>
                </tr>
              ))}
              {checkins.length === 0 && (
                <tr>
                  <td className="px-3 py-2 text-slate-500" colSpan={5}>Sem respostas para exibir.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
};

export default FalaAiPage;
