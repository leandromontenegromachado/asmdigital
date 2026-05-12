import api from './client';

export interface DashboardStatSummary {
  active_connectors: number;
  total_connectors: number;
  notifications_today: number;
  notifications_yesterday: number;
  pending_reports: number;
  active_automations: number;
}

export interface DashboardConnectorSummary {
  id: string;
  name: string;
  status: string;
  type: string;
  provider: string;
}

export interface DashboardAlertSummary {
  id: string;
  title: string;
  subtitle: string;
  type: string;
  tag: string;
  created_at?: string | null;
}

export interface DashboardAutomationSummary {
  id: string;
  time: string;
  title: string;
  subtitle: string;
  status: string;
  is_next: boolean;
  next_run_at?: string | null;
}

export interface DashboardSummary {
  generated_at: string;
  stats: DashboardStatSummary;
  connectors: DashboardConnectorSummary[];
  recent_alerts: DashboardAlertSummary[];
  upcoming_automations: DashboardAutomationSummary[];
}

export const getDashboardSummary = async () => {
  const { data } = await api.get<DashboardSummary>('/dashboard/summary');
  return data;
};
