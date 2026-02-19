import api from './client';

export interface Mapping {
  id: number;
  connector_id: number | null;
  mapping_type: string;
  rules_json: Record<string, any>;
}

export const getMapping = async (mapping_type: string) => {
  const { data } = await api.get<Mapping | null>('/mappings', { params: { type: mapping_type } });
  return data;
};

export const upsertMapping = async (mapping_type: string, payload: { connector_id?: number | null; rules_json: Record<string, any> }) => {
  const { data } = await api.put<Mapping>('/mappings', payload, { params: { type: mapping_type } });
  return data;
};

export interface MappingPreviewField {
  raw?: string | null;
  processed?: string | null;
  source?: string | null;
  is_warning: boolean;
}

export interface MappingPreviewTicket {
  id: string;
  title: string;
  cliente: MappingPreviewField;
  sistema: MappingPreviewField;
  entrega: MappingPreviewField;
  source_ref?: string | null;
  source_url?: string | null;
}

export const getMappingPreview = async (connector_id: number, project_id: string, limit = 5) => {
  const { data } = await api.get<{ tickets: MappingPreviewTicket[] }>('/mappings/preview', {
    params: { connector_id, project_id, limit },
  });
  return data;
};
