import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime';
import type { Edge, Node } from '@vue-flow/core';
import { defineComponent, h, reactive, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useNodePresetEditor } from '@/composables/useNodePresetEditor';
import type { NodePreset } from '@/types/nodePresets';

interface TestNode {
    id: string;
    type?: string;
    position: { x: number; y: number };
    dimensions: { width: number; height: number };
    width?: number;
    height?: number;
    parentNode?: string;
    selected?: boolean;
    data: Record<string, JsonValue>;
}

interface TestEdge {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
    type?: string;
}

const isEdgeId = (edge: string | TestEdge): edge is string => typeof edge === 'string';

const state = vi.hoisted(() => {
    const nodes: TestNode[] = [];
    const edges: TestEdge[] = [];
    return {
    nodes: { value: nodes },
    edges: { value: edges },
    ids: [
        '10000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000002',
        '10000000-0000-4000-8000-000000000003',
        '10000000-0000-4000-8000-000000000004',
    ],
    idIndex: 0,
    editorIssues: vi.fn(),
    markChanged: vi.fn(),
    mergerPlacement: vi.fn(),
    };
});

mockNuxtImport('useGraphFlow', () => () => {
    const asArray = <T>(value: T | T[]): T[] => (Array.isArray(value) ? value : [value]);
    const toTestNode = (node: Node): TestNode => {
        return {
            id: node.id,
            type: node.type,
            position: node.position,
            dimensions: {
                width: isRuntimeNumber(node.width) ? node.width : 0,
                height: isRuntimeNumber(node.height) ? node.height : 0,
            },
            width: isRuntimeNumber(node.width) ? node.width : undefined,
            height: isRuntimeNumber(node.height) ? node.height : undefined,
            parentNode: node.parentNode,
            selected:
                'selected' in node && isRuntimeBoolean(node.selected)
                    ? node.selected
                    : undefined,
            data: isJsonObject(node.data) ? node.data : {},
        };
    };
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
            getEdges: state.edges,
            setNodes: (nodes: Node[]) => {
                state.nodes.value = nodes.map(toTestNode);
            },
            setEdges: (edges: Edge[]) => (state.edges.value = edges.map(toTestEdge)),
            addNodes: (nodes: Node | Node[]) => {
                for (const node of asArray(nodes)) state.nodes.value.push(toTestNode(node));
            },
            addEdges: (edges: Edge | Edge[]) => {
                for (const edge of asArray(edges)) state.edges.value.push(toTestEdge(edge));
            },
            removeNodes: (nodes: TestNode[]) => {
                const ids = new Set(nodes.map((node) => node.id));
                state.nodes.value = state.nodes.value.filter((node) => !ids.has(node.id));
            },
            removeEdges: (edges: string[] | TestEdge[]) => {
                const ids = new Set(edges.map((edge) => (isEdgeId(edge) ? edge : edge.id)));
                state.edges.value = state.edges.value.filter((edge) => !ids.has(edge.id));
            },
            fitView: vi.fn().mockResolvedValue(true),
    };
});

const preset = reactive<NodePreset>({
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    name: 'Editor preset',
    accentColor: '#eb5e28',
    nodes: [],
    edges: [],
});
const settings = reactive({ nodePresetSettings: { schemaVersion: 1, presets: [preset] } });

mockNuxtImport('useSettingsStore', () => () => ({
    ...settings,
    setNodePresetEditorIssues: state.editorIssues,
    markSettingsChanged: state.markChanged,
}));
mockNuxtImport('useUniqueId', () => () => ({
    generateId: () => state.ids[state.idIndex++] ?? crypto.randomUUID(),
}));
mockNuxtImport('useBlocks', () => () => ({
    getBlockById: (id: string) => {
        const type = id === 'github' ? 'github' : id === 'generator' ? 'textToText' : 'prompt';
        return {
            id,
            nodeType: type,
            defaultData: type === 'prompt' ? { prompt: '', templateVariables: {} } : type === 'github' ? { files: [], selectedIssues: [] } : { model: '', selectedTools: [] },
            minSize: { width: type === 'textToText' ? 600 : 500, height: type === 'textToText' ? 300 : 200 },
        };
    },
    getBlockByNodeType: () => ({ defaultData: {} }),
}));
mockNuxtImport('useEdgeCompatibility', () => () => ({ checkEdgeCompatibility: () => true }));
mockNuxtImport('useGraphActions', () => () => ({
    handleContextMergerPlacement: state.mergerPlacement,
}));

describe('useNodePresetEditor', () => {
    beforeEach(() => {
        state.nodes!.value = [];
        state.edges!.value = [];
        state.idIndex = 0;
        preset.nodes = [];
        preset.edges = [];
        state.editorIssues.mockReset();
        state.markChanged.mockReset();
        state.mergerPlacement.mockReset();
    });

    it('adds, connects, groups, unlinks, serializes, and enforces the GitHub add lock', async () => {
        let editor: ReturnType<typeof useNodePresetEditor> | undefined;
        const Host = defineComponent({
            setup() {
                editor = useNodePresetEditor({ preset: ref(preset), flowId: 'node-preset-test' });
                return () => h('div');
            },
        });
        await mountSuspended(Host);
        expect(editor).toBeDefined();
        await editor!.hydrate();

        expect(editor!.addBlock('prompt', false)).toBe(true);
        expect(editor!.addBlock('generator', false)).toBe(true);
        const [prompt, generator] = state.nodes!.value;
        expect(
            editor!.connect({
                source: prompt!.id,
                sourceHandle: `prompt_${prompt!.id}`,
                target: generator!.id,
                targetHandle: `prompt_${generator!.id}`,
            }),
        ).toBe(true);
        expect(state.edges!.value).toHaveLength(1);

        prompt!.selected = true;
        generator!.selected = true;
        await expect(editor!.createGroup()).resolves.toBe(true);
        const group = state.nodes!.value.find((node) => node.type === 'group');
        expect(group).toBeDefined();
        expect(state.nodes!.value.filter((node) => node.parentNode === group!.id)).toHaveLength(2);

        editor!.unlinkNode(prompt!.id);
        expect(state.nodes!.value.find((node) => node.id === prompt!.id)?.parentNode).toBeUndefined();
        editor!.unlinkNode(generator!.id);
        expect(state.nodes!.value.some((node) => node.type === 'group')).toBe(false);
        expect(editor!.flush()).toBe(true);
        const storedPreset = settings.nodePresetSettings.presets.find(
            (entry) => entry.id === preset.id,
        );
        expect(storedPreset?.nodes).toHaveLength(2);
        expect(storedPreset?.edges).toHaveLength(1);

        expect(editor!.addBlock('github', true)).toBe(false);
        expect(editor!.actionMessage.value).toContain('Premium');
        expect(state.nodes!.value.some((node) => node.type === 'github')).toBe(false);
    });
});
