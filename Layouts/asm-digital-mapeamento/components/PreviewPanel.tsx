import React, { useState } from 'react';
import { Eye, CheckCircle2, AlertTriangle, RefreshCw, Info } from 'lucide-react';
import { TicketData } from '../types';

export const PreviewPanel: React.FC = () => {
  const [selectedTicketId, setSelectedTicketId] = useState<string>('48291');

  // Mock data to simulate real-time updates
  const tickets: Record<string, TicketData> = {
    '48291': {
      id: '48291',
      title: '#48291 - Erro no Login (SaaS)',
      client: { raw: '"  Acme Corp  "', processed: '"Acme Corp"', ruleApplied: 'Trim' },
      system: { raw: '"SYS-420-Prod"', processed: '"420Prod"', ruleApplied: 'Regex' },
      delivery: { raw: null, processed: null, isWarning: true }
    },
    '48292': {
      id: '48292',
      title: '#48292 - Atualização de Banco',
      client: { raw: '"Globex "', processed: '"Globex"', ruleApplied: 'Trim' },
      system: { raw: '"LEG-88-Fin"', processed: '"88Fin"', ruleApplied: 'Regex' },
      delivery: { raw: '"v1.2"', processed: '"v1.2"', isWarning: false }
    }
  };

  const activeTicket = tickets[selectedTicketId] || tickets['48291'];

  return (
    <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden flex flex-col h-auto min-h-[500px] sticky top-6 shadow-sm">
      <div className="px-5 py-4 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2 mb-3">
          <Eye size={20} className="text-primary-500" />
          <h3 className="text-lg font-bold text-slate-800">Preview em Tempo Real</h3>
        </div>
        <label className="block">
          <span className="text-xs text-slate-500 font-medium mb-1 block uppercase tracking-wide">Ticket de Exemplo</span>
          <select
            className="w-full bg-white border border-slate-300 rounded-lg text-slate-700 text-sm px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 shadow-sm outline-none"
            value={selectedTicketId}
            onChange={(e) => setSelectedTicketId(e.target.value)}
          >
            <option value="48291">#48291 - Erro no Login (SaaS)</option>
            <option value="48292">#48292 - Atualização de Banco</option>
          </select>
        </label>
      </div>

      <div className="p-5 flex-1 flex flex-col gap-6">
        {/* Field 1: Cliente */}
        <PreviewField
          label="Cliente"
          raw={activeTicket.client.raw}
          processed={activeTicket.client.processed}
          badge={activeTicket.client.ruleApplied}
          isValid={true}
        />

        {/* Field 2: Sistema */}
        <PreviewField
          label="Sistema"
          raw={activeTicket.system.raw}
          processed={activeTicket.system.processed}
          badge={activeTicket.system.ruleApplied}
          isValid={true}
        />

        {/* Field 3: Entrega (Error/Warning State) */}
        <div className="space-y-2">
          <div className="flex justify-between items-end">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Entrega</span>
            <AlertTriangle size={16} className="text-amber-500" />
          </div>
          <div className="bg-white rounded border border-slate-200 p-3 space-y-2 relative overflow-hidden shadow-sm ring-1 ring-amber-100">
             <div className="absolute right-0 top-0 p-1">
                <span className="h-2 w-2 rounded-full bg-amber-500 block"></span>
            </div>
            <div className="flex justify-between text-xs items-center border-b border-slate-100 pb-2">
              <span className="text-red-600 font-mono italic">Raw: null</span>
            </div>
            <div className="flex justify-between text-sm items-center pt-1">
              <span className="text-slate-400 font-mono italic">-- Empty --</span>
            </div>
          </div>
          <p className="text-xs text-amber-600 mt-1 flex items-center gap-1 font-medium">
            <Info size={12} />
            Nenhuma regra aplicada a valores nulos.
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-slate-100/50 p-4 border-t border-slate-200 text-center">
        <p className="text-xs text-slate-500 mb-3">Última sincronização: 5 min atrás</p>
        <button className="w-full py-2.5 rounded border border-slate-200 text-primary-600 text-xs font-bold hover:bg-white hover:shadow-sm transition-all uppercase tracking-wide bg-white flex items-center justify-center gap-2">
           <RefreshCw size={14} />
           Recarregar Dados
        </button>
      </div>
    </div>
  );
};

const PreviewField: React.FC<{
  label: string;
  raw: string;
  processed: string;
  badge?: string;
  isValid?: boolean;
}> = ({ label, raw, processed, badge, isValid }) => (
  <div className="space-y-2">
    <div className="flex justify-between items-end">
      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{label}</span>
      {isValid && <CheckCircle2 size={16} className="text-emerald-500" />}
    </div>
    <div className="bg-white rounded border border-slate-200 p-3 space-y-2 shadow-sm">
      <div className="flex justify-between text-xs items-center border-b border-slate-100 pb-2">
        <span className="text-red-600 font-mono">Raw: {raw}</span>
      </div>
      <div className="flex justify-between text-sm items-center pt-1">
        <span className="text-emerald-600 font-mono font-bold">{processed}</span>
        {badge && (
          <span className="text-[10px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 font-medium">
            {badge}
          </span>
        )}
      </div>
    </div>
  </div>
);
