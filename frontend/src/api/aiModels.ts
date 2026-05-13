import api from './client';

export interface AiModel {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  description?: string | null;
  api_key_env?: string | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface AiModelAssignment {
  id: number;
  feature_key: string;
  feature_label: string;
  model_id: number;
  model_name: string;
  provider: string;
  provider_label: string;
  provider_supported: boolean;
  external_model_id: string;
  created_at: string;
  updated_at: string;
}

export interface AiModelFeature {
  key: string;
  label: string;
}

export type AiModelPayload = Omit<AiModel, 'id' | 'created_at' | 'updated_at'>;

export const listAiModels = async () =>
  (await api.get<AiModel[]>('/ai-models')).data;

export const createAiModel = async (payload: AiModelPayload) =>
  (await api.post<AiModel>('/ai-models', payload)).data;

export const updateAiModel = async (id: number, payload: Partial<AiModelPayload>) =>
  (await api.put<AiModel>(`/ai-models/${id}`, payload)).data;

export const deleteAiModel = async (id: number) => {
  await api.delete(`/ai-models/${id}`);
};

export const listAiModelFeatures = async () =>
  (await api.get<AiModelFeature[]>('/ai-models/features')).data;

export const listAiModelAssignments = async () =>
  (await api.get<AiModelAssignment[]>('/ai-models/assignments')).data;

export const updateAiModelAssignment = async (featureKey: string, modelId: number) =>
  (await api.put<AiModelAssignment>(`/ai-models/assignments/${featureKey}`, { model_id: modelId })).data;
