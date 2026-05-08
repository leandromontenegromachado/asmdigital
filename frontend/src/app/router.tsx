import { createBrowserRouter } from 'react-router-dom';
import { AuthProvider } from './auth';
import { RequireAuth } from './RequireAuth';
import LoginPage from '../pages/LoginPage';
import DashboardPage from '../pages/DashboardPage';
import ExecutiveDashboardPage from '../pages/ExecutiveDashboardPage';
import ConnectorsPage from '../pages/ConnectorsPage';
import ReportsRedminePage from '../pages/ReportsRedminePage';
import AzureBoardsPage from '../pages/AzureBoardsPage';
import PromptReportsPage from '../pages/PromptReportsPage';
import MappingsPage from '../pages/MappingsPage';
import UsersPage from '../pages/UsersPage';
import RoutinesPage from '../pages/RoutinesPage';
import EmployeesPage from '../pages/EmployeesPage';
import NotificationsPage from '../pages/NotificationsPage';
import FalaAiPage from '../pages/FalaAiPage';
import EvaluationCyclesPage from '../pages/EvaluationCyclesPage';
import EvaluationAiReportPage from '../pages/EvaluationAiReportPage';
import EvaluationImportsPage from '../pages/EvaluationImportsPage';
import EvaluationScoringPage from '../pages/EvaluationScoringPage';
import EvaluationCalibrationPage from '../pages/EvaluationCalibrationPage';
import EvaluationFinalListPage from '../pages/EvaluationFinalListPage';

const Root = ({ children }: { children: React.ReactNode }) => {
  return <AuthProvider>{children}</AuthProvider>;
};

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Root><RequireAuth /></Root>,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'executive-dashboard', element: <ExecutiveDashboardPage /> },
      { path: 'connectors', element: <ConnectorsPage /> },
      { path: 'reports/redmine-deliveries', element: <ReportsRedminePage /> },
      { path: 'reports/azure-boards', element: <AzureBoardsPage /> },
      { path: 'reports/prompt-templates', element: <PromptReportsPage /> },
      { path: 'automations', element: <RoutinesPage /> },
      { path: 'chefia', element: <FalaAiPage /> },
      { path: 'fala-ai', element: <FalaAiPage /> },
      { path: 'automation', element: <RoutinesPage /> },
      { path: 'routines', element: <RoutinesPage /> },
      { path: 'rotinas', element: <RoutinesPage /> },
      { path: 'employees', element: <EmployeesPage /> },
      { path: 'funcionarios', element: <EmployeesPage /> },
      { path: 'notifications', element: <NotificationsPage /> },
      { path: 'notificacoes', element: <NotificationsPage /> },
      { path: 'settings/mappings', element: <MappingsPage /> },
      { path: 'settings/users', element: <UsersPage /> },
      { path: 'evaluation/cycles', element: <EvaluationCyclesPage /> },
      { path: 'evaluation/imports', element: <EvaluationImportsPage /> },
      { path: 'evaluation/ai-report', element: <EvaluationAiReportPage /> },
      { path: 'evaluation/scoring', element: <EvaluationScoringPage /> },
      { path: 'evaluation/calibration', element: <EvaluationCalibrationPage /> },
      { path: 'evaluation/final-list', element: <EvaluationFinalListPage /> },
    ],
  },
  {
    path: '/login',
    element: <Root><LoginPage /></Root>,
  },
]);
