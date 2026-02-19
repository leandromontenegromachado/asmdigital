import api from './client';
import { Report } from './reports';

export interface PromptReportTemplate {
  id: number;
  name: string;
  connector_id: number;
  prompt_text: string;
  params_json: Record<string, any>;
  schedule_cron?: string | null;
  is_enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptReportTemplatePayload {
  name: string;
  connector_id: number;
  prompt_text: string;
  params_json: Record<string, any>;
  schedule_cron?: string | null;
  is_enabled: boolean;
}

export interface PromptReportRunResponse {
  report_id: number;
  status: string;
  extracted_filters: Record<string, any>;
}

export const listPromptReportTemplates = async () => {
  const { data } = await api.get<PromptReportTemplate[]>('/prompt-reports');
  return data;
};

export const createPromptReportTemplate = async (payload: PromptReportTemplatePayload) => {
  const { data } = await api.post<PromptReportTemplate>('/prompt-reports', payload);
  return data;
};

export const updatePromptReportTemplate = async (id: number, payload: Partial<PromptReportTemplatePayload>) => {
  const { data } = await api.put<PromptReportTemplate>(`/prompt-reports/${id}`, payload);
  return data;
};

export const deletePromptReportTemplate = async (id: number) => {
  await api.delete(`/prompt-reports/${id}`);
};

export const runPromptReportTemplate = async (id: number, prompt_override?: string) => {
  const { data } = await api.post<PromptReportRunResponse>(`/prompt-reports/${id}/run`, { prompt_override });
  return data;
};

export const listPromptReportRuns = async (id: number, limit = 20) => {
  const { data } = await api.get<Report[]>(`/prompt-reports/${id}/runs`, { params: { limit } });
  return data;
};
