import { createBrowserRouter } from 'react-router-dom';
import { AuthProvider } from './auth';
import { RequireAuth } from './RequireAuth';
import LoginPage from '../pages/LoginPage';
import DashboardPage from '../pages/DashboardPage';
import ConnectorsPage from '../pages/ConnectorsPage';
import ReportsRedminePage from '../pages/ReportsRedminePage';
import PromptReportsPage from '../pages/PromptReportsPage';
import MappingsPage from '../pages/MappingsPage';
import UsersPage from '../pages/UsersPage';
import RoutinesPage from '../pages/RoutinesPage';

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
      { path: 'reports/prompt-templates', element: <PromptReportsPage /> },
      { path: 'automations', element: <RoutinesPage /> },
      { path: 'settings/mappings', element: <MappingsPage /> },
      { path: 'settings/users', element: <UsersPage /> },
    ],
  },
  {
    path: '/login',
    element: <Root><LoginPage /></Root>,
  },
]);
