import { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import {
  EvaluationCycle,
  PreliminaryReport,
  getPreliminaryReport,
  listEvaluationCycles,
  listReviews,
  listScores,
  runCycleAiAnalysis,
  runEmployeeAiAnalysis,
} from '../api/evaluation';

const fmt = (value: number | null | undefined) => (value === null || value === undefined ? '-' : value.toFixed(2));

const printReport = () => {
  window.print();
};

type EmployeeOption = {
  employee_id: number;
  employee_name: string;
};

export default function EvaluationAiReportPage() {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [cycleId, setCycleId] = useState<number | null>(null);
  const [employeeOptions, setEmployeeOptions] = useState<EmployeeOption[]>([]);
  const [employeeId, setEmployeeId] = useState<number | null>(null);
  const [report, setReport] = useState<PreliminaryReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const loadCycles = async () => {
    const loadedCycles = await listEvaluationCycles();
    setCycles(loadedCycles);
    const currentCycleId = cycleId || loadedCycles[0]?.id || null;
    setCycleId(currentCycleId);
    if (currentCycleId) {
      await loadScores(currentCycleId);
    }
  };

  const loadScores = async (id: number) => {
    const [loadedScores, loadedReviews] = await Promise.all([
      listScores(id).catch(() => []),
      listReviews(id).catch(() => []),
    ]);
    const byEmployee = new Map<number, EmployeeOption>();
    loadedScores.forEach((score) => {
      byEmployee.set(score.employee_id, {
        employee_id: score.employee_id,
        employee_name: score.employee_name,
      });
    });
    loadedReviews.forEach((review) => {
      if (review.evaluated_id) {
        byEmployee.set(review.evaluated_id, {
          employee_id: review.evaluated_id,
          employee_name: review.evaluated_name || `Colaborador ${review.evaluated_id}`,
        });
      }
    });
    const options = Array.from(byEmployee.values()).sort((left, right) => left.employee_name.localeCompare(right.employee_name));
    setEmployeeOptions(options);
    const currentEmployeeId = employeeId || options[0]?.employee_id || null;
    setEmployeeId(currentEmployeeId);
    if (currentEmployeeId) {
      await loadReport(id, currentEmployeeId);
    } else {
      setReport(null);
    }
  };

  const loadReport = async (currentCycleId: number, currentEmployeeId: number) => {
    setLoading(true);
    setMessage('');
    try {
      const loadedReport = await getPreliminaryReport(currentCycleId, currentEmployeeId);
      setReport(loadedReport);
    } catch {
      setReport(null);
      setMessage('Não foi possível carregar o relatório. Execute o cálculo e/ou a análise IA para este colaborador.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCycles().catch(() => setMessage('Não foi possível carregar ciclos.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCycleChange = async (id: number) => {
    setCycleId(id);
    setEmployeeId(null);
    setReport(null);
    await loadScores(id);
  };

  const handleEmployeeChange = async (id: number) => {
    setEmployeeId(id);
    if (cycleId) {
      await loadReport(cycleId, id);
    }
  };

  const handleRunCycleAi = async () => {
    if (!cycleId) return;
    setLoading(true);
    try {
      const result = await runCycleAiAnalysis(cycleId);
      setMessage(`Análise IA processada para ${result.length} colaborador(es).`);
      await loadScores(cycleId);
    } catch {
      setMessage('Erro ao executar análise IA do ciclo.');
    } finally {
      setLoading(false);
    }
  };

  const handleRunEmployeeAi = async () => {
    if (!cycleId || !employeeId) return;
    setLoading(true);
    try {
      await runEmployeeAiAnalysis(cycleId, employeeId);
      await loadReport(cycleId, employeeId);
      setMessage('Análise IA do colaborador atualizada.');
    } catch {
      setMessage('Erro ao executar análise IA do colaborador.');
    } finally {
      setLoading(false);
    }
  };

  const downloadHtmlReport = () => {
    if (!report) return;
    const html = document.getElementById('ai-report-printable')?.outerHTML || '';
    const blob = new Blob([
      `<!doctype html><html><head><meta charset="utf-8"><title>Relatório IA</title><style>body{font-family:Arial,sans-serif;padding:24px;color:#0f172a}h1,h2{margin:0 0 10px}section{border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.card{background:#f8fafc;border-radius:8px;padding:10px}li{margin:4px 0}</style></head><body>${html}</body></html>`,
    ], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `relatorio-ia-${report.employee.name}.html`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell>
    <div className="flex min-h-0 flex-col gap-6">
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #ai-report-printable, #ai-report-printable * { visibility: visible; }
          #ai-report-printable { position: absolute; left: 0; top: 0; width: 100%; padding: 24px; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="no-print">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">Avaliação final</p>
        <h1 className="text-2xl font-bold text-slate-900">Relatório IA e análise preliminar</h1>
        <p className="mt-1 text-sm text-slate-500">
          Visualize o resumo qualitativo da IA, scores calculados, alertas e comentários 360 por colaborador.
        </p>
      </div>

      {message && <div className="no-print rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-800">{message}</div>}

      <section className="no-print grid gap-4 rounded-2xl bg-white p-5 shadow-soft lg:grid-cols-[1fr_1fr_auto_auto_auto]">
        <label className="flex flex-col gap-2 text-sm font-semibold text-slate-700">
          Ciclo
          <select className="rounded-xl border border-slate-200 px-3 py-2" value={cycleId || ''} onChange={(event) => handleCycleChange(Number(event.target.value))}>
            {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
          </select>
        </label>

        <label className="flex flex-col gap-2 text-sm font-semibold text-slate-700">
          Colaborador
          <select className="rounded-xl border border-slate-200 px-3 py-2" value={employeeId || ''} onChange={(event) => handleEmployeeChange(Number(event.target.value))}>
            <option value="">Selecione</option>
            {employeeOptions.map((employee) => <option key={employee.employee_id} value={employee.employee_id}>{employee.employee_name}</option>)}
          </select>
        </label>

        <button disabled={!cycleId || loading} onClick={handleRunCycleAi} className="self-end rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">
          Rodar IA ciclo
        </button>
        <button disabled={!employeeId || loading} onClick={handleRunEmployeeAi} className="self-end rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">
          Rodar IA pessoa
        </button>
        <button disabled={!report} onClick={printReport} className="self-end rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
          Imprimir/PDF
        </button>
      </section>

      <div className="no-print flex justify-end">
        <button disabled={!report} onClick={downloadHtmlReport} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">
          Baixar HTML
        </button>
      </div>

      {loading && <div className="rounded-xl bg-white p-5 text-sm text-slate-500 shadow-soft">Carregando relatório...</div>}

      {!loading && report && (
        <div id="ai-report-printable" className="rounded-2xl bg-white p-6 shadow-soft">
          <header className="border-b border-slate-200 pb-5">
            <p className="text-sm font-bold uppercase tracking-wide text-blue-600">Relatório preliminar de avaliação</p>
            <h2 className="mt-1 text-2xl font-black text-slate-900">{report.employee.name}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {report.employee.department || 'Sem área'} · {report.employee.position || 'Sem cargo'} · {report.employee.email}
            </p>
          </header>

          <section className="mt-5 grid gap-3 md:grid-cols-4">
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">RPM/IHPE</p>
              <p className="mt-1 text-xl font-black text-slate-900">{fmt(report.score?.performance_score)}</p>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">360</p>
              <p className="mt-1 text-xl font-black text-slate-900">{fmt(report.score?.behavior_score)}</p>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">Gestor</p>
              <p className="mt-1 text-xl font-black text-slate-900">{fmt(report.score?.potential_score)}</p>
            </div>
            <div className="rounded-xl bg-blue-50 p-4">
              <p className="text-xs font-bold uppercase text-blue-600">Score final</p>
              <p className="mt-1 text-xl font-black text-blue-900">{fmt(report.score?.preliminary_final_score)}</p>
            </div>
          </section>

          <section className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">Categoria sugerida</p>
              <p className="mt-1 font-black text-slate-900">{report.score?.suggested_category || '-'}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">Categoria final</p>
              <p className="mt-1 font-black text-slate-900">{report.score?.final_category || '-'}</p>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs font-bold uppercase text-slate-500">9-box</p>
              <p className="mt-1 font-black text-slate-900">{report.score?.nine_box_position || '-'}</p>
            </div>
          </section>

          <section className="mt-5 rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between gap-4">
              <h3 className="text-lg font-black text-slate-900">Análise qualitativa da IA</h3>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{report.ai_analysis?.status || 'SEM ANÁLISE'}</span>
            </div>
            {report.ai_analysis ? (
              <div className="mt-4 space-y-4">
                {report.ai_analysis.error_message && (
                  <p className={`rounded-lg p-3 text-sm ${
                    report.ai_analysis.status === 'ERROR'
                      ? 'bg-red-50 text-red-700'
                      : 'bg-blue-50 text-blue-800'
                  }`}>
                    {report.ai_analysis.error_message}
                  </p>
                )}
                <div>
                  <p className="text-xs font-bold uppercase text-slate-500">Resumo</p>
                  <p className="mt-1 text-sm leading-6 text-slate-700">{report.ai_analysis.summary || '-'}</p>
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <ListBlock title="Pontos fortes" items={report.ai_analysis.strengths_json || []} />
                  <ListBlock title="Pontos de atenção" items={report.ai_analysis.attention_points_json || []} />
                  <ListBlock title="Temas recorrentes" items={report.ai_analysis.recurring_themes_json || []} />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase text-slate-500">Feedback sugerido</p>
                  <p className="mt-1 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">{report.ai_analysis.suggested_feedback || '-'}</p>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500">Ainda não existe análise IA para este colaborador.</p>
            )}
          </section>

          <section className="mt-5 rounded-xl border border-slate-200 p-5">
            <h3 className="text-lg font-black text-slate-900">Alertas do sistema</h3>
            {report.alerts.length ? (
              <div className="mt-3 space-y-2">
                {report.alerts.map((alert) => (
                  <div key={alert.id} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                    <strong>{alert.severity}</strong> · {alert.message}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Nenhum alerta aberto para este colaborador.</p>
            )}
          </section>

          <section className="mt-5 rounded-xl border border-slate-200 p-5">
            <h3 className="text-lg font-black text-slate-900">Comentários 360</h3>
            <div className="mt-3 space-y-3">
              {report.reviews.map((review) => (
                <div key={review.id} className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs font-bold uppercase text-slate-500">{review.relation_type} · nota {fmt(review.general_score || review.score)}</p>
                  <p className="mt-2 text-sm text-slate-700">{review.general_comment || review.comment || review.strengths_comment || review.improvement_comment || '-'}</p>
                </div>
              ))}
            </div>
          </section>

          <footer className="mt-6 border-t border-slate-200 pt-4 text-xs text-slate-500">
            A IA apoia a análise qualitativa e não decide nota, categoria, promoção ou resultado final. A decisão final é da gestão e deve ser calibrada com auditoria.
          </footer>
        </div>
      )}

      {!loading && !report && (
        <div className="rounded-xl bg-white p-6 text-sm text-slate-500 shadow-soft">
          Selecione um ciclo e um colaborador para visualizar o relatório. Se não aparecer colaborador, confirme a importação do CSV ou registre avaliações 360 no ciclo.
        </div>
      )}
    </div>
    </AppShell>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      {items.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Sem itens identificados.</p>
      )}
    </div>
  );
}
