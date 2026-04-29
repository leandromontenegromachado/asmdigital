import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import {
  createEmployee,
  createEvaluationCycle,
  CycleStatus,
  Employee,
  EvaluationCycle,
  listEmployees,
  listEvaluationCycles,
  updateEvaluationCycleStatus,
} from '../api/evaluation';

const today = new Date().toISOString().slice(0, 10);
const statuses: CycleStatus[] = ['RASCUNHO', 'EM_COLETA', 'EM_ANALISE', 'EM_CALIBRACAO', 'FINALIZADO'];

const EvaluationCyclesPage: React.FC = () => {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [cycleForm, setCycleForm] = useState({ name: 'Ciclo Avaliativo', start_date: today, end_date: today, notes: '' });
  const [employeeForm, setEmployeeForm] = useState({ name: '', email: '', department: '', position: '', manager_id: '' });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cycleRows, employeeRows] = await Promise.all([
        listEvaluationCycles(),
        listEmployees(departmentFilter ? { department: departmentFilter } : undefined),
      ]);
      setCycles(cycleRows);
      setEmployees(employeeRows);
    } catch {
      setError('Falha ao carregar avaliação.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [departmentFilter]);

  const saveCycle = async () => {
    await createEvaluationCycle({ ...cycleForm, notes: cycleForm.notes || null });
    setCycleForm({ name: 'Ciclo Avaliativo', start_date: today, end_date: today, notes: '' });
    await load();
  };

  const saveEmployee = async () => {
    await createEmployee({
      name: employeeForm.name,
      email: employeeForm.email,
      department: employeeForm.department || null,
      position: employeeForm.position || null,
      manager_id: employeeForm.manager_id ? Number(employeeForm.manager_id) : null,
      active: true,
    });
    setEmployeeForm({ name: '', email: '', department: '', position: '', manager_id: '' });
    await load();
  };

  return (
    <AppShell>
      <Topbar title="Avaliação - Ciclos e Colaboradores" subtitle="Cadastre ciclos avaliativos e a base de colaboradores do MVP." />

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-bold text-slate-700">Novo ciclo avaliativo</h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleForm.name} onChange={(e) => setCycleForm((p) => ({ ...p, name: e.target.value }))} placeholder="Nome do ciclo" />
            <input type="date" className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleForm.start_date} onChange={(e) => setCycleForm((p) => ({ ...p, start_date: e.target.value }))} />
            <input type="date" className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleForm.end_date} onChange={(e) => setCycleForm((p) => ({ ...p, end_date: e.target.value }))} />
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleForm.notes} onChange={(e) => setCycleForm((p) => ({ ...p, notes: e.target.value }))} placeholder="Observações" />
          </div>
          <button onClick={saveCycle} className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-bold text-white">Criar ciclo</button>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-bold text-slate-700">Novo colaborador</h3>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={employeeForm.name} onChange={(e) => setEmployeeForm((p) => ({ ...p, name: e.target.value }))} placeholder="Nome" />
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={employeeForm.email} onChange={(e) => setEmployeeForm((p) => ({ ...p, email: e.target.value }))} placeholder="E-mail" />
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={employeeForm.department} onChange={(e) => setEmployeeForm((p) => ({ ...p, department: e.target.value }))} placeholder="Área" />
            <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={employeeForm.position} onChange={(e) => setEmployeeForm((p) => ({ ...p, position: e.target.value }))} placeholder="Cargo" />
            <select className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={employeeForm.manager_id} onChange={(e) => setEmployeeForm((p) => ({ ...p, manager_id: e.target.value }))}>
              <option value="">Sem gestor</option>
              {employees.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
            </select>
          </div>
          <button onClick={saveEmployee} className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-bold text-white">Cadastrar colaborador</button>
        </div>
      </section>

      {loading && <StateBlock tone="loading" title="Carregando dados" />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}

      {!loading && !error && (
        <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 text-left">Ciclo</th>
                  <th className="px-4 py-3 text-left">Período</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map((cycle) => (
                  <tr key={cycle.id} className="border-t border-slate-100">
                    <td className="px-4 py-3 font-semibold text-slate-800">{cycle.name}</td>
                    <td className="px-4 py-3 text-slate-500">{cycle.start_date} até {cycle.end_date}</td>
                    <td className="px-4 py-3">
                      <select className="rounded-md border border-slate-200 px-2 py-1 text-xs" value={cycle.status} onChange={async (e) => { await updateEvaluationCycleStatus(cycle.id, e.target.value as CycleStatus); await load(); }}>
                        {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 p-3">
              <input className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} placeholder="Filtrar por área" />
            </div>
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 text-left">Colaborador</th>
                  <th className="px-4 py-3 text-left">Área</th>
                  <th className="px-4 py-3 text-left">Gestor</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((employee) => (
                  <tr key={employee.id} className="border-t border-slate-100">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-800">{employee.name}</div>
                      <div className="text-xs text-slate-500">{employee.email}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{employee.department || '-'}</td>
                    <td className="px-4 py-3 text-slate-600">{employee.manager_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </AppShell>
  );
};

export default EvaluationCyclesPage;
