import { User, StatData, Connector, Alert, AutomationTask } from './types';

export const CURRENT_USER: User = {
  name: 'Admin User',
  email: 'admin@company.com',
  avatarUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBcqZ9uvhSm8m4wsOjyjpDEdsppaPfZFMBQ5T_c8jNk3UYcBg7j-CwnXRNb8et7Bz7jB_UUEFf1QLt8jD_4eo9UOGJQRgCuFyAefSKFwXspJEWvgtXEyAfmeQUIJ5C3NrmNOlPKDAfoswQhSbp9xXsGqGDJDpMCYHZbD_LDHdHJs2OnJXiQ1qJFarMkZU-qEqZ8iBbRhixIizZkc6pC9UwZn6xUh7mw-Os7h1lTYOc36dABlyzuL_n0Dz9TM8zGRpCqTA1B0vYqLJY'
};

export const DASHBOARD_STATS: StatData[] = [
  {
    title: 'Conectores Ativos',
    value: '12',
    total: '/15',
    trend: 'Estável',
    trendDirection: 'neutral',
    icon: 'cable'
  },
  {
    title: 'Alertas Enviados (Hoje)',
    value: '342',
    trend: '+12%',
    trendDirection: 'up',
    icon: 'bell'
  },
  {
    title: 'Relatórios Pendentes',
    value: '3',
    trend: '-2 vs ontem',
    trendDirection: 'down', // 'down' is usually bad, but here contextually it might be good, but visually green/red depends on meaning. Following screenshot: Green
    icon: 'file'
  },
  {
    title: 'Economia de Tempo (IA)',
    value: '14h',
    trend: '+2.5h',
    trendDirection: 'up',
    icon: 'star',
    highlight: true
  }
];

export const CONNECTORS: Connector[] = [
  { id: '1', name: 'AWS', status: 'online', type: 'cloud', provider: 'aws' },
  { id: '2', name: 'Azure', status: 'online', type: 'cloud', provider: 'azure' },
  { id: '3', name: 'Slack', status: 'offline', type: 'chat', provider: 'slack' },
  { id: '4', name: 'Jira', status: 'online', type: 'task', provider: 'jira' },
  { id: '5', name: 'ServiceNow', status: 'online', type: 'db', provider: 'servicenow' },
];

export const RECENT_ALERTS: Alert[] = [
  {
    id: '1',
    title: 'Erro de Backup no Servidor DB-01',
    subtitle: 'Falha na conexão TCP/IP • Cluster A',
    type: 'critical',
    timeAgo: '10 min atrás',
    tag: 'Crítico'
  },
  {
    id: '2',
    title: 'Uso de CPU elevado',
    subtitle: 'Instância i-034af acima de 85% por 5m',
    type: 'warning',
    timeAgo: '25 min atrás',
    tag: 'Atenção'
  },
  {
    id: '3',
    title: 'Deploy automático concluído',
    subtitle: 'Release v2.4.1 em produção',
    type: 'success',
    timeAgo: '1h atrás',
    tag: 'Sucesso'
  }
];

export const UPCOMING_AUTOMATIONS: AutomationTask[] = [
  {
    id: '1',
    time: '14:00',
    title: 'Gerar Relatório Semanal',
    subtitle: 'Enviar para Gestão de TI',
    status: 'upcoming',
    isNext: true
  },
  {
    id: '2',
    time: '14:30',
    title: 'Limpeza de Cache',
    subtitle: 'Servidores de Aplicação',
    status: 'pending'
  },
  {
    id: '3',
    time: '16:00',
    title: 'Sincronização LDAP',
    subtitle: 'Atualização de usuários',
    status: 'pending'
  },
  {
    id: '4',
    time: '18:00',
    title: 'Verificação de Segurança',
    subtitle: 'Scan de vulnerabilidades',
    status: 'pending'
  }
];