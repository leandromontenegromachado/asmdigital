import api from './client';

export interface ManagementEventRule {
  id: number;
  name: string;
  description?: string | null;
  is_active: boolean;
  condition_json: Record<string, unknown>;
  action_json: Record<string, unknown>;
  priority: number;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ManagementEventRulePayload {
  name: string;
  description?: string | null;
  is_active: boolean;
  condition_json: Record<string, unknown>;
  action_json: Record<string, unknown>;
  priority: number;
}

export const listManagementEventRules = async () => {
  const { data } = await api.get<ManagementEventRule[]>('/management-events/rules');
  return data;
};

export const createManagementEventRule = async (payload: ManagementEventRulePayload) => {
  const { data } = await api.post<ManagementEventRule>('/management-events/rules', payload);
  return data;
};

export const updateManagementEventRule = async (id: number, payload: Partial<ManagementEventRulePayload>) => {
  const { data } = await api.put<ManagementEventRule>(`/management-events/rules/${id}`, payload);
  return data;
};

export const deleteManagementEventRule = async (id: number) => {
  await api.delete(`/management-events/rules/${id}`);
};
