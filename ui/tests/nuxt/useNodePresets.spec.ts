import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { Edge, Node } from '@vue-flow/core';
import { defineComponent, h, reactive, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useNodePresets } from '@/composables/useNodePresets';
import type { NodePreset, NodePresetSettings } from '@/types/nodePresets';

interface TestNode {
    id: string;
    type?: string;
    position: { x: number; y: number };
    data: object;
    selected?: boolean;
}

interface TestEdge {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
    type?: string;
}

const state = vi.hoisted(() => {
    const nodes: TestNode[] = [];
    const edges: TestEdge[] = [];
    const addedNodeBatches: string[][] = [];
    return {
    nodes: { value: nodes },
    edges: { value: edges },
    addedNodeBatches,
    failEdges: false,
    overlap: vi.fn(),
    toastError: vi.fn(),
    id: 0,
    };
});

mockNuxtImport('useGraphFlow', () => () => {
    const asArray = <T>(value: T | T[]): T[] => (Array.isArray(value) ? value : [value]);
    const toTestNode = (node: Node): TestNode => ({
        id: node.id,
        type: node.type,
        position: node.position,
        data: node.data,
        selected:
            'selected' in node && isRuntimeBoolean(node.selected) ? node.selected : undefined,
    });
    const toTestEdge = (edge: Edge): TestEdge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        type: edge.type,
    });
    return {
            getNodes: state.nodes,
            addNodes: (nodes: Node | Node[]) => {
                const batch = asArray(nodes);
                state.addedNodeBatches.push(batch.map((node) => node.id));
                state.nodes.value.push(...batch.map(toTestNode));
            },
            addEdges: (edges: Edge | Edge[]) => {
                if (state.failEdges) throw new Error('edge add failed');
                state.edges.value.push(...asArray(edges).map(toTestEdge));
            },
            removeNodes: (nodes: TestNode[]) => {
                const ids = new Set(nodes.map((node) => node.id));
                state.nodes.value = state.nodes.value.filter((node) => !ids.has(node.id));
            },
            removeEdges: (edges: TestEdge[]) => {
                const ids = new Set(edges.map((edge) => edge.id));
                state.edges.value = state.edges.value.filter((edge) => !ids.has(edge.id));
            },
    };
});

const preset: NodePreset = {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    name: 'Grouped starter',
    accentColor: '#3366aa',
    nodes: [
        {
            id: '11111111-1111-4111-8111-111111111111',
            type: 'group',
            position: { x: 0, y: 0 },
            width: 620,
            height: 320,
            data: { title: 'Inputs', comment: '<b>plain</b>', colorIndex: 2 },
        },
        {
            id: '22222222-2222-4222-8222-222222222222',
            type: 'prompt',
            position: { x: 60, y: 60 },
            width: 500,
            height: 200,
            parentId: '11111111-1111-4111-8111-111111111111',
            data: { prompt: 'Configured', templateVariables: {} },
        },
        {
            id: '33333333-3333-4333-8333-333333333333',
            type: 'textToText',
            position: { x: 760, y: 0 },
            width: 600,
            height: 300,
            data: { model: 'configured-model', selectedTools: [] },
        },
    ],
    edges: [
        {
            id: '44444444-4444-4444-8444-444444444444',
            source: '22222222-2222-4222-8222-222222222222',
            target: '33333333-3333-4333-8333-333333333333',
            category: 'prompt',
        },
    ],
};

const emptyPreset: NodePreset = {
    id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    name: 'Draft',
    accentColor: '#eb5e28',
    nodes: [],
    edges: [],
};
const duplicatePreset: NodePreset = {
    ...structuredClone(preset),
    id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    name: 'Ｇｒｏｕｐｅｄ ｓｔａｒｔｅｒ',
};
const settings = reactive<{ nodePresetSettings: NodePresetSettings }>({
    nodePresetSettings: { schemaVersion: 1, presets: [preset, emptyPreset, duplicatePreset] },
});
const session = {
    user: ref<{ plan_type: 'free' | 'premium' }>({ plan_type: 'premium' }),
};

mockNuxtImport('useSettingsStore', () => () => settings);
mockNuxtImport('useUserSession', () => () => session);
mockNuxtImport('useUniqueId', () => () => ({ generateId: () => `fresh-${++state.id}` }));
mockNuxtImport('useBlocks', () => () => ({
    getBlockByNodeType: (type: string) =>
        type === 'group'
            ? undefined
            : { defaultData: type === 'textToText' ? { model: 'default', reply: 'runtime' } : {} },
}));
mockNuxtImport('useEdgeCompatibility', () => () => ({ checkEdgeCompatibility: () => true }));
mockNuxtImport('useGraphOverlaps', () => () => ({ resolveOverlaps: state.overlap }));
mockNuxtImport('useToast', () => () => ({ error: state.toastError }));

describe('useNodePresets', () => {
    beforeEach(() => {
        state.nodes!.value = [{ id: 'existing', position: { x: 0, y: 0 }, data: {}, selected: true }];
        state.edges!.value = [];
        state.addedNodeBatches = [];
        state.failEdges = false;
        state.overlap.mockReset();
        state.toastError.mockReset();
        state.id = 0;
        session.user.value.plan_type = 'premium';
    });

    const mountComposable = async () => {
        let presets: ReturnType<typeof useNodePresets> | undefined;
        const Host = defineComponent({
            setup() {
                presets = useNodePresets(ref('graph-1'));
                return () => h('div');
            },
        });
        const wrapper = await mountSuspended(Host);
        return { presets: presets!, wrapper };
    };

    it('lists only valid nonempty presets and places a fresh selected graph atomically', async () => {
        const { presets, wrapper } = await mountComposable();
        expect(presets.placeablePresets.value.map((entry) => entry.preset.name)).toEqual([
            'Grouped starter',
        ]);

        expect(await presets.placePreset(preset, { x: 1000, y: 500 })).toBe(true);
        expect(state.addedNodeBatches).toHaveLength(2);
        expect(state.nodes!.value.find((node) => node.id === 'existing')?.selected).toBe(false);
        const placed = state.nodes!.value.filter((node) => node.id !== 'existing');
        expect(placed).toHaveLength(3);
        expect(placed.every((node) => node.selected)).toBe(true);
        expect(state.addedNodeBatches[0]?.[0]).toBe('group-fresh-1');
        expect(placed.find((node) => node.id === 'group-fresh-1')).toMatchObject({
            position: { x: 320, y: 340 },
            data: { comment: '<b>plain</b>', contentMode: 'plain' },
        });
        expect(placed.find((node) => node.id === 'fresh-3')).toMatchObject({
            position: { x: 1080, y: 340 },
            data: {
                model: 'configured-model',
                reply: '',
                usageData: null,
                activeGenerationHistoryId: undefined,
            },
        });
        expect(state.edges!.value[0]).toMatchObject({
            id: 'fresh-4',
            sourceHandle: 'prompt_fresh-2',
            targetHandle: 'prompt_fresh-3',
        });
        expect(state.overlap).toHaveBeenCalledOnce();
        expect(state.overlap).toHaveBeenCalledWith('group-fresh-1', ['fresh-3']);
        wrapper.unmount();
    });

    it('rolls back nodes and restores selection when a post-add mutation fails', async () => {
        const { presets, wrapper } = await mountComposable();
        state.failEdges = true;

        expect(await presets.placePreset(preset, { x: 1000, y: 500 })).toBe(false);
        expect(state.nodes!.value.map((node) => node.id)).toEqual(['existing']);
        expect(state.nodes!.value[0]?.selected).toBe(true);
        expect(state.edges!.value).toEqual([]);
        expect(state.overlap).not.toHaveBeenCalled();
        wrapper.unmount();
    });

    it('locks the whole GitHub preset for free users before graph mutation', async () => {
        const githubPreset: NodePreset = {
            ...preset,
            id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
            name: 'GitHub preset',
            nodes: [
                {
                    id: '55555555-5555-4555-8555-555555555555',
                    type: 'github',
                    position: { x: 0, y: 0 },
                    width: 500,
                    height: 250,
                    data: { files: [], selectedIssues: [] },
                },
            ],
            edges: [],
        };
        settings.nodePresetSettings.presets = [githubPreset];
        session.user.value.plan_type = 'free';
        const { presets, wrapper } = await mountComposable();

        expect(presets.placeablePresets.value[0]?.locked).toBe(true);
        expect(await presets.placePreset(githubPreset, { x: 0, y: 0 })).toBe(false);
        expect(state.addedNodeBatches).toEqual([]);
        expect(state.toastError).toHaveBeenCalledWith(
            'GitHub nodes are available on the Premium plan.',
            { title: 'Premium Feature' },
        );
        wrapper.unmount();
        settings.nodePresetSettings.presets = [preset, emptyPreset, duplicatePreset];
    });
});
