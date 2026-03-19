import React, { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Connector, listConnectors } from '../api/connectors';
import { AzureDevOpsSnapshot, getAzureDevOpsSnapshot } from '../api/azureDevops';
import { me } from '../api/auth';

type SectorPreset = {
  id: string;
  name: string;
  project: string;
  team: string;
  areaPath: string;
  iterationPath: string;
  top: string;
};

const AzureBoardsPage: React.FC = () => {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [connectorId, setConnectorId] = useState('');
  const [project, setProject] = useState('');
  const [team, setTeam] = useState('');
  const [areaPath, setAreaPath] = useState('');
  const [iterationPath, setIterationPath] = useState('');
  const [top, setTop] = useState('200');
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<AzureDevOpsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [presetName, setPresetName] = useState('');
  const [selectedPresetId, setSelectedPresetId] = useState('');
  const [presets, setPresets] = useState<SectorPreset[]>([]);

  const storageKey = useMemo(() => `asm_azure_sector_filters:${userId ?? 'anon'}`, [userId]);

  useEffect(() => {
    const load = async () => {
      const [all, user] = await Promise.all([listConnectors(), me().catch(() => null)]);
      const azure = all.filter((item) => ['azure', 'azure_devops', 'azure-devops'].includes(item.type));
      setConnectors(azure);
      if (user?.id) setUserId(Number(user.id));
      if (azure.length > 0) {
        setConnectorId(String(azure[0].id));
        const firstProject = Array.isArray(azure[0].config_json?.project_ids) ? azure[0].config_json.project_ids[0] : '';
        if (firstProject) setProject(String(firstProject));
      }
    };
    load();
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) {
        setPresets([]);
        return;
      }
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        setPresets([]);
        return;
      }
      setPresets(
        parsed
          .filter((item) => item && typeof item === 'object')
          .map((item) => ({
            id: String(item.id || `${Date.now()}-${Math.random()}`),
            name: String(item.name || 'Setor'),
            project: String(item.project || ''),
            team: String(item.team || ''),
            areaPath: String(item.areaPath || ''),
            iterationPath: String(item.iterationPath || ''),
            top: String(item.top || '200'),
          })),
      );
    } catch {
      setPresets([]);
    }
  }, [storageKey]);

  const persistPresets = (next: SectorPreset[]) => {
    setPresets(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  };

  const applyPreset = (id: string) => {
    setSelectedPresetId(id);
    const selected = presets.find((item) => item.id === id);
    if (!selected) return;
    setPresetName(selected.name);
    setProject(selected.project);
    setTeam(selected.team);
    setAreaPath(selected.areaPath);
    setIterationPath(selected.iterationPath);
    setTop(selected.top);
  };

  const savePreset = () => {
    const name = presetName.trim() || `Setor ${presets.length + 1}`;
    const data: SectorPreset = {
      id: selectedPresetId || `${Date.now()}`,
      name,
      project: project.trim(),
      team: team.trim(),
      areaPath: areaPath.trim(),
      iterationPath: iterationPath.trim(),
      top: top.trim() || '200',
    };
    const next = selectedPresetId
      ? presets.map((item) => (item.id === selectedPresetId ? data : item))
      : [...presets, data];
    persistPresets(next);
    setSelectedPresetId(data.id);
    setPresetName(name);
  };

  const deletePreset = () => {
    if (!selectedPresetId) return;
    const next = presets.filter((item) => item.id !== selectedPresetId);
    persistPresets(next);
    setSelectedPresetId('');
    setPresetName('');
  };

  const byState = useMemo(() => Object.entries(snapshot?.totals.by_state || {}), [snapshot]);
  const pbiWithoutTaskByUser = useMemo(() => snapshot?.diagnostics?.pbi_without_task?.users || [], [snapshot]);
  const tasksWithoutHoursByUser = useMemo(() => snapshot?.diagnostics?.tasks_without_hours?.users || [], [snapshot]);

  const handleQuery = async () => {
    if (!connectorId) {
      setError('Selecione um conector Azure DevOps.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getAzureDevOpsSnapshot(Number(connectorId), {
        project: project.trim() || undefined,
        team: team.trim() || undefined,
        area_path: areaPath.trim() || undefined,
        iteration_path: iterationPath.trim() || undefined,
        top: Number(top) > 0 ? Number(top) : 200,
      });
      setSnapshot(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao consultar Azure DevOps.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">Azure DevOps - Quadro do Setor</h1>
          <p className="mt-1 text-sm text-gray-500">Consulte status, horas e vinculo de epico dos PBIs e tarefas.</p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <select className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={connectorId} onChange={(e) => setConnectorId(e.target.value)}>
              {connectors.length === 0 && <option value="">Nenhum conector Azure</option>}
              {connectors.map((item) => (
                <option key={item.id} value={String(item.id)}>
                  #{item.id} - {item.name}
                </option>
              ))}
            </select>
            <input className="rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Projeto (opcional se configurado no conector)" value={project} onChange={(e) => setProject(e.target.value)} />
            <input className="rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Time (opcional)" value={team} onChange={(e) => setTeam(e.target.value)} />
            <input className="rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Area Path (opcional)" value={areaPath} onChange={(e) => setAreaPath(e.target.value)} />
            <input className="rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Iteration Path (opcional)" value={iterationPath} onChange={(e) => setIterationPath(e.target.value)} />
            <div className="flex gap-2">
              <input className="w-24 rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Top" value={top} onChange={(e) => setTop(e.target.value)} />
              <button onClick={handleQuery} disabled={loading} className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60">
                {loading ? 'Consultando...' : 'Consultar'}
              </button>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
            <select className="rounded-lg border border-gray-300 px-3 py-2 text-sm" value={selectedPresetId} onChange={(e) => applyPreset(e.target.value)}>
              <option value="">Setor salvo (usuario)</option>
              {presets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <input className="rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Nome do setor" value={presetName} onChange={(e) => setPresetName(e.target.value)} />
            <button onClick={savePreset} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50">
              Salvar setor
            </button>
            <button onClick={deletePreset} disabled={!selectedPresetId} className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60">
              Excluir setor
            </button>
          </div>
          {error && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
        </div>

        {snapshot && (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Total itens</p><p className="text-2xl font-bold text-gray-900">{snapshot.totals.total}</p></div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Com epico</p><p className="text-2xl font-bold text-emerald-700">{snapshot.totals.with_epic}</p></div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"><p className="text-xs text-gray-500">Sem epico</p><p className="text-2xl font-bold text-amber-700">{snapshot.totals.without_epic}</p></div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-gray-500">Horas (orig/rem/comp)</p>
                <p className="text-lg font-bold text-gray-900">{snapshot.totals.hours.original} / {snapshot.totals.hours.remaining} / {snapshot.totals.hours.completed}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
                <p className="text-xs font-semibold text-amber-700">PBIs sem task</p>
                <p className="text-2xl font-bold text-amber-800">{snapshot.diagnostics?.pbi_without_task?.total || 0}</p>
              </div>
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 shadow-sm">
                <p className="text-xs font-semibold text-rose-700">Tasks programadas sem horas</p>
                <p className="text-2xl font-bold text-rose-800">{snapshot.diagnostics?.tasks_without_hours?.total || 0}</p>
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-sm font-semibold text-gray-700">Status do quadro</h2>
              <div className="flex flex-wrap gap-2">
                {byState.map(([state, qty]) => (
                  <span key={state} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
                    {state}: {qty}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <h2 className="mb-2 text-sm font-semibold text-gray-700">Usuarios com PBI sem task</h2>
                {pbiWithoutTaskByUser.length === 0 ? (
                  <p className="text-sm text-gray-500">Nenhum caso encontrado.</p>
                ) : (
                  <div className="space-y-2">
                    {pbiWithoutTaskByUser.map((group) => (
                      <div key={group.user} className="rounded-lg border border-gray-200 p-2">
                        <p className="text-sm font-semibold text-gray-800">{group.user} <span className="text-xs text-gray-500">({group.count})</span></p>
                        <p className="mt-1 text-xs text-gray-600">
                          {group.items.slice(0, 6).map((item) => `#${item.id}`).join(', ')}
                          {group.items.length > 6 ? ' ...' : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <h2 className="mb-2 text-sm font-semibold text-gray-700">Usuarios com tasks sem horas</h2>
                {tasksWithoutHoursByUser.length === 0 ? (
                  <p className="text-sm text-gray-500">Nenhum caso encontrado.</p>
                ) : (
                  <div className="space-y-2">
                    {tasksWithoutHoursByUser.map((group) => (
                      <div key={group.user} className="rounded-lg border border-gray-200 p-2">
                        <p className="text-sm font-semibold text-gray-800">{group.user} <span className="text-xs text-gray-500">({group.count})</span></p>
                        <p className="mt-1 text-xs text-gray-600">
                          {group.items.slice(0, 6).map((item) => `#${item.id}`).join(', ')}
                          {group.items.length > 6 ? ' ...' : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-3 py-2">ID</th>
                    <th className="px-3 py-2">Tipo</th>
                    <th className="px-3 py-2">Titulo</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Horas (orig/rem/comp)</th>
                    <th className="px-3 py-2">PBI/Pai</th>
                    <th className="px-3 py-2">Epico</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.items.map((item) => (
                    <tr key={item.id} className="border-t border-gray-100">
                      <td className="px-3 py-2 font-semibold text-gray-800">#{item.id}</td>
                      <td className="px-3 py-2 text-gray-700">{item.type || '-'}</td>
                      <td className="px-3 py-2 text-gray-700">{item.title || '-'}</td>
                      <td className="px-3 py-2 text-gray-700">{item.state || '-'}</td>
                      <td className="px-3 py-2 text-gray-700">{item.hours.original} / {item.hours.remaining} / {item.hours.completed}</td>
                      <td className="px-3 py-2 text-gray-700">{item.parent ? `#${item.parent.id} - ${item.parent.title || ''}` : '-'}</td>
                      <td className="px-3 py-2 text-gray-700">{item.epic ? `#${item.epic.id} - ${item.epic.title || ''}` : 'Sem epico'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
};

export default AzureBoardsPage;
