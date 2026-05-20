import api from './client';

export interface AssistantAction {
  id: number;
  action_type: string;
  status: string;
  payload_json: Record<string, any>;
  result_json: Record<string, any>;
  created_at: string;
  confirmed_at?: string | null;
}

export interface AssistantMessageResponse {
  conversation_id: number;
  reply: string;
  action?: AssistantAction | null;
}

export interface AssistantActionResult {
  id: number;
  status: string;
  result_json: Record<string, any>;
}

export const sendAssistantMessage = async (text: string, channel = 'internal') => {
  const { data } = await api.post<AssistantMessageResponse>('/assistant/messages', { text, channel });
  return data;
};

export const listAssistantActions = async () => {
  const { data } = await api.get<AssistantAction[]>('/assistant/actions');
  return data;
};

export const confirmAssistantAction = async (id: number) => {
  const { data } = await api.post<AssistantActionResult>(`/assistant/actions/${id}/confirm`);
  return data;
};

export const cancelAssistantAction = async (id: number) => {
  const { data } = await api.post<AssistantActionResult>(`/assistant/actions/${id}/cancel`);
  return data;
};

export const bindCurrentTelegramChat = async (chatId: string, username?: string) => {
  const { data } = await api.post<{ status: string; chat_id: string }>('/assistant/telegram/bind-current', {
    chat_id: chatId,
    username: username || undefined,
  });
  return data;
};
