import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import {
  calculateScores,
  Employee,
  EvaluationAlert,
  EvaluationCycle,
  EvaluationScoreRow,
  listAlerts,
  listEmployees,
  listEvaluationCycles,
  listScores,
  upsertPotential,
} from '../api/evaluation';

const formatScore = (value: number | null | undefined) => (value === null || value === undefined ? '-' : value.toFixed(2));

const EvaluationScoringPage: React.FC = () => {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [cycleId, setCycleId] = useState<number | null>(null);
  const [scores, setScores] = useState<EvaluationScoreRow[]>([]);
  const [alerts, setAlerts] = useState<EvaluationAlert[]>([]);
  const [summary, setSummary] = useState<{ processed: number; incomplete: number; alerts_generated: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [managerInput, setManagerInput] = useState({
    employee_id: '',
    manager_score: 80,
    potential_comment: '',
  });

  const loadCycleData = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const [scoreRows, alertRows] = await Promise.all([listScores(id), listAlerts(id)]);
      setScores(scoreRows);
      setAlerts(alertRows);
    } catch {
      setError('Falha ao carregar a lista parcial. Execute o cálculo depois de importar a avaliação 360.');
    } finally {
      setLoading(false);
    }
  };

  const loadBase = async () => {
    const [cycleRows, employeeRows] = await Promise.all([listEvaluationCycles(), listEmployees()]);
    setCycles(cycleRows);
    setEmployees(employeeRows);
    const selectedCycle = cycleId || cycleRows[0]?.id || null;
    setCycleId(selectedCycle);
    if (selectedCycle) {
      await loadCycleData(selectedCycle);
    } else {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBase().catch(() => {
      setError('Falha ao carregar ciclos e colaboradores.');
      setLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const employeeOptions = useMemo(
    () => employees
      .filter((employee) => employee.active && employee.position?.toLowerCase() !== 'gestor')
      .map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>),
    [employees]
  );

  const sortedScores = useMemo(() => {
    return [...scores].sort((left, right) => {
      const rightValue = right.preliminary_final_score ?? right.behavior_score ?? -1;
      const leftValue = left.preliminary_final_score ?? left.behavior_score ?? -1;
      return rightValue - leftValue;
    });
  }, [scores]);

  const runCalculation = async () => {
    if (!cycleId) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const result = await calculateScores(cycleId);
      setSummary(result);
      await loadCycleData(cycleId);
      setMessage('Lista parcial recalculada. Se faltarem RPM/IHPE ou nota do gestor, o colaborador aparece com score parcial.');
    } catch {
      setError('Não foi possível executar o cálculo.');
    } finally {
      setSaving(false);
    }
  };

  const saveManagerEvaluation = async () => {
    if (!cycleId || !managerInput.employee_id) return;
    setSaving(true);
    setMessage(null);
      setError(null);
    try {
      const employeeId = Number(managerInput.employee_id);
      await upsertPotential(cycleId, employeeId, {
        score: Number(managerInput.manager_score),
        comment: managerInput.potential_comment || null,
      });
      const result = await calculateScores(cycleId);
      setSummary(result);
      await loadCycleData(cycleId);
      setMessage('Avaliação do gestor salva e lista recalculada.');
    } catch {
      setError('Não foi possível salvar a avaliação do gestor.');
    } finally {
      setSaving(false);
    }
  };

  const handleCycleChange = async (id: number) => {
    setCycleId(id);
    setSummary(null);
    setMessage(null);
    await loadCycleData(id);
  };

  return (
    <AppShell>
      <Topbar
        title="Avaliação - Lista Parcial e Gestor"
        subtitle="Fluxo simplificado: importe a avaliação 360, importe RPM/IHPE, gere a lista parcial e depois informe a nota do gestor."
        action={<button disabled={!cycleId || saving} onClick={runCalculation} className="rounded-md bg-primary px-4 py-2 text-sm font-bold text-white disabled:opacity-50">Gerar lista parcial</button>}
      />

      {message && <StateBlock tone="empty" title="Sucesso" description={message} />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Passo 1</p>
          <h3 className="mt-1 text-lg font-black text-slate-900">Importar avaliação 360</h3>
          <p className="mt-2 text-sm text-slate-500">Carregue o CSV/XLS do Google Forms e confirme a importação antes de gerar a lista parcial.</p>
          <Link to="/evaluation/imports" className="mt-4 inline-flex rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-700">Ir para CSV e IA</Link>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Passo 2</p>
          <h3 className="mt-1 text-lg font-black text-slate-900">Gerar lista parcial</h3>
          <p className="mt-2 text-sm text-slate-500">A lista parcial ordena por score final quando completo ou por comportamento 360 quando ainda faltam dados do gestor.</p>
          <button disabled={!cycleId || saving} onClick={runCalculation} className="mt-4 rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Gerar lista parcial</button>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wide text-blue-600">Passo 3</p>
          <h3 className="mt-1 text-lg font-black text-slate-900">Nota do gestor</h3>
          <p className="mt-2 text-sm text-slate-500">Informe uma nota única da chefia. Ela tem o mesmo peso da avaliação 360 no score final.</p>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_2fr]">
          <label className="flex flex-col gap-2 text-sm font-semibold text-slate-700">
            Ciclo avaliativo
            <select className="rounded-lg border border-slate-200 px-3 py-2" value={cycleId ?? ''} onChange={(event) => handleCycleChange(Number(event.target.value))}>
              {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
            </select>
          </label>

          {summary && (
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-slate-50 p-3 text-sm">Processados<br /><strong>{summary.processed}</strong></div>
              <div className="rounded-lg bg-slate-50 p-3 text-sm">Incompletos<br /><strong>{summary.incomplete}</strong></div>
              <div className="rounded-lg bg-slate-50 p-3 text-sm">Alertas<br /><strong>{summary.alerts_generated}</strong></div>
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4">
          <h3 className="text-lg font-black text-slate-900">Avaliação rápida do gestor</h3>
          <p className="text-sm text-slate-500">Use esta área após a lista parcial 360 para informar a nota da chefia. Fórmula: 360 45%, gestor 45%, RPM/IHPE 10%.</p>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[2fr_1fr_140px]">
          <select className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={managerInput.employee_id} onChange={(event) => setManagerInput((current) => ({ ...current, employee_id: event.target.value }))}>
            <option value="">Selecionar colaborador</option>
            {employeeOptions}
          </select>
          <input type="number" min={0} max={100} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" value={managerInput.manager_score} onChange={(event) => setManagerInput((current) => ({ ...current, manager_score: Number(event.target.value) }))} placeholder="Nota do gestor" />
          <button disabled={!managerInput.employee_id || saving} onClick={saveManagerEvaluation} className="rounded-lg bg-primary px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Salvar</button>
        </div>

        <input className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={managerInput.potential_comment} onChange={(event) => setManagerInput((current) => ({ ...current, potential_comment: event.target.value }))} placeholder="Comentário opcional do gestor sobre desempenho, responsabilidade, entregas ou contexto" />
      </section>

      {loading && <StateBlock tone="loading" title="Carregando lista parcial" />}

      {!loading && !error && (
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-5">
            <h3 className="text-lg font-black text-slate-900">Lista parcial ordenada</h3>
            <p className="text-sm text-slate-500">Enquanto faltar RPM/IHPE ou nota do gestor, use a avaliação 360 como referência parcial. A decisão final continua na calibração.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 text-left">#</th>
                  <th className="px-4 py-3 text-left">Colaborador</th>
                  <th className="px-4 py-3 text-left">360</th>
                  <th className="px-4 py-3 text-left">RPM/IHPE</th>
                  <th className="px-4 py-3 text-left">Gestor</th>
                  <th className="px-4 py-3 text-left">Score final</th>
                  <th className="px-4 py-3 text-left">Categoria</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {sortedScores.map((row, index) => {
                  const complete = row.preliminary_final_score !== null && row.preliminary_final_score !== undefined;
                  return (
                    <tr key={row.employee_id} className="border-t border-slate-100">
                      <td className="px-4 py-3 font-bold text-slate-500">{index + 1}</td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-800">{row.employee_name}</div>
                        <div className="text-xs text-slate-500">{row.department || '-'} · {row.position || '-'}</div>
                      </td>
                      <td className="px-4 py-3 font-semibold">{formatScore(row.behavior_score)}</td>
                      <td className="px-4 py-3">{formatScore(row.performance_score)}</td>
                      <td className="px-4 py-3">{formatScore(row.potential_score)}</td>
                      <td className="px-4 py-3 font-bold text-slate-900">{formatScore(row.preliminary_final_score)}</td>
                      <td className="px-4 py-3">{row.suggested_category || '-'}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-3 py-1 text-xs font-bold ${complete ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                          {complete ? 'Completo' : 'Parcial 360'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {alerts.length > 0 && (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="mb-2 text-sm font-bold text-amber-900">Alertas do ciclo</h3>
          <div className="space-y-2">
            {alerts.slice(0, 8).map((alert) => (
              <div key={alert.id} className="text-sm text-amber-900">{alert.employee_name}: {alert.message}</div>
            ))}
          </div>
        </section>
      )}
    </AppShell>
  );
};

export default EvaluationScoringPage;
