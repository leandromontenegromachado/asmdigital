import api from './client';

export interface NotificationTemplate {
  id: number;
  name: string;
  variable_automation_id?: number | null;
  channel: string;
  subject: string | null;
  body: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationRule {
  id: number;
  automation_id: number;
  automation_name?: string | null;
  is_active: boolean;
  send_condition?: string | null;
  recipient_type: string;
  preferred_channel: string;
  fallback_channel?: string | null;
  template_id?: number | null;
  template_name?: string | null;
  requires_approval: boolean;
  notify_manager: boolean;
  manager_condition?: string | null;
  params_json: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationHistory {
  id: number;
  execution_id?: number | null;
  automation_id?: number | null;
  automation_name?: string | null;
  employee_id?: number | null;
  employee_name?: string | null;
  channel: string;
  recipient?: string | null;
  subject?: string | null;
  message?: string | null;
  status: string;
  data_envio?: string | null;
  sent_at?: string | null;
  error?: string | null;
  attempts: number;
  simulation: boolean;
  created_at: string;
}

export interface NotificationTemplateVariables {
  automation_id: number;
  source_run_ids: number[];
  variables: string[];
  samples: Record<string, any>;
  aliases: Record<string, string>;
}

export const listNotificationTemplates = async () =>
  (await api.get<NotificationTemplate[]>('/notification-templates')).data;

export const listNotificationTemplateVariables = async (automationId: number) =>
  (await api.get<NotificationTemplateVariables>('/notification-template-variables', { params: { automation_id: automationId } })).data;

export const createNotificationTemplate = async (payload: Omit<NotificationTemplate, 'id' | 'created_at' | 'updated_at'>) =>
  (await api.post<NotificationTemplate>('/notification-templates', payload)).data;

export const updateNotificationTemplate = async (id: number, payload: Partial<NotificationTemplate>) =>
  (await api.put<NotificationTemplate>(`/notification-templates/${id}`, payload)).data;

export const deleteNotificationTemplate = async (id: number) => {
  await api.delete(`/notification-templates/${id}`);
};

export const listNotificationRules = async (params?: { automation_id?: number }) =>
  (await api.get<NotificationRule[]>('/notification-rules', { params })).data;

export const createNotificationRule = async (payload: Omit<NotificationRule, 'id' | 'automation_name' | 'template_name' | 'created_at' | 'updated_at'>) =>
  (await api.post<NotificationRule>('/notification-rules', payload)).data;

export const updateNotificationRule = async (id: number, payload: Partial<NotificationRule>) =>
  (await api.put<NotificationRule>(`/notification-rules/${id}`, payload)).data;

export const deleteNotificationRule = async (id: number) => {
  await api.delete(`/notification-rules/${id}`);
};

export const listNotifications = async (params?: { execution_id?: number; automation_id?: number; status?: string; limit?: number; offset?: number }) =>
  (await api.get<NotificationHistory[]>('/notifications', { params })).data;

export const retryNotification = async (id: number) =>
  (await api.post(`/notifications/${id}/retry`)).data;

export const approveNotification = async (id: number) =>
  (await api.post(`/notifications/${id}/approve`)).data;

export const cancelNotification = async (id: number) =>
  (await api.post(`/notifications/${id}/cancel`)).data;
