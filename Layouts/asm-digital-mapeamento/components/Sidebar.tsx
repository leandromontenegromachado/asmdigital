import React from 'react';
import { LayoutDashboard, FileText, Settings, Network, Users, Bot } from 'lucide-react';

export const Sidebar: React.FC = () => {
  const menuItems = [
    { icon: LayoutDashboard, label: 'Dashboard', active: false },
    { icon: FileText, label: 'Relatórios', active: false },
    { type: 'divider', label: 'CONFIGURAÇÃO' },
    { icon: Settings, label: 'Mapeamento', active: true },
    { icon: Network, label: 'Integrações', active: false },
    { icon: Users, label: 'Usuários', active: false },
  ];

  return (
    <aside className="w-64 bg-slate-50 border-r border-slate-200 hidden md:flex flex-col flex-shrink-0 h-screen fixed left-0 top-0 z-20">
      {/* Brand */}
      <div className="h-16 flex items-center px-6 border-b border-slate-100">
        <div className="bg-primary-100 p-2 rounded-lg mr-3">
          <Bot size={24} className="text-primary-600" />
        </div>
        <div>
          <h1 className="font-bold text-slate-800 leading-tight">IT Automation</h1>
          <p className="text-xs text-slate-500">Admin Console</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
        {menuItems.map((item, index) => {
          if (item.type === 'divider') {
            return (
              <div key={index} className="px-3 pt-4 pb-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  {item.label}
                </p>
              </div>
            );
          }

          const Icon = item.icon as React.ElementType;
          return (
            <a
              key={index}
              href="#"
              className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors group ${
                item.active
                  ? 'bg-white text-primary-600 shadow-sm ring-1 ring-slate-200'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <Icon
                size={20}
                className={`mr-3 ${
                  item.active ? 'text-primary-500' : 'text-slate-400 group-hover:text-slate-500'
                }`}
              />
              {item.label}
            </a>
          );
        })}
      </nav>

      {/* User Profile */}
      <div className="p-4 border-t border-slate-200">
        <div className="flex items-center p-2 rounded-lg border border-slate-200 bg-white shadow-sm">
          <img
            src="https://picsum.photos/id/64/100/100"
            alt="Admin User"
            className="h-9 w-9 rounded-full object-cover ring-2 ring-white"
          />
          <div className="ml-3 overflow-hidden">
            <p className="text-sm font-medium text-slate-700 truncate">Admin User</p>
            <p className="text-xs text-slate-500 truncate">admin@company.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
};