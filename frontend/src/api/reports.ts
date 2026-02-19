import api from './client';

export interface Report {
  id: number;
  type: string;
  params_json: Record<string, any>;
  generated_at: string;
  status: string;
  file_path?: string | null;
}

export interface ReportRow {
  id: number;
  cliente?: string | null;
  sistema?: string | null;
  entrega?: string | null;
  source_ref?: string | null;
  source_url?: string | null;
  created_at: string;
}

export interface ReportDetail {
  report: Report;
  rows: ReportRow[];
  total: number;
  page: number;
  page_size: number;
  query?: string | null;
}

export interface GenerateReportPayload {
  connector_id: number;
  project_ids: string[];
  start_date: string;
  end_date: string;
  status_id?: string | null;
  query_id?: string | null;
}

export const generateRedmineReport = async (payload: GenerateReportPayload) => {
  const { data } = await api.post<Report>('/reports/redmine-deliveries/generate', payload);
  return data;
};

export const listReports = async () => {
  const { data } = await api.get<Report[]>('/reports');
  return data;
};

export const getReport = async (id: number, params: { page?: number; page_size?: number; q?: string } = {}) => {
  const { data } = await api.get<ReportDetail>(`/reports/${id}`, { params });
  return data;
};

export const exportReportCsv = (id: number) => {
  return api.get(`/reports/${id}/export.csv`, { responseType: 'blob' });
};

export const exportReportPdf = (id: number) => {
  return api.get(`/reports/${id}/export.pdf`, { responseType: 'blob' });
};
