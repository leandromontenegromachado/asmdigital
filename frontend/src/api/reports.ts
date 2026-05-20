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
  raw_json?: Record<string, any> | null;
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

export const listReports = async (params: { page?: number; page_size?: number } = {}) => {
  const { data } = await api.get<Report[]>('/reports', { params });
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

export interface ReportNotificationResponse {
  report_id: number;
  total: number;
  sent: number;
  simulated: number;
  errors: number;
  pending_approval: number;
  notifications: Array<{
    id: number;
    row_id?: number | null;
    employee_name?: string | null;
    recipient?: string | null;
    status: string;
    error?: string | null;
  }>;
}

export const sendReportNotifications = async (
  id: number,
  payload: {
    row_ids?: number[];
    template_id?: number | null;
    channel?: string | null;
    subject?: string | null;
    message?: string | null;
    requires_approval?: boolean;
    notify_manager?: boolean;
    simulation?: boolean;
  } = {},
) => {
  const { data } = await api.post<ReportNotificationResponse>(`/reports/${id}/notifications/send`, payload);
  return data;
};
