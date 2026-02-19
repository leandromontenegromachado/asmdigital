import React from 'react';
import { Bot, Bell, User } from 'lucide-react';

const Header: React.FC = () => {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 flex items-center gap-2">
              <div className="bg-cyan-500 p-1.5 rounded-lg">
                <Bot className="h-6 w-6 text-white" />
              </div>
              <span className="font-bold text-gray-900 text-lg tracking-tight">Platforma de Automação IT</span>
            </div>
            <nav className="hidden md:ml-10 md:flex md:space-x-8">
              <a href="#" className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                Dashboard
              </a>
              <a href="#" className="border-cyan-500 text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                Rotinas
              </a>
              <a href="#" className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                Logs
              </a>
              <a href="#" className="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium">
                Configurações
              </a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button className="p-1 rounded-full text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500">
              <span className="sr-only">View notifications</span>
              <Bell className="h-6 w-6" />
            </button>
            <div className="ml-3 relative">
              <div className="flex items-center">
                <button className="bg-gray-100 flex text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 p-1">
                  <User className="h-6 w-6 text-gray-600" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
