import { defineStore } from 'pinia';
import { parseAgentRun } from '@/utils/agentRuns';
import type { AgentProfile, AgentRecord, AgentRun, AgentTeam, AgentVersion } from '@/types/agent';

export const useAgentStore = defineStore('agent', () => {
    const { apiFetch } = useAPI();
    const library = ref<AgentRecord[]>([]);
    const items = ref<AgentRecord[]>([]);
    const teams = ref<AgentTeam[]>([]);
    const total = ref(0);
    const loading = ref(false);
    const error = ref('');
    const runs = ref<Record<string, Record<string, AgentRun>>>({});
    const defaultTeamId = computed(() => teams.value.find((team) => team.is_default)?.id ?? '');
    let requestId = 0;

    const search = async (query: Record<string, string | number> = {}) => {
        const id = ++requestId;
        loading.value = true;
        error.value = '';
        try {
            const page = await apiFetch<{ items: AgentRecord[]; total: number }>(
                `/api/agents?${new URLSearchParams(Object.entries(query).map(([key, value]) => [key, String(value)]))}`,
            );
            if (id === requestId) {
                items.value = page.items;
                total.value = page.total;
            }
        } catch (err) {
            if (id === requestId)
                error.value = runtimeErrorMessage(err) ?? 'Could not load Agents.';
        } finally {
            if (id === requestId) loading.value = false;
        }
    };
    const loadLibrary = async () => {
        const all: AgentRecord[] = [];
        let offset = 0;
        while (true) {
            const page = await apiFetch<{ items: AgentRecord[]; total: number }>(
                `/api/agents?view=my&limit=100&offset=${offset}`,
            );
            all.push(...page.items);
            offset += page.items.length;
            if (offset >= page.total || page.items.length === 0) break;
        }
        library.value = all;
        teams.value = await apiFetch<AgentTeam[]>('/api/agents/teams');
    };
    const save = (profile: AgentProfile, id?: string) =>
        apiFetch<AgentRecord>(`/api/agents${id ? `/${id}` : ''}`, {
            method: id ? 'PUT' : 'POST',
            body: JSON.stringify(profile),
        });
    const fork = (id: string) =>
        apiFetch<AgentRecord>(`/api/agents/${id}/fork`, { method: 'POST' });
    const remove = (id: string) => apiFetch(`/api/agents/${id}`, { method: 'DELETE' });
    const bookmark = (agent: AgentRecord) =>
        apiFetch(`/api/agents/${agent.id}/bookmark`, {
            method: agent.bookmarked ? 'DELETE' : 'PUT',
        });
    const rate = (id: string, value: number) =>
        apiFetch(`/api/agents/${id}/rating`, {
            method: 'PUT',
            body: JSON.stringify({ value }),
        });
    const verify = (id: string, verified: boolean) =>
        apiFetch(`/api/agents/${id}/verification`, {
            method: 'PUT',
            body: JSON.stringify({ verified }),
        });
    const versions = (id: string) => apiFetch<AgentVersion[]>(`/api/agents/${id}/versions`);
    const restoreVersion = (id: string, version: number) =>
        apiFetch<AgentRecord>(`/api/agents/${id}/versions/${version}/restore`, { method: 'POST' });
    const generateIcon = (body: {
        name: string;
        description: string;
        instructions: string;
        category: string;
        tags: string[];
        tools: AgentProfile['tools'];
        model: string;
    }) =>
        apiFetch<{ iconSvg: string }>('/api/agents/generate-icon', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    const generateDescription = (body: { name: string; instructions: string; model: string }) =>
        apiFetch<{ description: string }>('/api/agents/generate-description', {
            method: 'POST',
            body: JSON.stringify(body),
        });
    const presets = () => apiFetch<AgentProfile[]>('/api/agents/presets');
    const importProfile = (body: JsonObject) =>
        apiFetch<AgentRecord>('/api/agents/import', { method: 'POST', body: JSON.stringify(body) });
    const exportProfile = (id: string) => apiFetch<JsonObject>(`/api/agents/${id}/export`);
    const saveTeam = (
        team: Pick<AgentTeam, 'name' | 'handle' | 'description' | 'members'>,
        id?: string,
    ) =>
        apiFetch<AgentTeam>(`/api/agents/teams${id ? `/${id}` : ''}`, {
            method: id ? 'PUT' : 'POST',
            body: JSON.stringify(team),
        });
    const resolveMention = (message: string) =>
        apiFetch<{ team_id: string | null; message: string }>('/api/agents/resolve-mention', {
            method: 'POST',
            body: JSON.stringify({ message }),
        });
    const updateRun = (nodeId: string, value: JsonValue) => {
        const run = parseAgentRun(value);
        if (!run) return;
        if (run.parent_id === null && run.status === 'running' && !runs.value[nodeId]?.[run.id]) {
            runs.value[nodeId] = {};
        }
        runs.value[nodeId] ??= {};
        runs.value[nodeId][run.id] = run;
    };
    const appendRunChunk = (nodeId: string, runId: string, chunk: string) => {
        const run = runs.value[nodeId]?.[runId];
        if (run) run.result += chunk;
    };
    return {
        library,
        items,
        teams,
        total,
        loading,
        error,
        runs,
        search,
        loadLibrary,
        save,
        fork,
        remove,
        bookmark,
        rate,
        verify,
        versions,
        restoreVersion,
        presets,
        generateDescription,
        generateIcon,
        importProfile,
        exportProfile,
        saveTeam,
        resolveMention,
        updateRun,
        appendRunChunk,
        defaultTeamId,
    };
});
