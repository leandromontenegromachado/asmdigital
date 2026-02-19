import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Cable,
  FileText,
  Bell,
  Settings,
  Users,
  Bot,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../app/auth';

const CURRENT_USER = {
  name: 'Admin User',
  email: 'admin@company.com',
  avatarUrl:
    'https://lh3.googleusercontent.com/aida-public/AB6AXuBcqZ9uvhSm8m4wsOjyjpDEdsppaPfZFMBQ5T_c8jNk3UYcBg7j-CwnXRNb8et7Bz7jB_UUEFf1QLt8jD_4eo9UOGJQRgCuFyAefSKFwXspJEWvgtXEyAfmeQUIJ5C3NrmNOlPKDAfoswQhSbp9xXsGqGDJDpMCYHZbD_LDHdHJs2OnJXiQ1qJFarMkZU-qEqZ8iBbRhixIizZkc6pC9UwZn6xUh7mw-Os7h1lTYOc36dABlyzuL_n0Dz9TM8zGRpCqTA1B0vYqLJY',
};

const linkBase =
  'flex items-center gap-3 px-3 py-3 rounded-lg transition-colors group border-l-4';

export const Sidebar: React.FC = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="hidden w-72 flex-col border-r border-slate-200 bg-sidebar-bg lg:flex shrink-0 shadow-soft z-20 h-full">
      <div className="flex items-center gap-3 px-6 py-6 border-b border-transparent">
        <div className="size-10 rounded-full bg-gradient-to-br from-primary to-blue-600 flex items-center justify-center shadow-md shadow-blue-200 text-white">
          <Bot size={24} />
        </div>
        <div className="flex flex-col">
          <h1 className="text-slate-900 text-lg font-bold leading-tight">ASM Digital</h1>
          <p className="text-slate-500 text-xs font-normal">v1.0.4 Beta</p>
        </div>
      </div>

      <nav className="flex-1 flex flex-col gap-2 px-4 py-4 overflow-y-auto">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <LayoutDashboard className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Dashboard</p>
            </>
          )}
        </NavLink>

        <NavLink
          to="/connectors"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Cable className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Conectores</p>
            </>
          )}
        </NavLink>

        <NavLink
          to="/reports/redmine-deliveries"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <FileText className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Relatórios</p>
            </>
          )}
        </NavLink>

        <NavLink
          to="/reports/prompt-templates"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Bot className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Relatórios IA</p>
            </>
          )}
        </NavLink>

        <NavLink
          to="/automations"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Bot className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Rotinas</p>
            </>
          )}
        </NavLink>

        <a
          href="#"
          className={`${linkBase} hover:bg-slate-50 border-transparent`}
        >
          <Bell className="text-slate-400 group-hover:text-primary transition-colors" size={20} />
          <p className="text-slate-600 group-hover:text-slate-900 text-sm font-medium transition-colors flex-1">Alertas</p>
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-[10px] font-bold text-red-600">3</span>
        </a>

        <NavLink
          to="/settings/mappings"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Settings className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Configurações</p>
            </>
          )}
        </NavLink>

        <NavLink
          to="/settings/users"
          className={({ isActive }) =>
            `${linkBase} ${
              isActive
                ? 'bg-blue-50 border-primary'
                : 'hover:bg-slate-50 border-transparent'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Users className={isActive ? 'text-primary' : 'text-slate-400 group-hover:text-primary'} size={20} />
              <p className={`text-sm ${isActive ? 'font-bold text-slate-900' : 'font-medium text-slate-600 group-hover:text-slate-900'} transition-colors`}>Usuários</p>
            </>
          )}
        </NavLink>
      </nav>

      <div className="p-4 mt-auto border-t border-slate-100">
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors">
          <div
            className="h-9 w-9 overflow-hidden rounded-full bg-slate-200 bg-cover bg-center border border-slate-200"
            style={{ backgroundImage: `url("${CURRENT_USER.avatarUrl}")` }}
            aria-label="User profile picture"
          />
          <div className="flex flex-col flex-1">
            <p className="text-slate-900 text-sm font-medium">{CURRENT_USER.name}</p>
            <p className="text-slate-500 text-xs">{CURRENT_USER.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-[11px] font-bold text-slate-600 hover:bg-slate-50"
            title="Sair"
          >
            <LogOut size={14} />
            Sair
          </button>
        </div>
      </div>
    </aside>
  );
};
