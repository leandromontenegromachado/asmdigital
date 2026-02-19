import React, { useEffect, useMemo, useState } from 'react';
import { ChevronRight, Save, ArrowRight, Info, Plus, Trash2, Code, GripHorizontal, Building2, Server, Truck, Eye, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { getMapping, getMappingPreview, upsertMapping, MappingPreviewTicket } from '../api/mappings';
import { listConnectors, Connector as ApiConnector } from '../api/connectors';
import { AppShell } from '../components/AppShell';

enum RuleStatus {
  ACTIVE = 'ACTIVE',
  INACTIVE = 'INACTIVE',
}

const defaultMapping = {
  sources_order: ['custom_fields', 'tags', 'subject_regex'],
  custom_fields: {
    cliente: 'Cliente',
    sistema: 'Sistema',
    entrega: 'Entrega',
  },
  tags: {
    cliente: 'cliente',
    sistema: 'sistema',
    entrega: 'entrega',
  },
  subject_regex: {
    cliente: 'Cliente:\\s*([^|]+)',
    sistema: 'Sistema:\\s*([^|]+)',
    entrega: 'Entrega:\\s*([^|]+)',
  },
};

const defaultNormalization = {
  options: {
    trim: true,
    uppercase: false,
    dedupe: true,
  },
  dictionary: {
    cliente: {},
    sistema: {},
    entrega: {},
  },
};

const defaultRegexRule = {
  enabled: true,
  pattern: '^(SYS|LEG)-(\\d+)-?',
  replacement: '$2',
};

const MappingsPage: React.FC = () => {
  const [mapping, setMapping] = useState(defaultMapping);
  const [normalization, setNormalization] = useState(defaultNormalization);
  const [regexRule, setRegexRule] = useState(defaultRegexRule);
  const [saving, setSaving] = useState(false);
  const [connectors, setConnectors] = useState<ApiConnector[]>([]);
  const [selectedConnectorId, setSelectedConnectorId] = useState<number | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [tickets, setTickets] = useState<MappingPreviewTicket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string>('');
  const [regexValid, setRegexValid] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadMappings = async () => {
    const redmineFields = await getMapping('redmine_fields');
    const normalizationDict = await getMapping('normalization_dictionary');
    const regexRules = await getMapping('regex_rules');

    if (redmineFields?.rules_json) {
      setMapping({ ...defaultMapping, ...redmineFields.rules_json });
    }
    if (normalizationDict?.rules_json) {
      setNormalization({ ...defaultNormalization, ...normalizationDict.rules_json });
    }
    if (regexRules?.rules_json) {
      setRegexRule({ ...defaultRegexRule, ...regexRules.rules_json });
    }
  };

  useEffect(() => {
    loadMappings();
  }, []);

  useEffect(() => {
    const loadConnectors = async () => {
      const data = await listConnectors();
      setConnectors(data);
      if (data.length && !selectedConnectorId) {
        const first = data[0];
        setSelectedConnectorId(first.id);
        const projectIds = first.config_json?.project_ids || [];
        if (projectIds.length) {
          setSelectedProjectId(String(projectIds[0]));
        }
      }
    };
    loadConnectors();
  }, []);

  useEffect(() => {
    const loadPreview = async () => {
      if (!selectedConnectorId || !selectedProjectId || !regexValid) return;
      setPreviewLoading(true);
      const result = await getMappingPreview(selectedConnectorId, selectedProjectId, 5);
      setTickets(result.tickets);
      if (result.tickets.length && !selectedTicketId) {
        setSelectedTicketId(result.tickets[0].id);
      }
      setPreviewLoading(false);
    };
    const timeout = setTimeout(() => {
      loadPreview();
    }, 600);
    return () => clearTimeout(timeout);
  }, [selectedConnectorId, selectedProjectId, regexRule, mapping, normalization]);

  useEffect(() => {
    if (!regexRule.pattern) {
      setRegexValid(true);
      return;
    }
    try {
      new RegExp(regexRule.pattern);
      setRegexValid(true);
    } catch (err) {
      setRegexValid(false);
    }
  }, [regexRule.pattern]);

  const activeTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId) || tickets[0],
    [tickets, selectedTicketId]
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      await upsertMapping('redmine_fields', { rules_json: mapping });
      await upsertMapping('normalization_dictionary', { rules_json: normalization });
      await upsertMapping('regex_rules', { rules_json: regexRule });
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <a href="#" className="hover:text-primary-600 transition-colors">Configurações</a>
          <ChevronRight size={14} className="text-slate-400" />
          <a href="#" className="hover:text-primary-600 transition-colors">Redmine</a>
          <ChevronRight size={14} className="text-slate-400" />
          <span className="text-slate-800 font-medium">Mapeamento e Normalização</span>
        </div>
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div className="space-y-2 max-w-2xl">
                <h2 className="text-3xl font-black text-slate-900 tracking-tight">Mapeamento de Dados</h2>
                <p className="text-slate-500 text-base leading-relaxed">
                  Configure como os campos personalizados do Redmine são traduzidos para as entidades do sistema (Cliente, Sistema e Entrega). Utilize regras de Regex para limpar e padronizar os dados antes da ingestão.
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button className="px-4 py-2.5 rounded-lg border border-slate-300 text-slate-600 font-semibold text-sm hover:text-slate-800 hover:bg-slate-50 transition-all bg-white shadow-sm">
                  Cancelar
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-2.5 rounded-lg bg-primary-500 text-white font-bold text-sm shadow-md shadow-primary-500/20 hover:bg-primary-600 transition-all flex items-center gap-2"
                >
                  <Save size={18} />
                  {saving ? 'Salvando...' : 'Salvar Alterações'}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
              <div className="xl:col-span-8 space-y-6">
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
                    <MappingRow
                      icon={Building2}
                      targetLabel="Cliente"
                      sourceValue={mapping.custom_fields.cliente}
                      onChange={(value) => setMapping((prev) => ({ ...prev, custom_fields: { ...prev.custom_fields, cliente: value } }))}
                      sourceOptions={[
                        { value: 'Cliente', label: 'Custom Field: Nome do Cliente (CF_32)' },
                        { value: 'Project Name', label: 'Project Name' },
                      ]}
                    />

                    <div className="border-t border-slate-100" />

                    <MappingRow
                      icon={Server}
                      targetLabel="Sistema / Aplicação"
                      sourceValue={mapping.custom_fields.sistema}
                      onChange={(value) => setMapping((prev) => ({ ...prev, custom_fields: { ...prev.custom_fields, sistema: value } }))}
                      sourceOptions={[
                        { value: 'Sistema', label: 'Custom Field: Sistema Afetado (CF_12)' },
                        { value: 'Category', label: 'Category' },
                      ]}
                    />

                    <div className="border-t border-slate-100" />

                    <MappingRow
                      icon={Truck}
                      targetLabel="Entrega / Release"
                      sourceValue={mapping.custom_fields.entrega}
                      onChange={(value) => setMapping((prev) => ({ ...prev, custom_fields: { ...prev.custom_fields, entrega: value } }))}
                      sourceOptions={[
                        { value: 'Entrega', label: 'Target Version (Fixed Version)' },
                        { value: 'Milestone', label: 'Milestone' },
                      ]}
                    />
                  </div>
                </section>

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
                    <RuleItem
                      title="Remover Espaços (Trim)"
                      description="Remove espaços em branco no início e no fim do valor."
                      active={normalization.options.trim}
                      status={normalization.options.trim ? RuleStatus.ACTIVE : RuleStatus.INACTIVE}
                      onToggle={(val) => setNormalization((prev) => ({ ...prev, options: { ...prev.options, trim: val } }))}
                    />

                    <RuleItem
                      title="Converter para Maiúsculas"
                      description="Converte todos os caracteres para UPPERCASE. Útil para siglas de sistemas."
                      active={normalization.options.uppercase}
                      status={normalization.options.uppercase ? RuleStatus.ACTIVE : RuleStatus.INACTIVE}
                      onToggle={(val) => setNormalization((prev) => ({ ...prev, options: { ...prev.options, uppercase: val } }))}
                    />

                    <div className={`p-6 transition-colors border-l-4 ${regexRule.enabled ? 'bg-blue-50/30 border-l-primary-500' : 'border-l-transparent'}`}>
                      <div className="flex items-start gap-4">
                        <div className="mt-1">
                          <Toggle checked={regexRule.enabled} onChange={(val) => setRegexRule((prev) => ({ ...prev, enabled: val }))} />
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
                              <StatusBadge status={regexRule.enabled ? RuleStatus.ACTIVE : RuleStatus.INACTIVE} />
                            </div>
                          </div>

                          <p className="text-sm text-slate-500">
                            Aplica uma expressão regular para limpar prefixos de ID de sistemas legados.
                          </p>

                          {regexRule.enabled && (
                            <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                                <div className="relative">
                                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Find Pattern (Regex)</label>
                                  <input
                                    type="text"
                                    className={`w-full bg-white border rounded text-sm text-purple-700 font-mono font-medium px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none ${regexValid ? 'border-slate-300' : 'border-red-400'}`}
                                    value={regexRule.pattern}
                                    onChange={(e) => setRegexRule((prev) => ({ ...prev, pattern: e.target.value }))}
                                  />
                                  <span className={`absolute right-3 top-8 text-[10px] font-bold ${regexValid ? 'text-emerald-600' : 'text-red-600'}`}>{regexValid ? 'OK' : 'INVÁLIDO'}</span>
                                </div>
                                <div>
                                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">Replacement String</label>
                                  <input
                                    type="text"
                                    className="w-full bg-white border border-slate-300 rounded text-sm text-emerald-700 font-mono font-medium px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 outline-none"
                                    value={regexRule.replacement}
                                    onChange={(e) => setRegexRule((prev) => ({ ...prev, replacement: e.target.value }))}
                                  />
                                </div>
                              </div>

                              <div className="flex items-center gap-2 mt-3 p-2 bg-slate-100/50 rounded border border-slate-200/50">
                                <span className="text-xs text-slate-500 font-mono bg-white px-2 py-0.5 rounded border border-slate-200">Input: SYS-001-Beta</span>
                                <ArrowRight size={14} className="text-slate-400" />
                                <span className="text-xs text-slate-800 font-bold font-mono bg-white px-2 py-0.5 rounded border border-primary-200 shadow-sm">Output: 001Beta</span>
                              </div>
                              {!regexValid && (
                                <p className="text-xs text-red-600 mt-2">Regex inválida. Corrija o padrão para atualizar o preview.</p>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              <div className="xl:col-span-4">
                <div className="bg-slate-50 rounded-xl border border-slate-200 overflow-hidden flex flex-col h-auto min-h-[500px] sticky top-6 shadow-sm">
                  <div className="px-5 py-4 border-b border-slate-200 bg-white">
                    <div className="flex items-center gap-2 mb-3">
                      <Eye size={20} className="text-primary-500" />
                      <h3 className="text-lg font-bold text-slate-800">Preview em Tempo Real</h3>
                    </div>
                    <div className="space-y-3">
                      <label className="block">
                        <span className="text-xs text-slate-500 font-medium mb-1 block uppercase tracking-wide">Conector</span>
                        <select
                          className="w-full bg-white border border-slate-300 rounded-lg text-slate-700 text-sm px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 shadow-sm outline-none"
                          value={selectedConnectorId ?? ''}
                          onChange={(e) => setSelectedConnectorId(Number(e.target.value))}
                          disabled={previewLoading}
                        >
                          {connectors.map((connector) => (
                            <option key={connector.id} value={connector.id}>{connector.name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block">
                        <span className="text-xs text-slate-500 font-medium mb-1 block uppercase tracking-wide">Projeto</span>
                        <input
                          className="w-full bg-white border border-slate-300 rounded-lg text-slate-700 text-sm px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 shadow-sm outline-none"
                          value={selectedProjectId}
                          onChange={(e) => setSelectedProjectId(e.target.value)}
                          placeholder="ID do projeto"
                          disabled={previewLoading}
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-slate-500 font-medium mb-1 block uppercase tracking-wide">Ticket de Exemplo</span>
                        <select
                          className="w-full bg-white border border-slate-300 rounded-lg text-slate-700 text-sm px-3 py-2 focus:ring-1 focus:ring-primary-500 focus:border-primary-500 shadow-sm outline-none"
                          value={selectedTicketId}
                          onChange={(e) => setSelectedTicketId(e.target.value)}
                          disabled={previewLoading}
                        >
                          {tickets.map((ticket) => (
                            <option key={ticket.id} value={ticket.id}>{ticket.title}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  </div>

                  <div className="p-5 flex-1 flex flex-col gap-6">
                    {previewLoading ? (
                      <div className="space-y-4">
                        <div className="rounded-lg border border-slate-200 bg-white p-4 flex items-center gap-3 text-sm text-slate-500">
                          <span className="h-4 w-4 rounded-full border-2 border-slate-300 border-t-primary-500 animate-spin"></span>
                          Carregando preview...
                        </div>
                        <div className="rounded-lg border border-slate-200 bg-white p-4">
                          <div className="h-3 w-24 bg-slate-100 rounded mb-3"></div>
                          <div className="h-8 w-full bg-slate-100 rounded"></div>
                        </div>
                        <div className="rounded-lg border border-slate-200 bg-white p-4">
                          <div className="h-3 w-24 bg-slate-100 rounded mb-3"></div>
                          <div className="h-8 w-full bg-slate-100 rounded"></div>
                        </div>
                        <div className="rounded-lg border border-slate-200 bg-white p-4">
                          <div className="h-3 w-24 bg-slate-100 rounded mb-3"></div>
                          <div className="h-8 w-full bg-slate-100 rounded"></div>
                        </div>
                      </div>
                    ) : activeTicket ? (
                      <>
                        <PreviewField
                          label="Cliente"
                          raw={activeTicket.cliente.raw || 'null'}
                          processed={activeTicket.cliente.processed || '-- Empty --'}
                          badge={activeTicket.cliente.source || undefined}
                          isValid={!activeTicket.cliente.is_warning}
                        />

                        <PreviewField
                          label="Sistema"
                          raw={activeTicket.sistema.raw || 'null'}
                          processed={activeTicket.sistema.processed || '-- Empty --'}
                          badge={activeTicket.sistema.source || undefined}
                          isValid={!activeTicket.sistema.is_warning}
                        />

                        <PreviewField
                          label="Entrega"
                          raw={activeTicket.entrega.raw || 'null'}
                          processed={activeTicket.entrega.processed || '-- Empty --'}
                          badge={activeTicket.entrega.source || undefined}
                          isValid={!activeTicket.entrega.is_warning}
                        />
                      </>
                    ) : (
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
                    )}
                  </div>

                  <div className="bg-slate-100/50 p-4 border-t border-slate-200 text-center">
                    <p className="text-xs text-slate-500 mb-3">Última sincronização: 5 min atrás</p>
                    <button className="w-full py-2.5 rounded border border-slate-200 text-primary-600 text-xs font-bold hover:bg-white hover:shadow-sm transition-all uppercase tracking-wide bg-white flex items-center justify-center gap-2">
                      <RefreshCw size={14} />
                      Recarregar Dados
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
    </AppShell>
  );
};

const MappingRow: React.FC<{
  icon: React.ElementType;
  targetLabel: string;
  sourceValue: string;
  onChange: (value: string) => void;
  sourceOptions: { value: string; label: string }[];
}> = ({ icon: Icon, targetLabel, sourceValue, onChange, sourceOptions }) => (
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
        value={sourceValue}
        onChange={(e) => onChange(e.target.value)}
      >
        {sourceOptions.map((opt) => (
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
  onToggle: (value: boolean) => void;
}> = ({ title, description, active, status, onToggle }) => (
  <div className="p-6 flex items-start gap-4 hover:bg-slate-50 transition-colors">
    <div className="mt-1">
      <Toggle checked={active} onChange={onToggle} />
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
      {isActive ? 'ACTIVE' : 'INACTIVE'}
    </span>
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
      {isValid ? <CheckCircle2 size={16} className="text-emerald-500" /> : <AlertTriangle size={16} className="text-amber-500" />}
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

export default MappingsPage;
