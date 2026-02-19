import api from './client';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export const login = async (payload: LoginRequest) => {
  const { data } = await api.post<LoginResponse>('/auth/login', payload);
  return data;
};

export const me = async () => {
  const { data } = await api.get('/auth/me');
  return data;
};
