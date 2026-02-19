import React from 'react';
import { 
  Settings, 
  Play, 
  History, 
  FileText, 
  Folder, 
  Cloud, 
  Clock, 
  Mail,
  CheckCircle2,
  AlertCircle,
  Clock3
} from 'lucide-react';
import { Routine, RoutineStatus } from '../types';

interface RoutineCardProps {
  routine: Routine;
}

const RoutineCard: React.FC<RoutineCardProps> = ({ routine }) => {
  
  const getIcon = () => {
    switch (routine.iconType) {
      case 'document': return <FileText className="h-6 w-6 text-blue-600" />;
      case 'folder': return <Folder className="h-6 w-6 text-amber-600" />;
      case 'azure': return <Cloud className="h-6 w-6 text-indigo-600" />;
      case 'clock': return <Clock className="h-6 w-6 text-purple-600" />;
      case 'mail': return <Mail className="h-6 w-6 text-emerald-600" />;
      default: return <FileText className="h-6 w-6 text-gray-600" />;
    }
  };

  const getIconBg = () => {
    switch (routine.iconType) {
      case 'document': return 'bg-blue-100';
      case 'folder': return 'bg-amber-100';
      case 'azure': return 'bg-indigo-100';
      case 'clock': return 'bg-purple-100';
      case 'mail': return 'bg-emerald-100';
      default: return 'bg-gray-100';
    }
  };

  const isPaused = routine.status === RoutineStatus.PAUSED;

  return (
    <div className="bg-white overflow-hidden rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-200 flex flex-col h-full">
      {/* Card Header */}
      <div className="p-5 flex justify-between items-start">
        <div className="flex gap-4">
          <div className={`h-12 w-12 rounded-full ${getIconBg()} flex items-center justify-center flex-shrink-0`}>
            {getIcon()}
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900 leading-snug">{routine.title}</h3>
            <div className="mt-1">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                isPaused 
                  ? 'bg-amber-100 text-amber-800' 
                  : 'bg-emerald-100 text-emerald-800'
              }`}>
                <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
                  isPaused ? 'bg-amber-500' : 'bg-emerald-500'
                }`}></div>
                {routine.status}
              </span>
            </div>
          </div>
        </div>
        <button className="text-gray-400 hover:text-gray-500 transition-colors">
          <Settings className="h-5 w-5" />
        </button>
      </div>

      {/* Info Block */}
      <div className="px-5 py-3 bg-gray-50 border-t border-b border-gray-100 flex-grow">
        <div className="grid grid-cols-1 gap-2 text-sm">
          <div className="flex justify-between items-center">
            <span className="text-gray-500">Última Execução</span>
            <div className="flex items-center gap-1.5 font-medium text-gray-700">
               {routine.lastRunStatus === 'success' ? (
                 <CheckCircle2 className="h-4 w-4 text-emerald-500" />
               ) : (
                 <AlertCircle className="h-4 w-4 text-red-500" />
               )}
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
                   <Clock3 className="h-4 w-4 text-blue-500" />
                   {routine.nextRun}
                 </>
               )}
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="p-5 flex gap-3 mt-auto">
        <button className="flex-1 bg-cyan-500 hover:bg-cyan-600 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500">
          <Play className="h-4 w-4 fill-current" />
          Executar Agora
        </button>
        <button className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2 px-3 rounded-lg flex items-center justify-center transition-colors">
          <History className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
};

export default RoutineCard;
