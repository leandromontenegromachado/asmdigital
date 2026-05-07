import api from './client';

export type CycleStatus = 'RASCUNHO' | 'EM_COLETA' | 'EM_ANALISE' | 'EM_CALIBRACAO' | 'FINALIZADO';
export type EvaluationCategory = 'DESTAQUE' | 'MUITO_BOM' | 'BOM' | 'EM_DESENVOLVIMENTO' | 'ATENCAO';
export type RelationType = 'MANAGER' | 'PEER' | 'INTERNAL_CLIENT' | 'SELF';
export type ImportStatus = 'UPLOADED' | 'MAPPED' | 'VALIDATED' | 'IMPORTED' | 'ERROR';

export interface EvaluationCycle {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  status: CycleStatus;
  performance_weight: number;
  behavior_weight: number;
  potential_weight: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Employee {
  id: number;
  name: string;
  email: string;
  teams_user_id?: string | null;
  matricula?: string | null;
  cargo?: string | null;
  setor?: string | null;
  department: string | null;
  position: string | null;
  manager_id: number | null;
  manager_name: string | null;
  active: boolean;
  recebe_notificacao?: boolean;
  participa_avaliacao?: boolean;
  canal_preferencial?: string;
  created_at: string;
  updated_at: string;
}

export interface Indicator {
  id: number;
  cycle_id: number;
  employee_id: number;
  employee_name: string | null;
  rpm_original: number | null;
  rpm_normalized: number | null;
  ihpe_original: number | null;
  ihpe_normalized: number | null;
}

export interface EvaluationAlert {
  id: number;
  cycle_id: number;
  employee_id: number;
  employee_name: string | null;
  alert_type: string;
  message: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  created_at: string;
  resolved_at: string | null;
  resolved_by: number | null;
}

export interface EvaluationScoreRow {
  id: number;
  cycle_id: number;
  employee_id: number;
  employee_name: string;
  department: string | null;
  position: string | null;
  manager_name: string | null;
  performance_score: number | null;
  behavior_score: number | null;
  potential_score: number | null;
  preliminary_final_score: number | null;
  suggested_category: EvaluationCategory | null;
  final_category: EvaluationCategory | null;
  nine_box_position: string | null;
  calibration_justification: string | null;
  calibrated_by: number | null;
  calibrated_at: string | null;
  alerts: EvaluationAlert[];
}

export interface Review360 {
  id: number;
  cycle_id: number;
  import_id?: number | null;
  import_row_id?: number | null;
  evaluator_id: number | null;
  evaluator_email?: string | null;
  evaluator_name: string | null;
  evaluated_id: number;
  evaluated_email?: string | null;
  evaluated_name: string | null;
  relation_type: RelationType;
  score: number | null;
  general_score?: number | null;
  communication_score?: number | null;
  teamwork_score?: number | null;
  commitment_score?: number | null;
  autonomy_score?: number | null;
  quality_score?: number | null;
  problem_solving_score?: number | null;
  strengths_comment?: string | null;
  improvement_comment?: string | null;
  general_comment?: string | null;
  comment: string | null;
}

export interface Potential {
  id: number;
  cycle_id: number;
  employee_id: number;
  employee_name: string | null;
  score: number;
  comment: string | null;
}

export interface CalculateResult {
  cycle_id: number;
  processed: number;
  incomplete: number;
  alerts_generated: number;
}

export interface Dashboard {
  cycle_id: number;
  total_evaluated: number;
  average_final_score: number | null;
  suggested_by_category: Record<string, number>;
  final_by_category: Record<string, number>;
  by_department: Record<string, number>;
  alerts: EvaluationAlert[];
}

export interface EvaluationImport {
  id: number;
  cycle_id: number;
  file_name: string;
  status: ImportStatus;
  uploaded_by: number | null;
  uploaded_at: string;
  column_mapping_json: Record<string, string> | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  error_message: string | null;
  headers: string[];
}

export interface EvaluationImportRow {
  id: number;
  import_id: number;
  row_number: number;
  raw_data_json: Record<string, unknown>;
  normalized_data_json: Record<string, unknown> | null;
  status: 'PENDING' | 'VALID' | 'IMPORTED' | 'ERROR';
  error_message: string | null;
}

export interface ImportValidationResult {
  import_id: number;
  status: ImportStatus;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  errors: EvaluationImportRow[];
}

export interface ImportConfirmResult {
  import_id: number;
  imported_rows: number;
  created_reviews: number;
}

export interface OperationalImportResult {
  imported_rows: number;
  updated_employees: number;
  updated_indicators: number;
  updated_rh_records: number;
  warnings: string[];
}

export interface AiFeedbackAnalysis {
  id: number;
  cycle_id: number;
  employee_id: number;
  employee_name: string | null;
  status: 'PENDING' | 'PROCESSED' | 'REVIEWED' | 'ERROR';
  summary: string | null;
  strengths_json: string[] | null;
  attention_points_json: string[] | null;
  recurring_themes_json: string[] | null;
  qualitative_alerts_json: Array<Record<string, unknown>> | null;
  suggested_feedback: string | null;
  model_used: string | null;
  error_message: string | null;
}

export interface PreliminaryReport {
  employee: Employee;
  score: EvaluationScoreRow | null;
  reviews: Review360[];
  ai_analysis: AiFeedbackAnalysis | null;
  alerts: EvaluationAlert[];
}

export const listEvaluationCycles = async () => (await api.get<EvaluationCycle[]>('/evaluation-cycles')).data;

export const createEvaluationCycle = async (payload: {
  name: string;
  start_date: string;
  end_date: string;
  status?: CycleStatus;
  notes?: string | null;
}) => (await api.post<EvaluationCycle>('/evaluation-cycles', payload)).data;

export const updateEvaluationCycleStatus = async (id: number, status: CycleStatus) =>
  (await api.patch<EvaluationCycle>(`/evaluation-cycles/${id}/status`, { status })).data;

export const listEmployees = async (params?: { department?: string; manager_id?: number }) =>
  (await api.get<Employee[]>('/employees', { params })).data;

export const createEmployee = async (payload: {
  name: string;
  email: string;
  teams_user_id?: string | null;
  matricula?: string | null;
  cargo?: string | null;
  setor?: string | null;
  department?: string | null;
  position?: string | null;
  manager_id?: number | null;
  active?: boolean;
  recebe_notificacao?: boolean;
  participa_avaliacao?: boolean;
  canal_preferencial?: string;
}) => (await api.post<Employee>('/employees', payload)).data;

export const updateEmployee = async (id: number, payload: Partial<Employee>) =>
  (await api.put<Employee>(`/employees/${id}`, payload)).data;

export const uploadEvaluationCsv = async (cycleId: number, file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return (await api.post<EvaluationImport>(`/evaluation-cycles/${cycleId}/imports`, formData)).data;
};

export const listEvaluationImports = async (cycleId: number) =>
  (await api.get<EvaluationImport[]>(`/evaluation-cycles/${cycleId}/imports`)).data;

export const mapImportColumns = async (cycleId: number, importId: number, mapping: Record<string, string>) =>
  (await api.post<EvaluationImport>(`/evaluation-cycles/${cycleId}/imports/${importId}/map-columns`, { mapping })).data;

export const validateImport = async (cycleId: number, importId: number) =>
  (await api.post<ImportValidationResult>(`/evaluation-cycles/${cycleId}/imports/${importId}/validate`)).data;

export const confirmImport = async (cycleId: number, importId: number) =>
  (await api.post<ImportConfirmResult>(`/evaluation-cycles/${cycleId}/imports/${importId}/confirm`)).data;

export const getImportErrors = async (cycleId: number, importId: number) =>
  (await api.get<EvaluationImportRow[]>(`/evaluation-cycles/${cycleId}/imports/${importId}/errors`)).data;

export const listIndicators = async (cycleId: number) =>
  (await api.get<Indicator[]>(`/evaluation-cycles/${cycleId}/indicators`)).data;

export const upsertIndicator = async (cycleId: number, employeeId: number, payload: { rpm_original: number | null; ihpe_original: number | null }) =>
  (await api.put<Indicator>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/indicators`, payload)).data;

export const listReviews = async (cycleId: number) =>
  (await api.get<Review360[]>(`/evaluation-cycles/${cycleId}/reviews`)).data;

export const createReview = async (cycleId: number, payload: { evaluator_id: number; evaluated_id: number; relation_type: RelationType; score: number; comment?: string | null }) =>
  (await api.post<Review360>(`/evaluation-cycles/${cycleId}/reviews`, payload)).data;

export const upsertPotential = async (cycleId: number, employeeId: number, payload: { score: number; comment?: string | null }) =>
  (await api.put<Potential>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/potential`, payload)).data;

export const calculateScores = async (cycleId: number) =>
  (await api.post<CalculateResult>(`/evaluation-cycles/${cycleId}/calculate-scores`)).data;

export const listScores = async (cycleId: number) =>
  (await api.get<EvaluationScoreRow[]>(`/evaluation-cycles/${cycleId}/scores`)).data;

export const runCycleAiAnalysis = async (cycleId: number) =>
  (await api.post<AiFeedbackAnalysis[]>(`/evaluation-cycles/${cycleId}/run-ai-analysis`)).data;

export const runEmployeeAiAnalysis = async (cycleId: number, employeeId: number) =>
  (await api.post<AiFeedbackAnalysis>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/run-ai-analysis`)).data;

export const getEmployeeAiAnalysis = async (cycleId: number, employeeId: number) =>
  (await api.get<AiFeedbackAnalysis>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/ai-analysis`)).data;

export const getPreliminaryReport = async (cycleId: number, employeeId: number) =>
  (await api.get<PreliminaryReport>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/preliminary-report`)).data;

export const getCalibration = async (cycleId: number) =>
  (await api.get<EvaluationScoreRow[]>(`/evaluation-cycles/${cycleId}/calibration`)).data;

export const calibrateEmployee = async (cycleId: number, employeeId: number, payload: { final_category: EvaluationCategory; calibration_justification?: string | null }) =>
  (await api.patch<EvaluationScoreRow>(`/evaluation-cycles/${cycleId}/employees/${employeeId}/calibration`, payload)).data;

export const getFinalList = async (cycleId: number, params?: { department?: string; category?: string }) =>
  (await api.get<EvaluationScoreRow[]>(`/evaluation-cycles/${cycleId}/final-list`, { params })).data;

export const exportFinalListCsv = async (cycleId: number) =>
  (await api.get(`/evaluation-cycles/${cycleId}/final-list/export`, { responseType: 'blob' })).data as Blob;

export const getFinalReportHtml = async (cycleId: number) =>
  (await api.get(`/evaluation-cycles/${cycleId}/final-report/html`, { responseType: 'blob' })).data as Blob;

const uploadOperationalFile = async (cycleId: number, kind: 'rpm' | 'ihpe' | 'rh', file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return (await api.post<OperationalImportResult>(`/evaluation-cycles/${cycleId}/operational-imports/${kind}`, formData)).data;
};

export const uploadRpmFile = async (cycleId: number, file: File) => uploadOperationalFile(cycleId, 'rpm', file);
export const uploadIhpeFile = async (cycleId: number, file: File) => uploadOperationalFile(cycleId, 'ihpe', file);
export const uploadRhFile = async (cycleId: number, file: File) => uploadOperationalFile(cycleId, 'rh', file);

export const listAlerts = async (cycleId: number) =>
  (await api.get<EvaluationAlert[]>(`/evaluation-cycles/${cycleId}/alerts`)).data;

export const getDashboard = async (cycleId: number) =>
  (await api.get<Dashboard>(`/evaluation-cycles/${cycleId}/dashboard`)).data;
