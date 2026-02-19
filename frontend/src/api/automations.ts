import api from './client';

export interface Automation {
  id: number;
  key: string;
  name: string;
  schedule_cron?: string | null;
  is_enabled: boolean;
  params_json: Record<string, any>;
  last_run_at?: string | null;
  next_run_at?: string | null;
}

export interface AutomationRun {
  id: number;
  automation_id: number;
  automation_name: string;
  automation_key: string;
  started_at: string;
  finished_at?: string | null;
  status: string;
  summary_json: Record<string, any>;
  error_text?: string | null;
}

export const listAutomations = async () => {
  const { data } = await api.get<Automation[]>('/automations');
  return data;
};

export const runAutomation = async (id: number, simulation = true) => {
  const { data } = await api.post(`/automations/${id}/run`, { simulation });
  return data;
};

export const listAutomationRuns = async () => {
  const { data } = await api.get<AutomationRun[]>('/automations/runs');
  return data;
};
