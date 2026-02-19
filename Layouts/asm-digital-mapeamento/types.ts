export interface TicketData {
  id: string;
  title: string;
  client: {
    raw: string;
    processed: string;
    ruleApplied?: string;
  };
  system: {
    raw: string;
    processed: string;
    ruleApplied?: string;
  };
  delivery: {
    raw: string | null;
    processed: string | null;
    isWarning?: boolean;
  };
}

export enum RuleStatus {
  ACTIVE = 'ATIVO',
  INACTIVE = 'INATIVO'
}
