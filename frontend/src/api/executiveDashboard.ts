import api from './client';

export interface ExecutiveRankItem {
  label: string;
  count: number;
}

export interface ExecutiveEventItem {
  id: number;
  title: string;
  event_type: string;
  severity: string;
  status: string;
  source_type?: string | null;
  source_id?: string | null;
  created_at: string;
}

export interface ExecutivePendingItem {
  id: number;
  title: string;
  priority: string;
  status: string;
  responsible_name?: string | null;
  due_date?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  created_at: string;
}

export interface ExecutiveDashboardSummary {
  total_events_today: number;
  new_events: number;
  high_events: number;
  critical_events: number;
  open_pending_items: number;
  overdue_pending_items: number;
  escalated_pending_items: number;
  failed_routines_today: number;
  top_projects_by_events: ExecutiveRankItem[];
  top_responsibles_by_pending_items: ExecutiveRankItem[];
  critical_event_list: ExecutiveEventItem[];
  overdue_pending_item_list: ExecutivePendingItem[];
}

export const getExecutiveDashboardSummary = async () => {
  const { data } = await api.get<ExecutiveDashboardSummary>('/executive-dashboard/summary');
  return data;
};
