import React, { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../components/AppShell';
import ConnectorCard, { ConnectorCardModel, ConnectorStatus } from '../components/connectors/ConnectorCard';
import ConnectorEditor from '../components/connectors/ConnectorEditor';
import { createConnector, listConnectors, testConnector, updateConnector, Connector as ApiConnector } from '../api/connectors';

interface EditorConfig {
  urlLabel: string;
  urlValue: string;
  tokenLabel: string;
  tokenValue: string;
  projectLabel: string;
  projectValue: string;
  projects: string[];
  warning?: string;
}

interface UiConnector extends ConnectorCardModel {
  connectorId?: number;
  type?: string;
  isNew?: boolean;
  isActive?: boolean;
  config?: EditorConfig;
  configJson?: Record<string, any>;
}

const CONNECTOR_LIBRARY: Record<string, { description: string; logoUrl: string; logoAlt: string }> = {
  redmine: {
    description: 'Gestão de projetos e rastreamento de issues.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAOA-Ku2pJnqI-zFvyJgy0G1nAhtviNe5_8Lhs_ii1LCmFFl5881PPaD6dYjiIv482-X_ek3zi6xvDqP6Cjv8avSvW-O-5BK9rRy7KN_XEgRhJ_0pJi9_eMdi-dqG5b2j6CsHnQA4qR3yEmvjWVQIcf2OnO7gyU5etmlzOMgqu68NDXelAVlupfa_jVgbTOMAlsXXHkbJo93-6GyqJ4d10SgyezHktdw9MZAeMRZiw_gcSkbT_k5H6Xn4JlLi1Emy-a7Ld0uKWVDO0',
    logoAlt: 'Redmine Logo',
  },
  teams: {
    description: 'Notificações e alertas em canais de equipe.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuACz0HpwacV0IQcQzQXldx5HDpt1Nr_KZ5nhkAU7ZS2Pqj8cjEL4rOpegyYL57wISK6ZvIAwsDyy1tuMVs3eZ7wmHP-XcEbWAYIlT1eCtZbmYHG6qN_vLmFTHtwn0x_P6BrRphLZOa1aBwlB_6ZAprhjRIq1oDi6ZNpDgR5lYiOt5aJLD4TDn4ABfwP9mzBaDPJG810qmgS-WeA3jrXkxja_5ed6A5oAbJC79CS9vOMvZb9LChA9XyVsW_eBtloUnK1jt8GdN3Nn6E',
    logoAlt: 'Teams Logo',
  },
  azure: {
    description: 'Build, test, and deploy with CI/CD.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBg0qoLaqqvfGSo1HhJLz0jc9LT_Nx2jbPjdmc0idn96w_6jGJomddFRNptlEveFcrYuEnpnpt64Rk0ktuV9DF0I0awHVDxq-5UfhJ74GT_FZsgz2vMsS-_3OOCQxyR9i75JzDdimq6qZf_YcOOENWMVWU39TiyO7_Po3zuMcbIwwpMVFTUR4av_GU2x_gAI8L6RR6I3g23Cnx_hhxHKUXr3vxyGL7n7Ml4BcNUkhSDENowlfUcctskZGl1s7vvJCZ9ZK_cMWpYEVs',
    logoAlt: 'Azure DevOps Logo',
  },
  slack: {
    description: 'Colaboração e bots de automação.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBQzJbfgwcPtoAvuaLWInXEi_oHdXc6bbb6ZrtSawPUAdH7niJkalJ186-uxmsYqJ2b48fouJb0J-NMOX_SyF93KbAJAsZP6xHND_WvXHzE9Xk0b9KvqhEL4vZVX0hyG3wJtjCH0YmC7bqrtQMW6cRkT4JsokZRfgezKBSKP0KcnqKTI2GLpe6l4glNLAJQWbXy9zeUeYLDjLBCjl6lsyCRccrBXyNK1iBbWBPcltO69pVaZUzLVJUKShQZ0oUhUDsAoeU-7hKcFPk',
    logoAlt: 'Slack Logo',
  },
  jira: {
    description: 'Rastreamento de projetos ágeis.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuD8Zkdq7MXR17vOUCJFx4uKYnVz87obYjTYmN-td7r12-sEZmYcJR1G0TLwiHVUHOVMG6ZVjwvdpVsrnmrjbBIg4lVLDM9iXFblGDgTa3IexF_NI5owvSFEK7vQId6-l_m4wtrLK7eRiwR78ZdBuyXsxxQ4S7Z0mdn22LrxiDtoJNiUriLCJeIvfQVXh5BQYHDitBIlxYbyFm2bUE_xJIycJ0slvGk2FIN6d1AnbfN3niGUJ43_UWBajsX_CzeS4eR_eEe7gDhSQrc',
    logoAlt: 'Jira Logo',
  },
};

const buildEditorConfig = (connector?: ApiConnector): EditorConfig => {
  const config = connector?.config_json || {};
  const projects = Array.isArray(config.project_ids) ? config.project_ids : [];
  return {
    urlLabel: 'Endpoint URL',
    urlValue: config.base_url || '',
    tokenLabel: 'API Key',
    tokenValue: config.api_key || '',
    projectLabel: 'Projetos',
    projectValue: projects.join(', '),
    projects,
    warning: config.warning,
  };
};

const mapConnector = (connector: ApiConnector): UiConnector => {
  const library = CONNECTOR_LIBRARY[connector.type] || {
    description: 'Integração de dados e automações.',
    logoUrl: '',
    logoAlt: connector.type,
  };
  const status: ConnectorStatus = connector.is_active ? 'connected' : 'inactive';
  return {
    id: String(connector.id),
    connectorId: connector.id,
    type: connector.type,
    name: connector.name,
    description: library.description,
    logoUrl: library.logoUrl,
    logoAlt: library.logoAlt,
    status,
    isActive: connector.is_active,
    syncTime: connector.config_json?.last_sync,
    errorMessage: connector.config_json?.error_message,
    errorCode: connector.config_json?.error_code,
    configJson: connector.config_json,
  };
};

const ConnectorsPage: React.FC = () => {
  const [connectors, setConnectors] = useState<UiConnector[]>([]);
  const [loading, setLoading] = useState(true);

  const loadConnectors = async () => {
    setLoading(true);
    try {
      const data = await listConnectors();
      setConnectors(data.map(mapConnector));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConnectors();
  }, []);

  const handleConfigure = (id: string) => {
    setConnectors((prev) =>
      prev.map((c) => {
        if (c.id === id) {
          return {
            ...c,
            status: 'editing',
            config: buildEditorConfig({
              id: c.connectorId || 0,
              type: c.type || 'redmine',
              name: c.name,
              config_json: c.configJson || {},
              is_active: c.isActive ?? true,
            } as ApiConnector),
          };
        }
        return c.status === 'editing' ? { ...c, status: c.isActive ? 'connected' : 'inactive' } : c;
      })
    );
  };

  const handleCancel = (id: string) => {
    setConnectors((prev) => prev.filter((c) => !(c.isNew && c.id === id)).map((c) => {
      if (c.id !== id) return c;
      return { ...c, status: c.isActive ? 'connected' : 'inactive' };
    }));
  };

  const handleSave = async (connector: UiConnector, config: EditorConfig, name: string, type: string) => {
    const payload = {
      base_url: config.urlValue,
      api_key: config.tokenValue,
      project_ids: config.projectValue.split(',').map((p) => p.trim()).filter(Boolean),
    };

    if (connector.isNew) {
      await createConnector({
        name: name || connector.name || 'Redmine',
        type: type || connector.type || 'redmine',
        config_json: payload,
        is_active: true,
      });
      await loadConnectors();
      return;
    }

    if (connector.connectorId) {
      await updateConnector(connector.connectorId, { name, type, config_json: payload });
      await testConnector(connector.connectorId);
      await loadConnectors();
    }
  };

  const addNewConnector = () => {
    const newId = `new-${Date.now()}`;
    setConnectors((prev) => [
      {
        id: newId,
        name: 'Redmine',
        description: CONNECTOR_LIBRARY.redmine.description,
        logoUrl: CONNECTOR_LIBRARY.redmine.logoUrl,
        logoAlt: CONNECTOR_LIBRARY.redmine.logoAlt,
        status: 'editing',
        isNew: true,
        type: 'redmine',
        isActive: true,
        config: buildEditorConfig(),
      },
      ...prev,
    ]);
  };

  const activeConnectors = useMemo(() => connectors, [connectors]);

  return (
    <AppShell>
        <nav aria-label="Breadcrumb" className="flex mb-6">
          <ol className="inline-flex items-center space-x-1 md:space-x-2 rtl:space-x-reverse">
            <li className="inline-flex items-center">
              <a className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white transition-colors" href="#">
                <span className="material-symbols-outlined !text-[18px] mr-1">home</span>
                Home
              </a>
            </li>
            <li>
              <div className="flex items-center">
                <span className="material-symbols-outlined !text-[16px] text-slate-400 dark:text-[#586e7a]">chevron_right</span>
                <a className="ms-1 text-sm font-medium text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white md:ms-2 transition-colors" href="#">Configurações</a>
              </div>
            </li>
            <li aria-current="page">
              <div className="flex items-center">
                <span className="material-symbols-outlined !text-[16px] text-slate-400 dark:text-[#586e7a]">chevron_right</span>
                <span className="ms-1 text-sm font-medium text-slate-900 dark:text-white md:ms-2">Conectores de Dados</span>
              </div>
            </li>
          </ol>
        </nav>

        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight text-slate-900 dark:text-white mb-2">Conectores de Dados</h1>
            <p className="text-slate-500 dark:text-[#92b7c9] text-lg max-w-2xl leading-relaxed">
              Gerencie as integrações de API para automação de relatórios, criação de tickets e envio de alertas.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative w-full md:w-auto group">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-[#92b7c9] group-focus-within:text-primary">
                <span className="material-symbols-outlined">filter_list</span>
              </span>
              <select className="h-10 w-full md:w-48 appearance-none rounded-lg border border-slate-200 dark:border-[#233c48] bg-white dark:bg-[#192b33] pl-10 pr-8 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none cursor-pointer transition-shadow">
                <option>Todos os tipos</option>
                <option>Gestão de Projetos</option>
                <option>Comunicação</option>
                <option>ERP/Financeiro</option>
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-slate-400">
                <span className="material-symbols-outlined !text-[18px]">expand_more</span>
              </span>
            </div>
            <button
              onClick={addNewConnector}
              className="flex items-center gap-2 bg-primary hover:bg-sky-600 text-white px-4 h-10 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-sky-500/20 active:scale-95 transform"
            >
              <span className="material-symbols-outlined !text-[20px]">add</span>
              <span>Novo Conector</span>
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-slate-500">Carregando conectores...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {activeConnectors.map((connector) => (
              connector.status === 'editing' && connector.config ? (
                <ConnectorEditor
                  key={connector.id}
                  name={connector.name}
                  type={connector.type || 'redmine'}
                  description={connector.description}
                  logoUrl={connector.logoUrl}
                  logoAlt={connector.logoAlt}
                  config={connector.config}
                  onCancel={() => handleCancel(connector.id)}
                  onSave={(cfg, name, type) => handleSave(connector, cfg, name, type)}
                />
              ) : (
                <ConnectorCard
                  key={connector.id}
                  connector={connector}
                  onConfigure={handleConfigure}
                />
              )
            ))}
          </div>
        )}
    </AppShell>
  );
};

export default ConnectorsPage;
