import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { Modal } from '../components/Modal';
import { StateBlock } from '../components/StateBlock';
import { StatusBadge } from '../components/StatusBadge';
import { createUser, listUsers, resetUserPassword, updateUser, User } from '../api/users';

const defaultForm = {
  name: '',
  email: '',
  password: '',
  role: 'viewer',
  is_active: true,
};

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form, setForm] = useState({ ...defaultForm });

  const loadUsers = async (q?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listUsers(q);
      setUsers(data);
    } catch (err) {
      setError('Não foi possível carregar os usuários.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const openCreate = () => {
    setEditingUser(null);
    setForm({ ...defaultForm });
    setModalOpen(true);
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setForm({
      name: user.name,
      email: user.email,
      password: '',
      role: user.role,
      is_active: user.is_active,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingUser) {
        await updateUser(editingUser.id, {
          name: form.name,
          email: form.email,
          role: form.role,
          is_active: form.is_active,
        });
      } else {
        await createUser({
          name: form.name,
          email: form.email,
          password: form.password,
          role: form.role,
          is_active: form.is_active,
        });
      }
      setModalOpen(false);
      await loadUsers(query || undefined);
    } catch (err) {
      setError('Erro ao salvar usuário.');
    }
  };

  const handleResetPassword = async (user: User) => {
    const newPassword = prompt(`Defina a nova senha para ${user.email}`);
    if (!newPassword) return;
    try {
      await resetUserPassword(user.id, newPassword);
      alert('Senha atualizada.');
    } catch (err) {
      alert('Falha ao atualizar senha.');
    }
  };

  const handleDeactivate = async (user: User) => {
    try {
      await updateUser(user.id, { is_active: !user.is_active });
      await loadUsers(query || undefined);
    } catch (err) {
      setError('Erro ao atualizar status.');
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Usuários"
        subtitle="Gerencie contas e permissões de acesso."
        action={
          <button
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-200 hover:bg-primary-dark transition-colors"
          >
            Novo usuário
          </button>
        }
      />

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Buscar por nome ou email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                loadUsers(query || undefined);
              }
            }}
          />
          <button
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600"
            onClick={() => loadUsers(query || undefined)}
          >
            Filtrar
          </button>
        </div>
      </section>

      {loading && <StateBlock tone="loading" title="Carregando usuários" description="Aguarde alguns segundos." />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}
      {!loading && !error && users.length === 0 && (
        <StateBlock tone="empty" title="Nenhum usuário encontrado" description="Crie o primeiro usuário para começar." />
      )}

      {!loading && users.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Nome</th>
                <th className="px-4 py-3 text-left font-semibold">Email</th>
                <th className="px-4 py-3 text-left font-semibold">Role</th>
                <th className="px-4 py-3 text-left font-semibold">Status</th>
                <th className="px-4 py-3 text-left font-semibold">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 text-slate-700 font-semibold">{user.name}</td>
                  <td className="px-4 py-3 text-slate-500">{user.email}</td>
                  <td className="px-4 py-3 text-slate-500">{user.role}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={user.is_active ? 'online' : 'offline'} />
                  </td>
                  <td className="px-4 py-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => openEdit(user)}
                      className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => handleResetPassword(user)}
                      className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
                    >
                      Reset senha
                    </button>
                    <button
                      onClick={() => handleDeactivate(user)}
                      className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
                    >
                      {user.is_active ? 'Desativar' : 'Ativar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingUser ? 'Editar usuário' : 'Novo usuário'}
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Nome</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-slate-700">Email</label>
            <input
              className="rounded-lg border border-slate-200 px-3 py-2"
              value={form.email}
              onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
            />
          </div>
          {!editingUser && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-slate-700">Senha</label>
              <input
                type="password"
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.password}
                onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
              />
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-slate-700">Role</label>
              <select
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.role}
                onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
              >
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold text-slate-700">Status</label>
              <select
                className="rounded-lg border border-slate-200 px-3 py-2"
                value={form.is_active ? 'active' : 'inactive'}
                onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === 'active' }))}
              >
                <option value="active">Ativo</option>
                <option value="inactive">Inativo</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setModalOpen(false)}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white"
            >
              Salvar
            </button>
          </div>
        </div>
      </Modal>
    </AppShell>
  );
};

export default UsersPage;
