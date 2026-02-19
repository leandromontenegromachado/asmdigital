export interface User {
  name: string;
  email: string;
  avatarUrl: string;
}

export interface StatData {
  title: string;
  value: string | number;
  total?: string | number;
  trend?: string;
  trendDirection?: 'up' | 'down' | 'neutral';
  icon: 'cable' | 'bell' | 'file' | 'star';
  highlight?: boolean;
}

export interface Connector {
  id: string;
  name: string;
  status: 'online' | 'offline';
  type: 'cloud' | 'chat' | 'task' | 'db';
  provider: 'aws' | 'azure' | 'slack' | 'jira' | 'servicenow';
}

export interface Alert {
  id: string;
  title: string;
  subtitle: string;
  type: 'critical' | 'warning' | 'success';
  timeAgo: string;
  tag: string;
}

export interface AutomationTask {
  id: string;
  time: string;
  title: string;
  subtitle: string;
  status: 'pending' | 'upcoming';
  isNext?: boolean;
}