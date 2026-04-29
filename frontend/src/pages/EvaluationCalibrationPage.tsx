import React, { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import {
  calibrateEmployee,
  EvaluationCategory,
  EvaluationCycle,
  EvaluationScoreRow,
  getCalibration,
  listEvaluationCycles,
} from '../api/evaluation';

const categories: EvaluationCategory[] = ['DESTAQUE', 'MUITO_BOM', 'BOM', 'EM_DESENVOLVIMENTO', 'ATENCAO'];

const EvaluationCalibrationPage: React.FC = () => {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [cycleId, setCycleId] = useState<number | null>(null);
  const [rows, setRows] = useState<EvaluationScoreRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCycles = async () => {
    const data = await listEvaluationCycles();
    setCycles(data);
    if (data.length && !cycleId) setCycleId(data[0].id);
  };

  const load = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      setRows(await getCalibration(id));
    } catch {
      setError('Falha ao carregar calibração.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCycles().catch(() => setError('Falha ao carregar ciclos.'));
  }, []);

  useEffect(() => {
    if (cycleId) load(cycleId);
  }, [cycleId]);

  const saveRow = async (row: EvaluationScoreRow) => {
    if (!cycleId || !row.final_category) return;
    try {
      const updated = await calibrateEmployee(cycleId, row.employee_id, {
        final_category: row.final_category,
        calibration_justification: row.calibration_justification || null,
      });
      setRows((prev) => prev.map((item) => item.employee_id === updated.employee_id ? updated : item));
    } catch {
      setError('Justificativa obrigatória quando a categoria final difere da sugerida.');
    }
  };

  return (
    <AppShell>
      <Topbar title="Avaliação - Calibração" subtitle="Revise a categoria sugerida e registre a justificativa gerencial quando houver ajuste." />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="mr-2 text-sm font-semibold text-slate-700">Ciclo</label>
        <select className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleId ?? ''} onChange={(e) => setCycleId(Number(e.target.value))}>
          {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
        </select>
      </section>

      {loading && <StateBlock tone="loading" title="Carregando calibração" />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 text-left">Colaborador</th>
                <th className="px-4 py-3 text-left">RPM/IHPE</th>
                <th className="px-4 py-3 text-left">360</th>
                <th className="px-4 py-3 text-left">Gestor</th>
                <th className="px-4 py-3 text-left">Final</th>
                <th className="px-4 py-3 text-left">Sugerida</th>
                <th className="px-4 py-3 text-left">Final</th>
                <th className="px-4 py-3 text-left">Justificativa</th>
                <th className="px-4 py-3 text-left">Alertas</th>
                <th className="px-4 py-3 text-left">Ação</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.employee_id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-800">{row.employee_name}</div>
                    <div className="text-xs text-slate-500">{row.department || '-'} - {row.position || '-'}</div>
                  </td>
                  <td className="px-4 py-3">{row.performance_score ?? '-'}</td>
                  <td className="px-4 py-3">{row.behavior_score ?? '-'}</td>
                  <td className="px-4 py-3">{row.potential_score ?? '-'}</td>
                  <td className="px-4 py-3 font-semibold">{row.preliminary_final_score ?? '-'}</td>
                  <td className="px-4 py-3">{row.suggested_category || '-'}</td>
                  <td className="px-4 py-3">
                    <select
                      className="rounded-md border border-slate-200 px-2 py-1"
                      value={row.final_category || row.suggested_category || 'BOM'}
                      onChange={(e) => {
                        const value = e.target.value as EvaluationCategory;
                        setRows((prev) => {
                          const copy = [...prev];
                          copy[index] = { ...copy[index], final_category: value };
                          return copy;
                        });
                      }}
                    >
                      {categories.map((category) => <option key={category} value={category}>{category}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      className="min-w-[260px] rounded-md border border-slate-200 px-3 py-2"
                      value={row.calibration_justification || ''}
                      onChange={(e) => {
                        const value = e.target.value;
                        setRows((prev) => {
                          const copy = [...prev];
                          copy[index] = { ...copy[index], calibration_justification: value };
                          return copy;
                        });
                      }}
                    />
                  </td>
                  <td className="px-4 py-3 text-xs text-amber-700">{row.alerts.length}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => saveRow(row)} className="rounded-md bg-primary px-3 py-2 text-xs font-bold text-white">Salvar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
};

export default EvaluationCalibrationPage;
