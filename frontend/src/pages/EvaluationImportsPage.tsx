import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../components/AppShell';
import {
  confirmImport,
  EvaluationCycle,
  EvaluationImport,
  ImportValidationResult,
  listEvaluationCycles,
  listEvaluationImports,
  mapImportColumns,
  runCycleAiAnalysis,
  uploadIhpeFile,
  uploadRhFile,
  uploadRpmFile,
  uploadEvaluationCsv,
  validateImport,
} from '../api/evaluation';

const mappingFields = [
  ['evaluated_email', 'E-mail do avaliado (opcional)'],
  ['evaluated_name', 'Nome do avaliado'],
  ['evaluator_email', 'E-mail do avaliador'],
  ['evaluator_name', 'Nome do avaliador'],
  ['relation_type', 'Tipo de relação (opcional)'],
  ['general_score', 'Nota geral'],
  ['communication_score', 'Comunicação'],
  ['teamwork_score', 'Trabalho em equipe'],
  ['commitment_score', 'Comprometimento'],
  ['autonomy_score', 'Autonomia'],
  ['quality_score', 'Qualidade'],
  ['problem_solving_score', 'Resolução de problemas'],
  ['strengths_comment', 'Pontos fortes'],
  ['improvement_comment', 'Pontos de melhoria'],
  ['general_comment', 'Comentário geral'],
  ['submitted_at', 'Data de envio'],
];

const repairMojibake = (value: string) => {
  if (!/[ÃÂ]/.test(value)) return value;
  const bytes = Array.from(value).map((char) => char.charCodeAt(0));
  if (bytes.some((code) => code > 255)) return value;
  try {
    return new TextDecoder('utf-8').decode(new Uint8Array(bytes));
  } catch {
    return value;
  }
};

const normalizeHeader = (value: string) => repairMojibake(value)
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, ' ')
  .trim();

const findHeader = (headers: string[], candidates: string[]) => {
  const normalizedCandidates = candidates.map(normalizeHeader);
  return headers.find((header) => {
    const normalized = normalizeHeader(header);
    return normalizedCandidates.some((candidate) => normalized === candidate || normalized.includes(candidate));
  }) || '';
};

const inferMapping = (headers: string[]) => {
  const longComment = findHeader(headers, ['aqui descreva', 'desenvolver mais', 'campo unico', 'consideracoes finais', 'comentario geral']);

  return {
    evaluated_email: findHeader(headers, ['email do avaliado', 'e mail do avaliado']),
    evaluated_name: findHeader(headers, ['avaliado', 'nome do avaliado', 'colaborador avaliado']),
    evaluator_email: findHeader(headers, ['email', 'e mail', 'email do avaliador', 'e mail do avaliador']),
    evaluator_name: findHeader(headers, ['avaliador', 'nome do avaliador']),
    relation_type: findHeader(headers, ['tipo de relacao', 'relacao', 'perfil do avaliador']),
    general_score: findHeader(headers, ['nota geral', 'avaliacao geral', 'score geral']),
    communication_score: findHeader(headers, ['comunicacao', 'comunicação']),
    teamwork_score: findHeader(headers, ['trabalho em equipe', 'equipe']),
    commitment_score: findHeader(headers, ['comprometimento e dedicacao', 'comprometimento', 'dedicacao']),
    autonomy_score: findHeader(headers, ['autonomia', 'autodesenvolvimento profissional', 'autodesenvolvimento', 'capacitacao para funcao', 'capacitacao']),
    quality_score: findHeader(headers, ['qualidade do trabalho', 'qualidade']),
    problem_solving_score: findHeader(headers, ['orientacao para resultados', 'resultados', 'criatividade e inovacao', 'produtividade', 'cumprimento de prazos metas']),
    strengths_comment: longComment,
    improvement_comment: longComment,
    general_comment: longComment,
    submitted_at: findHeader(headers, ['hora de conclusao', 'data de envio', 'submitted at', 'conclusao']),
  };
};

export default function EvaluationImportsPage() {
  const [cycles, setCycles] = useState<EvaluationCycle[]>([]);
  const [cycleId, setCycleId] = useState<number | null>(null);
  const [imports, setImports] = useState<EvaluationImport[]>([]);
  const [selectedImportId, setSelectedImportId] = useState<number | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<ImportValidationResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [rpmFile, setRpmFile] = useState<File | null>(null);
  const [ihpeFile, setIhpeFile] = useState<File | null>(null);
  const [rhFile, setRhFile] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const selectedImport = useMemo(
    () => imports.find((item) => item.id === selectedImportId) || imports[0],
    [imports, selectedImportId]
  );
  const hasImportedReviews = imports.some((item) => item.status === 'IMPORTED');
  const canConfirmImport = Boolean(
    selectedImport
    && selectedImport.status !== 'IMPORTED'
    && selectedImport.valid_rows > 0
  );

  const load = async () => {
    const loadedCycles = await listEvaluationCycles();
    setCycles(loadedCycles);
    const currentCycleId = cycleId || loadedCycles[0]?.id || null;
    setCycleId(currentCycleId);
    if (currentCycleId) {
      const loadedImports = await listEvaluationImports(currentCycleId);
      setImports(loadedImports);
      if (!selectedImportId && loadedImports[0]) {
        setSelectedImportId(loadedImports[0].id);
        setMapping(loadedImports[0].column_mapping_json || inferMapping(loadedImports[0].headers || []));
      }
    }
  };

  useEffect(() => {
    load().catch(() => setMessage('Não foi possível carregar os dados de importação.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedImport) {
      setMapping(selectedImport.column_mapping_json || inferMapping(selectedImport.headers || []));
      setValidation(null);
    }
  }, [selectedImport?.id]);

  const refreshImports = async (currentCycleId = cycleId) => {
    if (!currentCycleId) return [];
    const loadedImports = await listEvaluationImports(currentCycleId);
    setImports(loadedImports);
    if (loadedImports[0] && !loadedImports.some((item) => item.id === selectedImportId)) {
      setSelectedImportId(loadedImports[0].id);
    }
    return loadedImports;
  };

  const handleCycleChange = async (id: number) => {
    setCycleId(id);
    setSelectedImportId(null);
    setValidation(null);
    const loadedImports = await listEvaluationImports(id);
    setImports(loadedImports);
    setSelectedImportId(loadedImports[0]?.id || null);
    setMapping(loadedImports[0]?.column_mapping_json || inferMapping(loadedImports[0]?.headers || []));
  };

  const handleUpload = async () => {
    if (!cycleId || !file) return;
    setLoading(true);
    setMessage('');
    try {
      const created = await uploadEvaluationCsv(cycleId, file);
      setSelectedImportId(created.id);
      setMapping(inferMapping(created.headers || []));
      await refreshImports(cycleId);
      setMessage(`Arquivo enviado: ${created.total_rows} linhas lidas. O mapeamento automático foi preenchido; revise e clique em Salvar mapa.`);
    } catch {
      setMessage('Erro ao enviar arquivo.');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoMap = () => {
    if (!selectedImport) return;
    setMapping(inferMapping(selectedImport.headers || []));
    setMessage('Mapeamento automático aplicado. Revise os campos antes de validar.');
  };

  const handleMap = async () => {
    if (!cycleId || !selectedImport) return;
    setLoading(true);
    try {
      await mapImportColumns(cycleId, selectedImport.id, mapping);
      await refreshImports();
      setMessage('Mapeamento salvo. Agora clique em Validar.');
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Erro no mapeamento. Verifique nome do avaliado, e-mail/nome do avaliador e pelo menos uma nota.');
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!cycleId || !selectedImport) return;
    setLoading(true);
    try {
      const result = await validateImport(cycleId, selectedImport.id);
      setValidation(result);
      await refreshImports();
      setMessage(`Validação concluída: ${result.valid_rows} válidas, ${result.invalid_rows} inválidas.`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Erro ao validar importação.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!cycleId || !selectedImport) return;
    setLoading(true);
    try {
      const result = await confirmImport(cycleId, selectedImport.id);
      await refreshImports();
      setMessage(`Importação confirmada: ${result.created_reviews} avaliações 360 criadas.`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Erro ao confirmar importação.');
    } finally {
      setLoading(false);
    }
  };

  const handleAi = async () => {
    if (!cycleId) return;
    if (!hasImportedReviews) {
      setMessage('Antes de rodar a IA, confirme uma importação validada. Validar apenas confere as linhas; Confirmar cria as avaliações 360 no ciclo.');
      return;
    }
    setLoading(true);
    try {
      setMessage('Análise IA em execução. Pode levar alguns minutos em ciclos com muitos colaboradores.');
      const result = await runCycleAiAnalysis(cycleId);
      setMessage(`Análise IA executada para ${result.length} colaborador(es).`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Erro ao executar análise IA.');
    } finally {
      setLoading(false);
    }
  };

  const handleOperationalUpload = async (kind: 'rpm' | 'ihpe' | 'rh') => {
    if (!cycleId) return;
    const selectedFile = kind === 'rpm' ? rpmFile : kind === 'ihpe' ? ihpeFile : rhFile;
    if (!selectedFile) return;
    setLoading(true);
    try {
      const result = kind === 'rpm'
        ? await uploadRpmFile(cycleId, selectedFile)
        : kind === 'ihpe'
          ? await uploadIhpeFile(cycleId, selectedFile)
          : await uploadRhFile(cycleId, selectedFile);
      const label = kind === 'rpm' ? 'RPM' : kind === 'ihpe' ? 'IHPE' : 'RH';
      setMessage(`${label} importado: ${result.imported_rows} linhas lidas, ${result.updated_indicators || result.updated_rh_records} registro(s) atualizados.`);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Erro ao importar planilha operacional.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="flex min-h-0 flex-col gap-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-600">Avaliação final</p>
          <h1 className="text-2xl font-bold text-slate-900">Importação CSV/Excel e IA qualitativa</h1>
          <p className="mt-1 text-sm text-slate-500">
            Importe respostas do Google Forms em CSV, XLSX ou XLS, mapeie colunas, valide linhas, crie avaliações 360 e gere análise qualitativa sem alterar notas.
          </p>
        </div>

        {message && <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-800">{message}</div>}

        <section className="grid gap-4 rounded-2xl bg-white p-5 shadow-soft lg:grid-cols-3">
          <label className="flex flex-col gap-2 text-sm font-semibold text-slate-700">
            Ciclo avaliativo
            <select
              className="rounded-xl border border-slate-200 px-3 py-2"
              value={cycleId || ''}
              onChange={(event) => handleCycleChange(Number(event.target.value))}
            >
              {cycles.map((cycle) => (
                <option key={cycle.id} value={cycle.id}>{cycle.name}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 text-sm font-semibold text-slate-700">
            CSV/Excel Google Forms
            <input className="rounded-xl border border-slate-200 px-3 py-2" type="file" accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>

          <div className="flex items-end gap-2">
            <button disabled={!file || !cycleId || loading} onClick={handleUpload} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
              Enviar arquivo
            </button>
            <button disabled={!cycleId || loading || !hasImportedReviews} onClick={handleAi} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50" title={!hasImportedReviews ? 'Confirme a importação antes de rodar IA' : undefined}>
              Rodar IA do ciclo
            </button>
          </div>
        </section>

        <section className="grid gap-3 rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-950 lg:grid-cols-4">
          <div><strong>1. Enviar</strong><br />Carrega o CSV/XLS.</div>
          <div><strong>2. Validar</strong><br />Confere se as linhas estão corretas.</div>
          <div><strong>3. Confirmar</strong><br />Cria as avaliações 360 no ciclo.</div>
          <div><strong>4. Rodar IA</strong><br />Analisa os colaboradores importados.</div>
        </section>

        <section className="rounded-2xl bg-white p-5 shadow-soft">
          <h2 className="text-lg font-bold text-slate-900">Planilhas complementares</h2>
          <p className="mt-1 text-sm text-slate-500">
            Use esta área para importar RPM, IHPE e RH. O sistema recalcula RPM/IHPE e atualiza a lista parcial/final.
          </p>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-slate-200 p-4">
              <h3 className="font-bold text-slate-800">RPM 2025/2026</h3>
              <p className="mb-3 text-xs text-slate-500">Calcula horas em projetos / horas totais, excluindo genéricas e treinamento.</p>
              <input type="file" accept=".xlsx,.xls" onChange={(event) => setRpmFile(event.target.files?.[0] || null)} className="w-full text-sm" />
              <button disabled={!rpmFile || loading} onClick={() => handleOperationalUpload('rpm')} className="mt-3 rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Importar RPM</button>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <h3 className="font-bold text-slate-800">IHPE 2025/2026</h3>
              <p className="mb-3 text-xs text-slate-500">Recalcula mês a mês: entregáveis / horas trabalhadas, depois média dos meses.</p>
              <input type="file" accept=".xlsx,.xls" onChange={(event) => setIhpeFile(event.target.files?.[0] || null)} className="w-full text-sm" />
              <button disabled={!ihpeFile || loading} onClick={() => handleOperationalUpload('ihpe')} className="mt-3 rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Importar IHPE</button>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <h3 className="font-bold text-slate-800">ASM RH</h3>
              <p className="mb-3 text-xs text-slate-500">Importa ANC, última promoção, admissão e elegibilidade por mérito.</p>
              <input type="file" accept=".xlsx,.xls" onChange={(event) => setRhFile(event.target.files?.[0] || null)} className="w-full text-sm" />
              <button disabled={!rhFile || loading} onClick={() => handleOperationalUpload('rh')} className="mt-3 rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white disabled:opacity-50">Importar RH</button>
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <div className="rounded-2xl bg-white p-5 shadow-soft">
            <h2 className="text-lg font-bold text-slate-900">Importações</h2>
            <div className="mt-4 flex flex-col gap-3">
              {imports.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelectedImportId(item.id)}
                  className={`rounded-xl border p-3 text-left text-sm ${selectedImport?.id === item.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-white'}`}
                >
                  <p className="font-bold text-slate-900">{item.file_name}</p>
                  <p className="text-slate-500">{item.status} · {item.total_rows} linhas · {item.valid_rows} válidas</p>
                </button>
              ))}
              {!imports.length && <p className="text-sm text-slate-500">Nenhuma importação enviada neste ciclo.</p>}
            </div>
          </div>

          <div className="rounded-2xl bg-white p-5 shadow-soft">
            <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Mapeamento de colunas</h2>
                <p className="text-sm text-slate-500">Campos obrigatórios: nome do avaliado, e-mail/nome do avaliador e nota geral ou competências. Sem relação mapeada, assume PAR.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button disabled={!selectedImport || loading} onClick={handleAutoMap} className="rounded-xl border border-blue-200 px-4 py-2 text-sm font-bold text-blue-700 disabled:opacity-50">Mapear automático</button>
                <button disabled={!selectedImport || loading} onClick={handleMap} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">Salvar mapa</button>
                <button disabled={!selectedImport || loading || selectedImport.status === 'IMPORTED'} onClick={handleValidate} className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 disabled:opacity-50">Validar</button>
                <button disabled={!canConfirmImport || loading} onClick={handleConfirm} className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">Confirmar</button>
              </div>
            </div>

            {selectedImport?.status === 'IMPORTED' && (
              <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                Importação confirmada. As avaliações 360 já foram criadas; agora você pode rodar a IA do ciclo ou ir para Pontuação para gerar a lista parcial.
              </div>
            )}

            {selectedImport?.status === 'VALIDATED' && (
              <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                Arquivo validado, mas ainda não entrou no ciclo. Clique em Confirmar para criar as avaliações 360.
              </div>
            )}

            {selectedImport && (
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {mappingFields.map(([field, label]) => (
                  <label key={field} className="flex flex-col gap-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                    {label}
                    <select
                      className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium normal-case tracking-normal text-slate-700"
                      value={mapping[field] || ''}
                      onChange={(event) => setMapping((current) => ({ ...current, [field]: event.target.value }))}
                    >
                      <option value="">Não mapear</option>
                      {selectedImport.headers.map((header) => (
                        <option key={header} value={header}>{header}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            )}

            {validation && (
              <div className="mt-6 rounded-xl border border-slate-200 p-4">
                <h3 className="font-bold text-slate-900">Resultado da validação</h3>
                <p className="mt-1 text-sm text-slate-600">{validation.valid_rows} linhas válidas · {validation.invalid_rows} linhas inválidas</p>
                {validation.errors.length > 0 && (
                  <div className="mt-3 max-h-64 overflow-auto rounded-lg bg-slate-50">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-100 text-slate-500">
                        <tr><th className="p-2">Linha</th><th className="p-2">Erro</th></tr>
                      </thead>
                      <tbody>
                        {validation.errors.map((row) => (
                          <tr key={row.id} className="border-t border-slate-200">
                            <td className="p-2">{row.row_number}</td>
                            <td className="p-2">{row.error_message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
