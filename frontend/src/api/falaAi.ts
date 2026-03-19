import api from './client';

export interface FalaAiCheckin {
  id: number;
  user_id: number;
  tipo: string;
  origem: string;
  created_at: string;
}

export interface FalaAiReminder {
  id: number;
  mensagem: string;
  horario: string;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

export interface FalaAiDailyUserStatus {
  user_id: number;
  name: string;
  email: string;
  last_checkin_at?: string | null;
}

export interface FalaAiDailyReport {
  date: string;
  checked_in_users: FalaAiDailyUserStatus[];
  missing_users: FalaAiDailyUserStatus[];
}

export interface FalaAiDispatchConfirmation {
  user_id: number;
  name: string;
  email: string;
  confirmation?: {
    checkin_id?: number;
    reason?: string;
    at?: string;
  } | null;
}

export interface FalaAiPollReport {
  dispatch_id: string;
  reminder_id?: number | null;
  message?: string | null;
  sent_at?: string | null;
  channel_id?: string | null;
  conversation_id?: string | null;
  checked_in_users: FalaAiDispatchConfirmation[];
  missing_users: FalaAiDispatchConfirmation[];
}

export interface FalaAiPollHistoryItem {
  dispatch_id: string;
  reminder_id?: number | null;
  message?: string | null;
  sent_at?: string | null;
  checked_in_total: number;
  missing_total: number;
}

export const createCheckin = async (payload?: { user_id?: number; tipo?: string; origem?: string }) => {
  const { data } = await api.post<FalaAiCheckin>('/fala-ai/checkin', payload || { tipo: 'manual', origem: 'web' });
  return data;
};

export const listReminders = async () => {
  const { data } = await api.get<FalaAiReminder[]>('/fala-ai/reminders');
  return data;
};

export const createReminder = async (payload: { mensagem: string; horario: string; ativo: boolean }) => {
  const { data } = await api.post<FalaAiReminder>('/fala-ai/reminders', payload);
  return data;
};

export const updateReminder = async (id: number, payload: Partial<{ mensagem: string; horario: string; ativo: boolean }>) => {
  const { data } = await api.put<FalaAiReminder>(`/fala-ai/reminders/${id}`, payload);
  return data;
};

export const deleteReminder = async (id: number) => {
  await api.delete(`/fala-ai/reminders/${id}`);
};

export const sendReminderNow = async (id: number) => {
  await api.post(`/fala-ai/reminders/${id}/send`);
};

export const listCheckins = async () => {
  const { data } = await api.get<FalaAiCheckin[]>('/fala-ai/checkins');
  return data;
};

export const getDailyReport = async (dateRef?: string) => {
  const { data } = await api.get<FalaAiDailyReport>('/fala-ai/report/daily', {
    params: dateRef ? { date_ref: `${dateRef}T00:00:00Z` } : undefined,
  });
  return data;
};

export const getBotReply = async (mensagem: string) => {
  const { data } = await api.post<{ resposta: string }>('/fala-ai/reply', { mensagem });
  return data;
};

export const getLatestPollReport = async () => {
  const { data } = await api.get<FalaAiPollReport>('/fala-ai/report/poll/latest');
  return data;
};

export const getPollHistory = async (limit = 20) => {
  const { data } = await api.get<FalaAiPollHistoryItem[]>('/fala-ai/report/poll/history', {
    params: { limit },
  });
  return data;
};

export const getPollHistoryByDate = async (dateRef: string, limit = 100) => {
  const { data } = await api.get<FalaAiPollHistoryItem[]>('/fala-ai/report/poll/history', {
    params: { limit, date_ref: dateRef },
  });
  return data;
};
