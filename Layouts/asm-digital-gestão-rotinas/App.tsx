import React, { useState } from 'react';
import Header from './components/Header';
import RoutineCard from './components/RoutineCard';
import { Routine, RoutineStatus, AIRoutineSuggestion } from './types';
import { Search, LayoutGrid, List, ChevronDown, Plus, Sparkles, X, Loader2 } from 'lucide-react';
import { generateRoutineSuggestion } from './services/geminiService';

// Mock Data matching the screenshot
const initialRoutines: Routine[] = [
  {
    id: '1',
    title: 'Redmine Trimestral',
    iconType: 'document',
    status: RoutineStatus.ACTIVE,
    lastRun: 'Hoje, 14:00',
    lastRunStatus: 'success',
    nextRun: 'Amanhã, 08:00'
  },
  {
    id: '2',
    title: 'FADPRO/IHPE',
    iconType: 'folder',
    status: RoutineStatus.PAUSED,
    lastRun: 'Ontem, 09:30',
    lastRunStatus: 'error',
    nextRun: 'Não agendada'
  },
  {
    id: '3',
    title: 'Azure Épicos',
    iconType: 'azure',
    status: RoutineStatus.ACTIVE,
    lastRun: 'Hoje, 10:15',
    lastRunStatus: 'success',
    nextRun: 'Hoje, 18:00'
  },
  {
    id: '4',
    title: 'Apropriação de Horas',
    iconType: 'clock',
    status: RoutineStatus.ACTIVE,
    lastRun: 'Hoje, 06:00',
    lastRunStatus: 'success',
    nextRun: 'Amanhã, 06:00'
  },
  {
    id: '5',
    title: 'E-mail do Ponto',
    iconType: 'mail',
    status: RoutineStatus.ACTIVE,
    lastRun: 'Sexta, 18:00',
    lastRunStatus: 'success',
    nextRun: 'Segunda, 08:30'
  }
];

const App: React.FC = () => {
  const [routines, setRoutines] = useState<Routine[]>(initialRoutines);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  
  // AI Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AIRoutineSuggestion | null>(null);

  const filteredRoutines = routines.filter(r => 
    r.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setIsGenerating(true);
    setAiSuggestion(null);
    
    const result = await generateRoutineSuggestion(aiPrompt);
    
    if (result) {
      setAiSuggestion(result);
    }
    setIsGenerating(false);
  };

  const handleCreateFromAI = () => {
    if (!aiSuggestion) return;
    
    const newRoutine: Routine = {
      id: Date.now().toString(),
      title: aiSuggestion.title,
      iconType: 'document', // Default for AI
      status: RoutineStatus.ACTIVE,
      lastRun: 'Nunca',
      lastRunStatus: 'warning',
      nextRun: 'Agendado pelo CRON'
    };

    setRoutines([...routines, newRoutine]);
    setIsModalOpen(false);
    setAiPrompt('');
    setAiSuggestion(null);
  };

  return (
    <div className="min-h-screen bg-[#F3F4F6] pb-20">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Gestão de Rotinas</h1>
            <p className="mt-1 text-gray-500">Gerencie, agende e monitore suas automações de relatórios e alertas em tempo real.</p>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center justify-center px-4 py-2.5 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-cyan-500 hover:bg-cyan-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 transition-all"
          >
            <Plus className="h-5 w-5 mr-2" />
            Nova Automação
          </button>
        </div>

        {/* Filters and Controls */}
        <div className="bg-transparent mb-8 flex flex-col sm:flex-row gap-4 justify-between items-center">
          <div className="relative w-full sm:w-96">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              className="block w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg leading-5 bg-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm shadow-sm"
              placeholder="Buscar rotina por nome..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
             <div className="relative w-full sm:w-48">
               <button className="relative w-full bg-white border border-gray-300 rounded-lg shadow-sm pl-3 pr-10 py-2.5 text-left cursor-default focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm">
                 <span className="block truncate text-gray-700">Todos os Status</span>
                 <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                   <ChevronDown className="h-4 w-4 text-gray-400" />
                 </span>
               </button>
             </div>
             
             <div className="flex bg-white rounded-lg border border-gray-300 shadow-sm p-1 gap-1">
               <button 
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-md ${viewMode === 'grid' ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}
               >
                 <LayoutGrid className="h-5 w-5" />
               </button>
               <button 
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-md ${viewMode === 'list' ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}
               >
                 <List className="h-5 w-5" />
               </button>
             </div>
          </div>
        </div>

        {/* Grid Content */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredRoutines.map((routine) => (
            <RoutineCard key={routine.id} routine={routine} />
          ))}

          {/* New Routine Placeholder Card */}
          <button 
            onClick={() => setIsModalOpen(true)}
            className="group border-2 border-dashed border-gray-300 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-cyan-500 hover:bg-cyan-50/50 transition-all duration-200 min-h-[300px]"
          >
            <div className="h-14 w-14 bg-gray-100 rounded-full flex items-center justify-center mb-4 group-hover:bg-cyan-100 transition-colors">
              <Plus className="h-8 w-8 text-gray-400 group-hover:text-cyan-600" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-1">Criar Nova Rotina</h3>
            <p className="text-sm text-gray-500 max-w-[200px]">Configure uma nova automação do zero ou use IA para ajudar.</p>
          </button>
        </div>
      </main>

      <footer className="mt-20 border-t border-gray-200 py-8 bg-white">
        <div className="max-w-7xl mx-auto px-4 text-center text-gray-500 text-sm">
          &copy; 2024 Platforma de Automação IT. Todos os direitos reservados.
        </div>
      </footer>

      {/* AI Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" aria-hidden="true">
              <div className="absolute inset-0 bg-gray-500 opacity-75" onClick={() => setIsModalOpen(false)}></div>
            </div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div className="hidden sm:block absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
                  onClick={() => setIsModalOpen(false)}
                >
                  <span className="sr-only">Close</span>
                  <X className="h-6 w-6" />
                </button>
              </div>

              <div className="sm:flex sm:items-start">
                <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-cyan-100 sm:mx-0 sm:h-10 sm:w-10">
                  <Sparkles className="h-6 w-6 text-cyan-600" />
                </div>
                <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                  <h3 className="text-lg leading-6 font-medium text-gray-900">
                    Criar Automação com IA
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500 mb-4">
                      Descreva o que você precisa automatizar e deixe nossa IA configurar a rotina ideal para você.
                    </p>
                    
                    <textarea 
                      className="w-full border border-gray-300 rounded-md p-3 focus:ring-cyan-500 focus:border-cyan-500 text-sm"
                      rows={4}
                      placeholder="Ex: Gere um backup do banco de dados SQL toda sexta-feira às 23h e envie um email de confirmação."
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                    ></textarea>

                    {aiSuggestion && (
                      <div className="mt-4 bg-gray-50 rounded-md p-4 border border-gray-200 text-left">
                         <h4 className="text-sm font-bold text-gray-900 mb-2">Sugestão: {aiSuggestion.title}</h4>
                         <p className="text-xs text-gray-600 mb-2">{aiSuggestion.description}</p>
                         <div className="flex gap-2 text-xs">
                            <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded font-mono">{aiSuggestion.cronExpression}</span>
                            <span className="bg-gray-200 text-gray-700 px-2 py-1 rounded">Duração est: {aiSuggestion.estimatedDuration}</span>
                         </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                {!aiSuggestion ? (
                   <button
                    type="button"
                    disabled={isGenerating || !aiPrompt.trim()}
                    onClick={handleGenerate}
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-cyan-600 text-base font-medium text-white hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4" />
                        Gerando...
                      </>
                    ) : (
                      'Gerar Sugestão'
                    )}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCreateFromAI}
                    className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-green-600 text-base font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    Criar Rotina
                  </button>
                )}
               
                <button
                  type="button"
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 sm:mt-0 sm:w-auto sm:text-sm"
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
