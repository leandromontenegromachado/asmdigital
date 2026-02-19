export type ConnectorStatus = 'connected' | 'inactive' | 'error' | 'editing';

export interface Connector {
  id: string;
  name: string;
  description: string;
  logoUrl: string;
  logoAlt: string;
  status: ConnectorStatus;
  syncTime?: string;
  errorMessage?: string;
  errorCode?: string;
  
  // Fields for editing simulation
  config?: {
    urlLabel: string;
    urlValue: string;
    tokenLabel: string;
    tokenValue: string; // masked in UI usually
    projectLabel: string;
    projectValue: string;
    projects: string[];
    warning?: string;
  }
}
