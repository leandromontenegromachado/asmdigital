import React from 'react';
import { 
  LayoutDashboard, 
  Cable, 
  FileText, 
  Bell, 
  Settings, 
  Bot
} from 'lucide-react';
import { CURRENT_USER } from '../constants';

export const Sidebar: React.FC = () => {
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
        <a href="#" className="flex items-center gap-3 px-3 py-3 rounded-lg bg-blue-50 border-l-4 border-primary transition-all">
          <LayoutDashboard className="text-primary" size={20} />
          <p className="text-slate-900 text-sm font-bold">Dashboard</p>
        </a>
        
        <a href="#" className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-slate-50 transition-colors group border-l-4 border-transparent">
          <Cable className="text-slate-400 group-hover:text-primary transition-colors" size={20} />
          <p className="text-slate-600 group-hover:text-slate-900 text-sm font-medium transition-colors">Conectores</p>
        </a>

        <a href="#" className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-slate-50 transition-colors group border-l-4 border-transparent">
          <FileText className="text-slate-400 group-hover:text-primary transition-colors" size={20} />
          <p className="text-slate-600 group-hover:text-slate-900 text-sm font-medium transition-colors">Relatórios</p>
        </a>

        <a href="#" className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-slate-50 transition-colors group border-l-4 border-transparent w-full">
          <Bell className="text-slate-400 group-hover:text-primary transition-colors" size={20} />
          <p className="text-slate-600 group-hover:text-slate-900 text-sm font-medium transition-colors flex-1">Alertas</p>
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-[10px] font-bold text-red-600">3</span>
        </a>

        <a href="#" className="flex items-center gap-3 px-3 py-3 rounded-lg hover:bg-slate-50 transition-colors group border-l-4 border-transparent">
          <Settings className="text-slate-400 group-hover:text-primary transition-colors" size={20} />
          <p className="text-slate-600 group-hover:text-slate-900 text-sm font-medium transition-colors">Configurações</p>
        </a>
      </nav>

      <div className="p-4 mt-auto border-t border-slate-100">
        <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors">
          <div 
            className="h-9 w-9 overflow-hidden rounded-full bg-slate-200 bg-cover bg-center border border-slate-200"
            style={{ backgroundImage: `url("${CURRENT_USER.avatarUrl}")` }}
            aria-label="User profile picture"
          />
          <div className="flex flex-col">
            <p className="text-slate-900 text-sm font-medium">{CURRENT_USER.name}</p>
            <p className="text-slate-500 text-xs">{CURRENT_USER.email}</p>
          </div>
        </a>
      </div>
    </aside>
  );
};