import React, { useState } from 'react';
import { ArrowRight, Info, Plus, Trash2, Code, GripHorizontal, Building2, Server, Truck } from 'lucide-react';
import { RuleStatus } from '../types';

export const MappingPanel: React.FC = () => {
  const [regexEnabled, setRegexEnabled] = useState(true);

  return (
    <div className="space-y-6">
      {/* Section 1: Campos de Origem */}
      <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="bg-blue-100 p-1.5 rounded-md">
              <GripHorizontal size={18} className="text-blue-600" />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Campos de Origem</h3>
          </div>
          <span className="bg-blue-50 text-blue-700 text-xs font-bold px-2.5 py-1 rounded border border-blue-100">
            3 Mapeados
          </span>
        </div>

        <div className="p-6 space-y-6">
          {/* Mapping Item 1 */}
          <MappingRow
            icon={Building2}
            targetLabel="Cliente"
            sourceValue="cf_32"
            sourceOptions={[
              { value: "cf_32", label: "Custom Field: Nome do Cliente (CF_32)" },
              { value: "cf_99", label: "Project Name" }
            ]}
          />

          <div className="border-t border-slate-100" />

          {/* Mapping Item 2 */}
          <MappingRow
            icon={Server}
            targetLabel="Sistema / Aplicação"
            sourceValue="cf_12"
            sourceOptions={[
              { value: "cf_12", label: "Custom Field: Sistema Afetado (CF_12)" },
              { value: "cat", label: "Category" }
            ]}
          />

          <div className="border-t border-slate-100" />

          {/* Mapping Item 3 */}
          <MappingRow
            icon={Truck}
            targetLabel="Entrega / Release"
            sourceValue="ver"
            sourceOptions={[
              { value: "ver", label: "Target Version (Fixed Version)" },
              { value: "milestone", label: "Milestone" }
            ]}
          />
        </div>
      </section>

      {/* Section 2: Regras de Normalização */}
      <section className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="bg-purple-100 p-1.5 rounded-md">
              <Code size={18} className="text-purple-600" />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Regras de Normalização</h3>
          </div>
          <button className="flex items-center text-xs font-bold text-primary-600 hover:text-primary-700 transition-colors">
            <Plus size={16} className="mr-1" />
            ADICIONAR REGRA
          </button>
        </div>

        <div className="divide-y divide-slate-100">
          {/* Rule 1: Trim */}
          <RuleItem
            title="Remover Espaços (Trim)"
            description="Remove espaços em branco no início e no fim do valor."
            active={true}
            status={RuleStatus.ACTIVE}
          />

          {/* Rule 2: Uppercase */}
          <RuleItem
            title="Converter para Maiúsculas"
            description="Converte todos os caracteres para UPPERCASE. Útil para siglas de sistemas."
            active={false}
            status={RuleStatus.INACTIVE}
          />

          {/* Rule 3: Regex (Expanded) */}
          <div className={`p-6 transition-colors border-l-4 ${regexEnabled ? 'bg-blue-50/30 border-l-primary-500' : 'border-l-transparent'}`}>
            <div className="flex items-start gap-4">
              <div className="mt-1">
                <Toggle checked={regexEnabled} onChange={setRegexEnabled} />
              </div>
              <div className="flex-1 space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-slate-800">Substituição Regex</h4>
                    <span className="bg-slate-100 text-slate-500 p-0.5 rounded">
                      <Code size={14} />
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button className="text-slate-400 hover:text-red-500 transition-colors">
                      <Trash2 size={18} />
                    </button>
                    <StatusBadge status={regexEnabled ? RuleStatus.ACTIVE : RuleStatus.INACTIVE} />
                  </div>
                </div>

                <p className="text-sm text-slate-500">
                  Aplica uma expressão regular para limpar prefixos de ID de sistemas legados.
                </p>

                {regexEnabled && (
                  <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      <div className="relative">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Find Pattern (Regex)</label>
                        <input
                          type="text"
                          className="w-full bg-white border border-slate-300 rounded text-sm text-purple-700 font-mono font-medium px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none"
                          defaultValue="^(SYS|LEG)-(\d+)-?"
                        />
                        <span className="absolute right-3 top-8 text-[10px] font-bold text-emerald-600">OK</span>
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Replacement String</label>
                        <input
                          type="text"
                          className="w-full bg-white border border-slate-300 rounded text-sm text-emerald-700 font-mono font-medium px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none"
                          defaultValue="$2"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mt-3 p-2 bg-slate-100/50 rounded border border-slate-200/50">
                      <span className="text-xs text-slate-500 font-mono bg-white px-2 py-0.5 rounded border border-slate-200">Input: SYS-001-Beta</span>
                      <ArrowRight size={14} className="text-slate-400" />
                      <span className="text-xs text-slate-800 font-bold font-mono bg-white px-2 py-0.5 rounded border border-primary-200 shadow-sm">Output: 001Beta</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </section>
    </div>
  );
};

// Sub-components for better organization

const MappingRow: React.FC<{
  icon: React.ElementType;
  targetLabel: string;
  sourceValue: string;
  sourceOptions: { value: string; label: string }[];
}> = ({ icon: Icon, targetLabel, sourceValue, sourceOptions }) => (
  <div className="grid md:grid-cols-[1fr_40px_1fr] gap-4 items-center">
    <div>
      <label className="block text-sm font-medium text-slate-500 mb-1.5">Campo Destino (Interno)</label>
      <div className="h-11 w-full rounded-lg bg-slate-50 border border-slate-200 flex items-center px-4 text-slate-500 font-medium select-none cursor-not-allowed">
        <Icon size={18} className="mr-3 text-slate-400" />
        {targetLabel}
      </div>
    </div>
    <div className="hidden md:flex justify-center pt-6">
      <ArrowRight className="text-primary-500" />
    </div>
    <div>
      <label className="block mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-700">Origem Redmine</span>
        <Info size={14} className="text-slate-400 cursor-help" />
      </label>
      <select
        className="w-full h-11 bg-white border border-slate-300 rounded-lg text-slate-900 text-sm px-3 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none shadow-sm"
        defaultValue={sourceValue}
      >
        {sourceOptions.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  </div>
);

const RuleItem: React.FC<{
  title: string;
  description: string;
  active: boolean;
  status: RuleStatus;
}> = ({ title, description, active, status }) => (
  <div className="p-6 flex items-start gap-4 hover:bg-slate-50 transition-colors">
    <div className="mt-1">
      <Toggle checked={active} />
    </div>
    <div className="flex-1">
      <div className="flex justify-between items-center mb-1">
        <h4 className="text-sm font-semibold text-slate-800">{title}</h4>
        <StatusBadge status={status} />
      </div>
      <p className="text-sm text-slate-500">{description}</p>
    </div>
  </div>
);

const Toggle: React.FC<{ checked?: boolean; onChange?: (checked: boolean) => void }> = ({ checked = false, onChange }) => (
  <label className="relative inline-flex items-center cursor-pointer">
    <input type="checkbox" className="sr-only peer" checked={checked} onChange={(e) => onChange && onChange(e.target.checked)} />
    <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500"></div>
  </label>
);

const StatusBadge: React.FC<{ status: RuleStatus }> = ({ status }) => {
  const isActive = status === RuleStatus.ACTIVE;
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider border ${
      isActive 
        ? 'text-emerald-600 bg-emerald-50 border-emerald-100' 
        : 'text-slate-500 bg-slate-100 border-slate-200'
    }`}>
      {status}
    </span>
  );
};
