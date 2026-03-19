import { createBrowserRouter } from 'react-router-dom';
import { AuthProvider } from './auth';
import { RequireAuth } from './RequireAuth';
import LoginPage from '../pages/LoginPage';
import DashboardPage from '../pages/DashboardPage';
import ConnectorsPage from '../pages/ConnectorsPage';
import ReportsRedminePage from '../pages/ReportsRedminePage';
import AzureBoardsPage from '../pages/AzureBoardsPage';
import PromptReportsPage from '../pages/PromptReportsPage';
import MappingsPage from '../pages/MappingsPage';
import UsersPage from '../pages/UsersPage';
import RoutinesPage from '../pages/RoutinesPage';
import FalaAiPage from '../pages/FalaAiPage';

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
      { path: 'settings/mappings', element: <MappingsPage /> },
      { path: 'settings/users', element: <UsersPage /> },
    ],
  },
  {
    path: '/login',
    element: <Root><LoginPage /></Root>,
  },
]);
