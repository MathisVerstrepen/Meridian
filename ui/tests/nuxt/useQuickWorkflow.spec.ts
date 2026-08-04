import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphNode } from '@vue-flow/core';

import { useQuickWorkflow } from '@/composables/useQuickWorkflow';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition } from '@/types/graph';

const stubs = vi.hoisted(() => ({
    nodes: { value: [] as GraphNode[] },
    edges: { value: [] as Array<{ target: string; targetHandle: string }> },
    placeBlock: vi.fn(),
    placeEdge: vi.fn(),
}));

vi.mock('@vue-flow/core', () => ({
    useVueFlow: () => ({ getNodes: stubs.nodes, getEdges: stubs.edges }),
}));

mockNuxtImport('useRoute', () => () => ({ params: { id: 'graph-id' } }));
mockNuxtImport('useGraphActions', () => () => ({
    placeBlock: stubs.placeBlock,
    placeEdge: stubs.placeEdge,
}));
mockNuxtImport('useEdgeCompatibility', () => () => ({
    acceptsMultipleInputEdges: () => false,
}));
mockNuxtImport('useGraphOverlaps', () => () => ({ resolveOverlaps: vi.fn() }));
mockNuxtImport('useBlocks', () => () => ({
    getBlockByNodeType: (nodeType: NodeTypeEnum) =>
        ({
            id: `block-${nodeType}`,
            nodeType,
            name: nodeType,
            icon: 'test',
            desc: '',
            defaultData: {},
            minSize: { width: 100, height: 100 },
            color: '',
        }) as unknown as BlockDefinition,
}));

describe('useQuickWorkflow availability', () => {
    beforeEach(() => {
        stubs.nodes.value = [
            {
                id: 'anchor',
                type: NodeTypeEnum.TEXT_TO_TEXT,
                position: { x: 0, y: 0 },
            } as GraphNode,
        ];
        stubs.edges.value = [];
    });

    it('uses creation validation for valid, invalid, missing, and occupied anchors', () => {
        const { canCreateQuickWorkflow } = useQuickWorkflow(ref('graph-id'));
        const validPayload = {
            fromNodeId: 'anchor',
            category: NodeCategoryEnum.PROMPT,
            direction: 'target' as const,
            slot: { name: 'Prompt', mainBloc: NodeTypeEnum.PROMPT, options: [] },
        };

        expect(canCreateQuickWorkflow(validPayload)).toBe(true);
        expect(
            canCreateQuickWorkflow({
                ...validPayload,
                slot: { ...validPayload.slot, mainBloc: NodeTypeEnum.GITHUB },
            }),
        ).toBe(false);
        expect(canCreateQuickWorkflow({ ...validPayload, fromNodeId: 'missing' })).toBe(false);

        stubs.edges.value = [{ target: 'anchor', targetHandle: 'prompt_anchor' }];
        expect(canCreateQuickWorkflow(validPayload)).toBe(false);
    });
});
