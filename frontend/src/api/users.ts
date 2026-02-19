import api from './client';

export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UserCreatePayload {
  name: string;
  email: string;
  password: string;
  role: string;
  is_active: boolean;
}

export interface UserUpdatePayload {
  name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export const listUsers = async (q?: string) => {
  const { data } = await api.get<User[]>('/users', { params: { q } });
  return data;
};

export const createUser = async (payload: UserCreatePayload) => {
  const { data } = await api.post<User>('/users', payload);
  return data;
};

export const updateUser = async (id: number, payload: UserUpdatePayload) => {
  const { data } = await api.put<User>(`/users/${id}`, payload);
  return data;
};

export const resetUserPassword = async (id: number, password: string) => {
  const { data } = await api.post<User>(`/users/${id}/reset-password`, { password });
  return data;
};
