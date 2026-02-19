export enum RoutineStatus {
  ACTIVE = 'Ativo',
  PAUSED = 'Pausado',
  ERROR = 'Erro',
}

export interface Routine {
  id: string;
  title: string;
  iconType: 'document' | 'folder' | 'azure' | 'clock' | 'mail';
  status: RoutineStatus;
  lastRun: string;
  lastRunStatus: 'success' | 'error' | 'warning';
  nextRun: string;
  description?: string;
}

export interface AIRoutineSuggestion {
  title: string;
  description: string;
  cronExpression: string;
  estimatedDuration: string;
}
