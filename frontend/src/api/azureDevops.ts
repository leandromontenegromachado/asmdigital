import api from './client';

export interface AzureDevOpsLinkedItem {
  id: number;
  type?: string | null;
  title?: string | null;
  state?: string | null;
}

export interface AzureDevOpsWorkItem {
  id: number;
  type?: string | null;
  title?: string | null;
  state?: string | null;
  area_path?: string | null;
  iteration_path?: string | null;
  assigned_to?: string | null;
  hours: {
    original: number;
    remaining: number;
    completed: number;
  };
  parent?: AzureDevOpsLinkedItem | null;
  epic?: AzureDevOpsLinkedItem | null;
}

export interface AzureDevOpsSnapshot {
  items: AzureDevOpsWorkItem[];
  totals: {
    total: number;
    with_epic: number;
    without_epic: number;
    by_state: Record<string, number>;
    hours: {
      original: number;
      remaining: number;
      completed: number;
    };
  };
  diagnostics: {
    pbi_without_task: {
      total: number;
      users: Array<{
        user: string;
        count: number;
        items: Array<{
          id: number;
          title?: string | null;
          state?: string | null;
          type?: string | null;
          parent?: AzureDevOpsLinkedItem | null;
          epic?: AzureDevOpsLinkedItem | null;
        }>;
      }>;
    };
    tasks_without_hours: {
      total: number;
      users: Array<{
        user: string;
        count: number;
        items: Array<{
          id: number;
          title?: string | null;
          state?: string | null;
          type?: string | null;
          parent?: AzureDevOpsLinkedItem | null;
          epic?: AzureDevOpsLinkedItem | null;
        }>;
      }>;
    };
  };
}

export interface AzureDevOpsSnapshotParams {
  project?: string;
  team?: string;
  area_path?: string;
  iteration_path?: string;
  top?: number;
}

export const getAzureDevOpsSnapshot = async (connectorId: number, params: AzureDevOpsSnapshotParams) => {
  const { data } = await api.get<AzureDevOpsSnapshot>(`/azure-devops/connectors/${connectorId}/snapshot`, { params });
  return data;
};
