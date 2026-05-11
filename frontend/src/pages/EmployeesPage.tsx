import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Save, Trash2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { Employee, createEmployee, deleteEmployee, listEmployees, updateEmployee } from '../api/evaluation';

const emptyForm = {
  name: '',
  email: '',
  matricula: '',
  teams_user_id: '',
  cargo: '',
  setor: '',
  manager_id: '',
  active: true,
  recebe_notificacao: true,
  participa_avaliacao: true,
  canal_preferencial: 'email',
};

const EmployeesPage: React.FC = () => {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const formRef = useRef<HTMLElement | null>(null);

  const duplicateEmail = useMemo(() => {
    const email = form.email.trim().toLowerCase();
    if (!email) return null;
    return employees.find((item) => item.email.toLowerCase() === email && item.id !== editing?.id) || null;
  }, [employees, form.email, editing?.id]);

  const duplicateMatricula = useMemo(() => {
    const matricula = form.matricula.trim();
    if (!matricula) return null;
    return employees.find((item) => item.matricula === matricula && item.id !== editing?.id) || null;
  }, [employees, form.matricula, editing?.id]);

  const scrollToForm = () => {
    window.setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  };

  const getErrorMessage = (err: unknown, fallback: string) => {
    const detail = (err as any)?.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg || JSON.stringify(item)).join('; ');
    }
    return fallback;
  };

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setEmployees(await listEmployees());
    } catch (err) {
      setError(getErrorMessage(err, 'Nao foi possivel carregar os funcionarios.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm });
    setError(null);
    scrollToForm();
  };

  const openEdit = (employee: Employee) => {
    setEditing(employee);
    setForm({
      name: employee.name,
      email: employee.email,
      matricula: employee.matricula || '',
      teams_user_id: employee.teams_user_id || '',
      cargo: employee.cargo || employee.position || '',
      setor: employee.setor || employee.department || '',
      manager_id: employee.manager_id ? String(employee.manager_id) : '',
      active: employee.active,
      recebe_notificacao: employee.recebe_notificacao ?? true,
      participa_avaliacao: employee.participa_avaliacao ?? true,
      canal_preferencial: employee.canal_preferencial || 'email',
    });
    setError(null);
    scrollToForm();
  };

  const save = async () => {
    setError(null);
    if (duplicateEmail) {
      setError(`Este email ja esta cadastrado para ${duplicateEmail.name}. Use outro email ou edite esse funcionario.`);
      scrollToForm();
      return;
    }
    if (duplicateMatricula) {
      setError(`Esta matricula ja esta cadastrada para ${duplicateMatricula.name}.`);
      scrollToForm();
      return;
    }
    const payload = {
      name: form.name.trim(),
      email: form.email.trim(),
      matricula: form.matricula.trim() || null,
      teams_user_id: form.teams_user_id.trim() || null,
      cargo: form.cargo.trim() || null,
      setor: form.setor.trim() || null,
      department: form.setor.trim() || null,
      position: form.cargo.trim() || null,
      manager_id: form.manager_id ? Number(form.manager_id) : null,
      active: form.active,
      recebe_notificacao: form.recebe_notificacao,
      participa_avaliacao: form.participa_avaliacao,
      canal_preferencial: form.canal_preferencial,
    };
    try {
      if (editing) {
        await updateEmployee(editing.id, payload);
      } else {
        await createEmployee(payload);
      }
      openNew();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, 'Falha ao salvar funcionario.'));
      scrollToForm();
    }
  };

  const removeEmployee = async (employee: Employee) => {
    if (!window.confirm(`Excluir o funcionario ${employee.name}?`)) return;
    setError(null);
    try {
      await deleteEmployee(employee.id);
      if (editing?.id === employee.id) {
        openNew();
      }
      await load();
    } catch (err) {
      setError(getErrorMessage(err, 'Falha ao excluir funcionario. Se houver historico vinculado, desative o cadastro.'));
      scrollToForm();
    }
  };

  return (
    <AppShell>
      <Topbar
        title="Funcionarios"
        subtitle="Cadastro reutilizavel para notificacoes, rotinas e avaliacao."
        action={
          <button onClick={openNew} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white">
            <Plus className="h-4 w-4" />
            Novo
          </button>
        }
      />

      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <section ref={formRef} className="mb-6 scroll-mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-slate-900">{editing ? `Editar ${editing.name}` : 'Novo funcionario'}</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Nome" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div>
            <input className={`w-full rounded-lg border px-3 py-2 text-sm ${duplicateEmail ? 'border-red-300 bg-red-50' : 'border-slate-200'}`} placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            {duplicateEmail && <p className="mt-1 text-xs font-semibold text-red-600">Ja usado por {duplicateEmail.name}.</p>}
          </div>
          <div>
            <input className={`w-full rounded-lg border px-3 py-2 text-sm ${duplicateMatricula ? 'border-red-300 bg-red-50' : 'border-slate-200'}`} placeholder="Matricula" value={form.matricula} onChange={(e) => setForm({ ...form, matricula: e.target.value })} />
            {duplicateMatricula && <p className="mt-1 text-xs font-semibold text-red-600">Ja usada por {duplicateMatricula.name}.</p>}
          </div>
          <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Teams user ID" value={form.teams_user_id} onChange={(e) => setForm({ ...form, teams_user_id: e.target.value })} />
          <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Cargo" value={form.cargo} onChange={(e) => setForm({ ...form, cargo: e.target.value })} />
          <input className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Setor" value={form.setor} onChange={(e) => setForm({ ...form, setor: e.target.value })} />
          <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.manager_id} onChange={(e) => setForm({ ...form, manager_id: e.target.value })}>
            <option value="">Sem gestor</option>
            {employees.filter((item) => item.id !== editing?.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={form.canal_preferencial} onChange={(e) => setForm({ ...form, canal_preferencial: e.target.value })}>
            <option value="email">Email</option>
            <option value="teams">Teams</option>
            <option value="internal">Interna</option>
          </select>
          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-700">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />Ativo</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.recebe_notificacao} onChange={(e) => setForm({ ...form, recebe_notificacao: e.target.checked })} />Recebe notificacao</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.participa_avaliacao} onChange={(e) => setForm({ ...form, participa_avaliacao: e.target.checked })} />Participa avaliacao</label>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button disabled={Boolean(duplicateEmail || duplicateMatricula)} onClick={save} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">
            <Save className="h-4 w-4" />
            Salvar
          </button>
          {editing && <button onClick={openNew} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">Cancelar</button>}
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loading ? <div className="p-6 text-sm text-slate-500">Carregando...</div> : (
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 text-left">Nome</th>
                <th className="px-4 py-3 text-left">Setor</th>
                <th className="px-4 py-3 text-left">Canal</th>
                <th className="px-4 py-3 text-left">Gestor</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.id} className="border-t border-slate-100">
                  <td className="px-4 py-3"><div className="font-semibold">{employee.name}</div><div className="text-xs text-slate-500">{employee.email}</div></td>
                  <td className="px-4 py-3">{employee.setor || employee.department || '-'}</td>
                  <td className="px-4 py-3">{employee.canal_preferencial || 'email'}</td>
                  <td className="px-4 py-3">{employee.manager_name || '-'}</td>
                  <td className="px-4 py-3">{employee.active ? 'Ativo' : 'Inativo'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-3">
                      <button onClick={() => openEdit(employee)} className="font-semibold text-cyan-700">Editar</button>
                      <button onClick={() => removeEmployee(employee)} className="inline-flex items-center gap-1 font-semibold text-red-600">
                        <Trash2 className="h-4 w-4" />
                        Excluir
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </AppShell>
  );
};

export default EmployeesPage;
