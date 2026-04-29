import React, { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Topbar } from '../components/Topbar';
import { StateBlock } from '../components/StateBlock';
import { EvaluationCycle, EvaluationScoreRow, exportFinalListCsv, getFinalList, getFinalReportHtml, listEvaluationCycles } from '../api/evaluation';

const formatScore = (value: number | null | undefined) => (value === null || value === undefined ? '-' : value.toFixed(2));

const EvaluationFinalListPage: React.FC = () => {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [cycleId, setCycleId] = useState<number | null>(null);
  const [rows, setRows] = useState<EvaluationScoreRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [department, setDepartment] = useState('');
  const [category, setCategory] = useState('');

  const loadCycles = async () => {
    const data = await listEvaluationCycles();
    setCycles(data);
    if (data.length && !cycleId) setCycleId(data[0].id);
  };

  const load = async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      setRows(await getFinalList(id, { department: department || undefined, category: category || undefined }));
    } catch {
      setError('Falha ao carregar lista final.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCycles().catch(() => setError('Falha ao carregar ciclos.'));
  }, []);

  useEffect(() => {
    if (cycleId) load(cycleId);
  }, [cycleId, department, category]);

  const departments = useMemo(() => Array.from(new Set(rows.map((row) => row.department).filter(Boolean))) as string[], [rows]);
  const categories = useMemo(() => Array.from(new Set(rows.map((row) => row.final_category).filter(Boolean))) as string[], [rows]);

  const downloadCsv = async () => {
    if (!cycleId) return;
    const blob = await exportFinalListCsv(cycleId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lista_final_ciclo_${cycleId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadHtml = async () => {
    if (!cycleId) return;
    const blob = await getFinalReportHtml(cycleId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `relatorio_final_ciclo_${cycleId}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell>
      <Topbar
        title="Avaliação - Lista Final"
        subtitle="Lista ordenada para apoio à decisão gerencial, com 360, nota do gestor e RPM/IHPE."
        action={(
          <div className="flex gap-2">
            <button onClick={downloadHtml} className="rounded-md border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700">Baixar relatório HTML</button>
            <button onClick={downloadCsv} className="rounded-md bg-primary px-4 py-2 text-sm font-bold text-white">Exportar CSV</button>
          </div>
        )}
      />

      <section className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-950">
        <h3 className="font-black">Metodologia aplicada</h3>
        <p className="mt-1">A avaliação 360 desconsidera autoavaliação. A pontuação final usa 360 com peso 45%, nota do gestor com peso 45% e RPM/IHPE com peso 10%. Enquanto RPM/IHPE ou nota do gestor não forem preenchidos, a ordenação usa a média 360 como lista parcial.</p>
        <p className="mt-1">Critérios de desempate recomendados: comprometimento/responsabilidade, produtividade e entregas de valor. A decisão final deve ser registrada na calibração com justificativa.</p>
      </section>

      <section className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="text-sm font-semibold text-slate-700">Ciclo</label>
        <select className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={cycleId ?? ''} onChange={(e) => setCycleId(Number(e.target.value))}>
          {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
        </select>
        <label className="text-sm font-semibold text-slate-700">Área</label>
        <select className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">Todas</option>
          {departments.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <label className="text-sm font-semibold text-slate-700">Categoria</label>
        <select className="rounded-md border border-slate-200 px-3 py-2 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Todas</option>
          {categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </section>

      {loading && <StateBlock tone="loading" title="Carregando lista final" />}
      {error && <StateBlock tone="error" title="Erro" description={error} />}

      {!loading && !error && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3 text-left">Pos.</th>
                <th className="px-4 py-3 text-left">Colaborador</th>
                <th className="px-4 py-3 text-left">Área</th>
                <th className="px-4 py-3 text-left">Cargo</th>
                <th className="px-4 py-3 text-left">360</th>
                <th className="px-4 py-3 text-left">RPM/IHPE</th>
                <th className="px-4 py-3 text-left">Gestor</th>
                <th className="px-4 py-3 text-left">Score final</th>
                <th className="px-4 py-3 text-left">Final</th>
                <th className="px-4 py-3 text-left">Justificativa</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.employee_id} className="border-t border-slate-100">
                  <td className="px-4 py-3 font-bold text-slate-700">{index + 1}</td>
                  <td className="px-4 py-3 font-semibold text-slate-800">{row.employee_name}</td>
                  <td className="px-4 py-3 text-slate-600">{row.department || '-'}</td>
                  <td className="px-4 py-3 text-slate-600">{row.position || '-'}</td>
                  <td className="px-4 py-3 font-semibold text-slate-700">{formatScore(row.behavior_score)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatScore(row.performance_score)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatScore(row.potential_score)}</td>
                  <td className="px-4 py-3 font-semibold text-slate-700">{formatScore(row.preliminary_final_score)}</td>
                  <td className="px-4 py-3 text-slate-600">{row.final_category || row.suggested_category || '-'}</td>
                  <td className="px-4 py-3 text-slate-600">{row.calibration_justification || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
};

export default EvaluationFinalListPage;
