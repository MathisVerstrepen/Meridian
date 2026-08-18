import { mockNuxtImport } from '@nuxt/test-utils/runtime';
import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GraphNode } from '@vue-flow/core';

import { useQuickWorkflow } from '@/composables/useQuickWorkflow';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition } from '@/types/graph';

const stubs = vi.hoisted(() => ({
    nodes: { value: [] as GraphNode[] },
    edges: {
        value: [] as Array<{
            source: string;
            target: string;
            targetHandle?: string;
        }>,
    },
    placeBlock: vi.fn(),
    placeEdge: vi.fn(),
    resolveOverlaps: vi.fn(),
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
mockNuxtImport('useGraphOverlaps', () => () => ({ resolveOverlaps: stubs.resolveOverlaps }));
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
        vi.clearAllMocks();
        stubs.nodes.value = [
            {
                id: 'anchor',
                type: NodeTypeEnum.TEXT_TO_TEXT,
                position: { x: 0, y: 0 },
                dimensions: { width: 320, height: 180 },
            } as GraphNode,
        ];
        stubs.edges.value = [];
        stubs.placeBlock.mockImplementation(
            (options: {
                positionFrom: { x: number; y: number };
                positionOffset?: { x: number; y: number };
            }) => ({
                id: 'quick-main-id',
                position: {
                    x: options.positionFrom.x + (options.positionOffset?.x ?? 0),
                    y: options.positionFrom.y + (options.positionOffset?.y ?? 0),
                },
            }),
        );
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

        stubs.edges.value = [
            { source: 'occupied-source', target: 'anchor', targetHandle: 'prompt_anchor' },
        ];
        expect(canCreateQuickWorkflow(validPayload)).toBe(false);
    });

    it('places a context source generator below an anchor without generator children', () => {
        const { createQuickWorkflow } = useQuickWorkflow(ref('graph-id'));

        createQuickWorkflow({
            fromNodeId: 'anchor',
            category: NodeCategoryEnum.CONTEXT,
            direction: 'source',
            slot: {
                name: 'Generator',
                mainBloc: NodeTypeEnum.TEXT_TO_TEXT,
                options: [],
            },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'block-textToText',
                positionFrom: { x: 0, y: 330 },
                positionOffset: undefined,
            }),
        );
    });

    it('places a context source generator right of the rightmost direct generator child', () => {
        stubs.nodes.value.push(
            {
                id: 'direct-child',
                type: NodeTypeEnum.ROUTING,
                position: { x: 500, y: 600 },
                dimensions: { width: 350, height: 100 },
            } as GraphNode,
            {
                id: 'descendant',
                type: NodeTypeEnum.PARALLELIZATION,
                position: { x: 1200, y: 1000 },
                width: 300,
            } as GraphNode,
        );
        stubs.edges.value = [
            { source: 'anchor', target: 'direct-child' },
            { source: 'direct-child', target: 'descendant' },
        ];
        const { createQuickWorkflow } = useQuickWorkflow(ref('graph-id'));

        createQuickWorkflow({
            fromNodeId: 'anchor',
            category: NodeCategoryEnum.CONTEXT,
            direction: 'source',
            slot: {
                name: 'Generator',
                mainBloc: NodeTypeEnum.ROUTING,
                options: [],
            },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'block-routing',
                positionFrom: { x: 1000, y: 600 },
                positionOffset: undefined,
            }),
        );
    });

    it('keeps target-direction workflow placement unchanged', () => {
        const { createQuickWorkflow } = useQuickWorkflow(ref('graph-id'));

        createQuickWorkflow({
            fromNodeId: 'anchor',
            category: NodeCategoryEnum.CONTEXT,
            direction: 'target',
            slot: {
                name: 'Generator',
                mainBloc: NodeTypeEnum.PARALLELIZATION,
                options: [],
            },
        });

        expect(stubs.placeBlock).toHaveBeenCalledWith(
            expect.objectContaining({
                blocId: 'block-parallelization',
                positionFrom: { x: 0, y: 0 },
                positionOffset: { x: 0, y: -250 },
            }),
        );
    });
});
