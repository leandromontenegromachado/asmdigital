import React from 'react';
import { Sidebar } from './Sidebar';

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="flex h-screen w-full bg-background-main">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-y-auto">
        <div className="mx-auto w-full max-w-7xl p-4 md:p-6 lg:p-8 flex flex-col gap-8">
          {children}
        </div>
      </main>
    </div>
  );
};
