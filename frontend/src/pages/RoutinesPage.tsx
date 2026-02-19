import React, { useEffect, useState } from 'react';
import { Search, LayoutGrid, List, ChevronDown, Plus, Sparkles, X, Loader2 } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { listAutomations, runAutomation, listAutomationRuns, Automation, AutomationRun } from '../api/automations';

interface RoutineCardModel {
  id: string;
  title: string;
  iconType: 'document' | 'folder' | 'azure' | 'clock' | 'mail';
  status: 'Ativo' | 'Pausado' | 'Erro';
  lastRun: string;
  lastRunStatus: 'success' | 'error' | 'warning';
  nextRun: string;
}

const iconMap: Record<string, RoutineCardModel['iconType']> = {
  redmine_quarterly_report: 'document',
  fadpro_ihpe_check: 'folder',
  azure_epics_overdue: 'azure',
  hours_appropriation_watch: 'clock',
  ponto_abono_email: 'mail',
};

const statusMap = (automation: Automation): RoutineCardModel['status'] => (automation.is_enabled ? 'Ativo' : 'Pausado');

const formatDate = (value?: string | null) => {
  if (!value) return 'Não agendada';
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
};

const RoutinesPage: React.FC = () => {
  const [routines, setRoutines] = useState<RoutineCardModel[]>([]);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<{ title: string; description: string; cronExpression: string; estimatedDuration: string } | null>(null);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AutomationRun | null>(null);
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);

  const loadRoutines = async () => {
    const data = await listAutomations();
    const mapped: RoutineCardModel[] = data.map((automation) => ({
      id: String(automation.id),
      title: automation.name,
      iconType: iconMap[automation.key] || 'document',
      status: statusMap(automation),
      lastRun: formatDate(automation.last_run_at),
      lastRunStatus: automation.last_run_at ? 'success' : 'warning',
      nextRun: formatDate(automation.next_run_at),
    }));
    setRoutines(mapped);
  };

  useEffect(() => {
    loadRoutines();
    listAutomationRuns().then(setRuns);
  }, []);

  const filteredRoutines = routines.filter((r) => r.title.toLowerCase().includes(searchQuery.toLowerCase()));

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setIsGenerating(true);
    setAiSuggestion(null);
    await new Promise((resolve) => setTimeout(resolve, 800));
    setAiSuggestion({
      title: 'Rotina Automatizada (IA)',
      description: aiPrompt,
      cronExpression: '0 8 * * 1',
      estimatedDuration: '2 mins',
    });
    setIsGenerating(false);
  };

  const handleCreateFromAI = () => {
    if (!aiSuggestion) return;
    setRoutines((prev) => [
      {
        id: `ai-${Date.now()}`,
        title: aiSuggestion.title,
        iconType: 'document',
        status: 'Ativo',
        lastRun: 'Nunca',
        lastRunStatus: 'warning',
        nextRun: 'Agendado pelo CRON',
      },
      ...prev,
    ]);
    setIsModalOpen(false);
    setAiPrompt('');
    setAiSuggestion(null);
  };

  const handleRunNow = async (id: string) => {
    await runAutomation(Number(id), true);
    await loadRoutines();
    const updatedRuns = await listAutomationRuns();
    setRuns(updatedRuns);
  };

  const openRunModal = (run: AutomationRun) => {
    setSelectedRun(run);
    setIsRunModalOpen(true);
  };

  return (
    <AppShell>
      <div className="w-full">
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

        <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'flex flex-col gap-4'}>
          {filteredRoutines.map((routine) => (
            <div key={routine.id} className="bg-white overflow-hidden rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-200 flex flex-col h-full">
              <div className="p-5 flex justify-between items-start">
                <div className="flex gap-4">
                  <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <span className="material-symbols-outlined text-blue-600">description</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900 leading-snug">{routine.title}</h3>
                    <div className="mt-1">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        routine.status === 'Pausado'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                          routine.status === 'Pausado' ? 'bg-amber-500' : 'bg-emerald-500'
                        }`}></div>
                        {routine.status}
                      </span>
                    </div>
                  </div>
                </div>
                <button className="text-gray-400 hover:text-gray-500 transition-colors">
                  <span className="material-symbols-outlined">settings</span>
                </button>
              </div>

              <div className="px-5 py-3 bg-gray-50 border-t border-b border-gray-100 flex-grow">
                <div className="grid grid-cols-1 gap-2 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Última Execução</span>
                    <div className="flex items-center gap-1.5 font-medium text-gray-700">
                      <span className="material-symbols-outlined text-emerald-500 !text-[18px]">check_circle</span>
                      {routine.lastRun}
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500">Próxima Execução</span>
                    <div className="flex items-center gap-1.5 font-medium text-gray-700">
                      {routine.nextRun === 'Não agendada' ? (
                        <span className="text-gray-400 italic text-xs">Não agendada</span>
                      ) : (
                        <>
                          <span className="material-symbols-outlined text-blue-500 !text-[18px]">schedule</span>
                          {routine.nextRun}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-5 flex gap-3 mt-auto">
                <button
                  onClick={() => handleRunNow(routine.id)}
                  className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
                >
                  <span className="material-symbols-outlined">play_arrow</span>
                  Executar Agora
                </button>
                <button className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2 px-3 rounded-lg flex items-center justify-center transition-colors">
                  <span className="material-symbols-outlined">history</span>
                </button>
              </div>
            </div>
          ))}

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

        <section className="mt-10 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Últimas Execuções</h2>
            <p className="text-sm text-gray-500">Acompanhe as execuções mais recentes das rotinas.</p>
          </div>
          {runs.length === 0 ? (
            <div className="p-6 text-sm text-gray-500">Nenhuma execução registrada ainda.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-6 py-3 text-left font-semibold">Rotina</th>
                    <th className="px-6 py-3 text-left font-semibold">Status</th>
                    <th className="px-6 py-3 text-left font-semibold">Início</th>
                    <th className="px-6 py-3 text-left font-semibold">Fim</th>
                    <th className="px-6 py-3 text-left font-semibold">Resumo</th>
                    <th className="px-6 py-3 text-left font-semibold">Detalhes</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-gray-100">
                      <td className="px-6 py-3 text-gray-700 font-medium">{run.automation_name}</td>
                      <td className="px-6 py-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          run.status === 'success' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                        }`}>
                          {run.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-gray-500">{new Date(run.started_at).toLocaleString('pt-BR')}</td>
                      <td className="px-6 py-3 text-gray-500">{run.finished_at ? new Date(run.finished_at).toLocaleString('pt-BR') : '-'}</td>
                      <td className="px-6 py-3 text-gray-500">
                        <button
                          onClick={() => openRunModal(run)}
                          className="text-cyan-600 hover:text-cyan-700 font-semibold"
                        >
                          {run.summary_json?.message || 'Detalhes'}
                        </button>
                      </td>
                      <td className="px-6 py-3">
                        <button
                          onClick={() => openRunModal(run)}
                          className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-600 hover:bg-gray-50"
                        >
                          Ver detalhes
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

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

      {isRunModalOpen && selectedRun && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" aria-hidden="true">
              <div className="absolute inset-0 bg-gray-500 opacity-75" onClick={() => setIsRunModalOpen(false)}></div>
            </div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div className="hidden sm:block absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
                  onClick={() => setIsRunModalOpen(false)}
                >
                  <span className="sr-only">Close</span>
                  <X className="h-6 w-6" />
                </button>
              </div>

              <div>
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-2">
                  Execução: {selectedRun.automation_name}
                </h3>
                <div className="text-sm text-gray-500 space-y-1">
                  <p>Status: <span className="font-semibold text-gray-700">{selectedRun.status}</span></p>
                  <p>Início: {new Date(selectedRun.started_at).toLocaleString('pt-BR')}</p>
                  <p>Fim: {selectedRun.finished_at ? new Date(selectedRun.finished_at).toLocaleString('pt-BR') : '-'}</p>
                </div>
                <div className="mt-4">
                  <h4 className="text-sm font-bold text-gray-700 mb-2">Resumo</h4>
                  <pre className="bg-gray-50 border border-gray-200 rounded p-3 text-xs text-gray-700 whitespace-pre-wrap">
{JSON.stringify(selectedRun.summary_json, null, 2)}
                  </pre>
                </div>
                {selectedRun.error_text && (
                  <div className="mt-4">
                    <h4 className="text-sm font-bold text-red-600 mb-2">Erro</h4>
                    <pre className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700 whitespace-pre-wrap">
{selectedRun.error_text}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default RoutinesPage;
