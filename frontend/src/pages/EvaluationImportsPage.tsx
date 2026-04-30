import { useEffect, useMemo, useRef, useState } from 'react';
import { BarChart2, CheckCircle2, ChevronDown, CloudUpload, FileText, FileUp, Sparkles, Users } from 'lucide-react';
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
] as const;

const mappingGroups = [
  {
    title: 'Identificadores',
    fields: ['evaluated_email', 'evaluated_name', 'relation_type', 'evaluator_email', 'evaluator_name', 'submitted_at'],
  },
  {
    title: 'Competências & notas',
    fields: ['general_score', 'communication_score', 'teamwork_score', 'commitment_score', 'autonomy_score', 'quality_score', 'problem_solving_score'],
  },
  {
    title: 'Campos qualitativos (textos longos)',
    fields: ['strengths_comment', 'improvement_comment', 'general_comment'],
  },
] as const;

const requiredMappingFields = new Set(['evaluated_name', 'evaluator_email']);
const fieldLabels = Object.fromEntries(mappingFields) as Record<string, string>;

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

const stepItems = ['Enviar', 'Validar', 'Confirmar', 'Rodar IA'];

const getStepState = (selectedImport: EvaluationImport | undefined, hasImportedReviews: boolean) => {
  if (hasImportedReviews) return 3;
  if (!selectedImport) return 0;
  if (selectedImport.status === 'VALIDATED') return 2;
  if (selectedImport.status === 'MAPPED') return 1;
  return 0;
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

  const mainFileRef = useRef<HTMLInputElement>(null);
  const rpmFileRef = useRef<HTMLInputElement>(null);
  const ihpeFileRef = useRef<HTMLInputElement>(null);
  const rhFileRef = useRef<HTMLInputElement>(null);

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
  const activeStep = getStepState(selectedImport, hasImportedReviews);

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
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-6 text-[#191c1e]">
        <header>
          <h1 className="text-2xl font-black tracking-tight text-[#0f172a]">Importação CSV/Excel e IA qualitativa</h1>
          <div className="mt-4 flex items-center gap-0 overflow-x-auto pb-1">
            {stepItems.map((item, index) => (
              <div key={item} className="flex min-w-fit items-center">
                <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-black ${index <= activeStep ? 'bg-[#004ac6] text-white' : 'bg-[#e6e8ea] text-[#434654]'}`}>{index + 1}</span>
                <span className={`ml-2 text-xs font-bold ${index <= activeStep ? 'text-[#003594]' : 'text-[#434654]'}`}>{item}</span>
                {index < stepItems.length - 1 && <span className={`mx-3 h-px w-16 ${index < activeStep ? 'bg-[#004ac6]' : 'bg-[#c3c6d6]'}`} />}
              </div>
            ))}
          </div>
        </header>

        {message && (
          <div className="rounded-2xl border border-[#b8c8ff] bg-[#eef3ff] px-5 py-3 text-sm font-semibold text-[#003594]">
            {message}
          </div>
        )}

        <section className="rounded-xl border border-[#c3c6d6] bg-white p-5 shadow-sm">
          <div className="grid gap-5 lg:grid-cols-[1fr_2fr_auto] lg:items-end">
            <label className="flex flex-col gap-2">
              <span className="text-[11px] font-black uppercase tracking-[0.12em] text-[#434654]">Ciclo avaliativo</span>
              <span className="relative">
                <select className="h-12 w-full appearance-none rounded-lg border border-[#c3c6d6] bg-[#f2f4f6] px-4 pr-10 text-sm font-semibold text-[#191c1e] outline-none focus:border-[#004ac6] focus:ring-2 focus:ring-[#dbe1ff]" value={cycleId || ''} onChange={(event) => handleCycleChange(Number(event.target.value))}>
                  {cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-5 w-5 text-[#737685]" />
              </span>
            </label>

            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-black uppercase tracking-[0.12em] text-[#434654]">Arquivo de dados</span>
              <button type="button" onClick={() => mainFileRef.current?.click()} className="flex h-12 items-center justify-between rounded-lg border-2 border-dashed border-[#c3c6d6] bg-[#f2f4f6] px-4 text-left transition hover:bg-[#e6e8ea]">
                <span className="flex min-w-0 items-center gap-3">
                  <FileUp className="h-5 w-5 shrink-0 text-[#737685]" />
                  <span className="truncate text-sm font-bold text-[#191c1e]">{file?.name || 'CSV/Excel Google Forms'}</span>
                </span>
                <span className="text-xs font-bold text-[#737685]">Procurar</span>
              </button>
              <input ref={mainFileRef} className="hidden" type="file" accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </div>

            <div className="flex flex-wrap gap-3 lg:flex-nowrap">
              <button disabled={!file || !cycleId || loading} onClick={handleUpload} className="inline-flex h-12 items-center gap-2 rounded-lg bg-[#004ac6] px-5 text-sm font-black text-white shadow-sm transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-50">
                <CloudUpload className="h-4 w-4" />
                Enviar arquivo
              </button>
              <button disabled={!cycleId || loading || !hasImportedReviews} onClick={handleAi} className="h-12 rounded-lg border border-[#c3c6d6] bg-white px-5 text-sm font-black text-[#191c1e] transition hover:bg-[#f2f4f6] disabled:cursor-not-allowed disabled:opacity-50" title={!hasImportedReviews ? 'Confirme a importação antes de rodar IA' : undefined}>
                Rodar IA do ciclo
              </button>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-black text-[#191c1e]">Planilhas complementares</h2>
          <div className="mt-4 grid gap-5 md:grid-cols-3">
            <OperationalCard title="RPM 2025/2026" icon={<FileText className="h-5 w-5 text-[#46566c]" />} file={rpmFile} inputRef={rpmFileRef} onFileChange={setRpmFile} onImport={() => handleOperationalUpload('rpm')} disabled={!rpmFile || loading} />
            <OperationalCard title="IHPE 2025/2026" icon={<BarChart2 className="h-5 w-5 text-[#46566c]" />} file={ihpeFile} inputRef={ihpeFileRef} onFileChange={setIhpeFile} onImport={() => handleOperationalUpload('ihpe')} disabled={!ihpeFile || loading} />
            <OperationalCard title="ASM RH" icon={<Users className="h-5 w-5 text-[#46566c]" />} file={rhFile} inputRef={rhFileRef} onFileChange={setRhFile} onImport={() => handleOperationalUpload('rh')} disabled={!rhFile || loading} />
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[300px_1fr]">
          <aside className="h-fit overflow-hidden rounded-xl border border-[#c3c6d6] bg-white shadow-sm">
            <div className="border-b border-[#c3c6d6] bg-[#f2f4f6] px-4 py-3">
              <h2 className="text-lg font-black text-[#191c1e]">Importações</h2>
            </div>
            <div className="flex flex-col gap-2 p-3">
              {imports.map((item) => (
                <button key={item.id} onClick={() => setSelectedImportId(item.id)} className={`flex items-start gap-3 rounded-lg border px-3 py-3 text-left transition ${selectedImport?.id === item.id ? 'border-[#004ac6]/30 bg-[#dbe1ff] text-[#003594]' : 'border-transparent text-[#434654] hover:bg-[#f2f4f6]'}`}>
                  <FileText className={`mt-0.5 h-5 w-5 shrink-0 ${selectedImport?.id === item.id ? 'text-[#004ac6]' : 'text-[#737685]'}`} />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-black">{item.file_name}</span>
                    <span className="mt-1 block text-xs opacity-80">{item.status} · {item.total_rows} linhas · {item.valid_rows} válidas</span>
                  </span>
                </button>
              ))}
              {!imports.length && <p className="rounded-lg bg-[#f2f4f6] px-3 py-4 text-sm font-semibold text-[#737685]">Nenhuma importação enviada neste ciclo.</p>}
            </div>
          </aside>

          <div className="rounded-xl border border-[#c3c6d6] bg-white p-5 shadow-sm">
            <div className="flex flex-col justify-between gap-4 border-b border-[#c3c6d6] pb-5 xl:flex-row xl:items-start">
              <div>
                <h2 className="text-xl font-black text-[#191c1e]">Mapeamento de colunas</h2>
                <StatusPill selectedImport={selectedImport} validation={validation} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ActionButton disabled={!selectedImport || loading} onClick={handleAutoMap} variant="light"><Sparkles className="h-4 w-4" />Mapear automático</ActionButton>
                <ActionButton disabled={!selectedImport || loading} onClick={handleMap} variant="light">Salvar mapa</ActionButton>
                <ActionButton disabled={!selectedImport || loading || selectedImport.status === 'IMPORTED'} onClick={handleValidate} variant="soft">Validar</ActionButton>
                <ActionButton disabled={!canConfirmImport || loading} onClick={handleConfirm} variant="primary">Confirmar</ActionButton>
              </div>
            </div>

            {selectedImport && (
              <div className="mt-6 space-y-7">
                {mappingGroups.map((group) => (
                  <div key={group.title}>
                    <div className="mb-4 border-b border-[#c3c6d6]/70 pb-2">
                      <h3 className="text-[11px] font-black uppercase tracking-[0.14em] text-[#434654]">{group.title}</h3>
                    </div>
                    <div className="grid gap-x-6 gap-y-5 md:grid-cols-2 xl:grid-cols-3">
                      {group.fields.map((field) => (
                        <MappingSelect key={field} field={field} label={fieldLabels[field]} required={requiredMappingFields.has(field)} value={mapping[field] || ''} headers={selectedImport.headers} onChange={(value) => setMapping((current) => ({ ...current, [field]: value }))} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {validation && (
              <div className="mt-6 rounded-xl border border-[#c3c6d6] p-4">
                <h3 className="font-black text-[#191c1e]">Resultado da validação</h3>
                <p className="mt-1 text-sm font-semibold text-[#434654]">{validation.valid_rows} linhas válidas · {validation.invalid_rows} linhas inválidas</p>
                {validation.errors.length > 0 && (
                  <div className="mt-3 max-h-64 overflow-auto rounded-lg bg-[#f2f4f6]">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#e6e8ea] text-[#434654]"><tr><th className="p-2">Linha</th><th className="p-2">Erro</th></tr></thead>
                      <tbody>{validation.errors.map((row) => <tr key={row.id} className="border-t border-[#c3c6d6]"><td className="p-2">{row.row_number}</td><td className="p-2">{row.error_message}</td></tr>)}</tbody>
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

function OperationalCard({ title, icon, file, inputRef, onFileChange, onImport, disabled }: {
  title: string;
  icon: React.ReactNode;
  file: File | null;
  inputRef: React.RefObject<HTMLInputElement>;
  onFileChange: (file: File | null) => void;
  onImport: () => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[#c3c6d6] bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-black text-[#191c1e]">{title}</h3>
        {icon}
      </div>
      <button type="button" onClick={() => inputRef.current?.click()} className="rounded-lg border border-dashed border-[#c3c6d6] bg-[#f2f4f6] p-4 text-center text-xs font-bold text-[#737685] transition hover:bg-[#e6e8ea]">
        {file?.name || 'Selecione o arquivo...'}
      </button>
      <input ref={inputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={(event) => onFileChange(event.target.files?.[0] || null)} />
      <button disabled={disabled} onClick={onImport} className="h-10 rounded-lg border border-[#c3c6d6] bg-white text-sm font-black text-[#191c1e] transition hover:bg-[#f2f4f6] disabled:cursor-not-allowed disabled:opacity-50">Importar</button>
    </div>
  );
}

function StatusPill({ selectedImport, validation }: { selectedImport?: EvaluationImport; validation: ImportValidationResult | null }) {
  if (!selectedImport) {
    return <p className="mt-2 rounded-full bg-[#f2f4f6] px-3 py-1.5 text-sm font-semibold text-[#737685]">Envie um arquivo para iniciar o mapeamento.</p>;
  }
  if (selectedImport.status === 'IMPORTED') {
    return <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-bold text-emerald-700"><CheckCircle2 className="h-4 w-4" />Importação confirmada. A IA já pode ser executada.</p>;
  }
  if (validation || selectedImport.status === 'VALIDATED') {
    return <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1.5 text-sm font-bold text-amber-700"><CheckCircle2 className="h-4 w-4" />Arquivo validado. Confirme para criar as avaliações 360.</p>;
  }
  return <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-[#dbe1ff] px-3 py-1.5 text-sm font-bold text-[#003594]"><CheckCircle2 className="h-4 w-4" />Mapeamento preparado. Revise antes de validar.</p>;
}

function ActionButton({ children, disabled, onClick, variant }: { children: React.ReactNode; disabled: boolean; onClick: () => void; variant: 'light' | 'soft' | 'primary' }) {
  const className = variant === 'primary'
    ? 'bg-[#004ac6] text-white shadow-sm hover:brightness-95'
    : variant === 'soft'
      ? 'border border-[#b8c8ff] bg-[#dbe1ff]/60 text-[#003594] hover:bg-[#dbe1ff]'
      : 'border border-[#c3c6d6] bg-white text-[#191c1e] hover:bg-[#f2f4f6]';
  return <button disabled={disabled} onClick={onClick} className={`inline-flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-50 ${className}`}>{children}</button>;
}

function MappingSelect({ field, label, required, value, headers, onChange }: {
  field: string;
  label: string;
  required: boolean;
  value: string;
  headers: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex justify-between text-xs font-black text-[#191c1e]">
        {label}
        {required && <span className="text-red-600">*</span>}
      </span>
      <select className={`h-10 w-full rounded-md border bg-[#f2f4f6] px-3 text-sm font-semibold text-[#191c1e] outline-none focus:border-[#004ac6] focus:ring-1 focus:ring-[#004ac6] ${value ? 'border-[#9aa7cf]' : 'border-[#c3c6d6] text-[#737685]'}`} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{field === 'submitted_at' || field === 'general_comment' ? '-- Selecionar coluna --' : 'Não mapear'}</option>
        {headers.map((header) => <option key={header} value={header}>{header}</option>)}
      </select>
    </label>
  );
}

