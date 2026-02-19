import api from './client';

export interface Connector {
  id: number;
  type: string;
  name: string;
  config_json: Record<string, any>;
  is_active: boolean;
}

export const listConnectors = async () => {
  const { data } = await api.get<Connector[]>('/connectors');
  return data;
};

export const createConnector = async (payload: Omit<Connector, 'id'>) => {
  const { data } = await api.post<Connector>('/connectors', payload);
  return data;
};

export const updateConnector = async (id: number, payload: Partial<Connector>) => {
  const { data } = await api.put<Connector>(`/connectors/${id}`, payload);
  return data;
};

export const testConnector = async (id: number) => {
  const { data } = await api.post(`/connectors/${id}/test`);
  return data;
};

export interface RedmineQuery {
  id: number;
  name: string;
  is_public?: boolean | null;
}

export const listRedmineQueries = async (id: number, projectId?: string) => {
  const { data } = await api.get<RedmineQuery[]>(`/connectors/${id}/queries`, {
    params: projectId ? { project_id: projectId } : undefined,
  });
  return data;
};
