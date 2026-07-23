import { describe, expect, it } from 'vitest';
import { ReasoningEffortEnum } from '@/types/enums';
import { decodeGraphEditorResponse } from '@/utils/graphResponse';

const minimalResponse = () => ({
    version: 1,
    graph: {
        id: 'graph-1',
        name: 'Graph',
        node_count: 1,
    },
    nodes: [
        {
            id: 'node-1',
            type: 'prompt',
            position_x: 10,
            position_y: 20,
        },
    ],
    edges: [
        {
            id: 'edge-1',
            source_node_id: 'node-1',
            target_node_id: 'node-2',
        },
    ],
});

describe('decodeGraphEditorResponse', () => {
    it('decodes a minimal version-1 graph with every default', () => {
        expect(decodeGraphEditorResponse(minimalResponse())).toEqual({
            version: 1,
            graph: {
                id: 'graph-1',
                name: 'Graph',
                node_count: 1,
                folder_id: null,
                workspace_id: null,
                description: null,
                temporary: false,
                pinned: false,
                created_at: null,
                updated_at: null,
                custom_instructions: [],
                max_tokens: null,
                temperature: null,
                top_p: null,
                top_k: null,
                frequency_penalty: null,
                presence_penalty: null,
                repetition_penalty: null,
                reasoning_effort: null,
            },
            nodes: [
                {
                    id: 'node-1',
                    type: 'prompt',
                    position_x: 10,
                    position_y: 20,
                    width: '100px',
                    height: '100px',
                    parent_node_id: null,
                    data: null,
                },
            ],
            edges: [
                {
                    id: 'edge-1',
                    source_node_id: 'node-1',
                    target_node_id: 'node-2',
                    source_handle_id: null,
                    target_handle_id: null,
                    type: null,
                    label: null,
                    animated: false,
                    style: null,
                    data: null,
                },
            ],
        });
    });

    it('preserves fully populated optionals and JSON-container references', () => {
        const nodeData = { model: 'model-1' };
        const edgeStyle = { stroke: '#fff' };
        const edgeData = ['metadata'];
        const response = {
            version: 1,
            graph: {
                id: 'graph-1',
                name: 'Graph',
                node_count: 1,
                folder_id: 'folder-1',
                workspace_id: 'workspace-1',
                description: 'Description',
                temporary: true,
                pinned: true,
                created_at: '2026-07-18T00:00:00Z',
                updated_at: '2026-07-18T01:00:00Z',
                custom_instructions: ['Be concise'],
                max_tokens: 4096,
                temperature: 0.5,
                top_p: 0.9,
                top_k: 40,
                frequency_penalty: 0.1,
                presence_penalty: 0.2,
                repetition_penalty: 1.1,
                reasoning_effort: ReasoningEffortEnum.HIGH,
            },
            nodes: [
                {
                    id: 'node-1',
                    type: 'prompt',
                    position_x: 10,
                    position_y: 20,
                    width: '240px',
                    height: '160px',
                    parent_node_id: 'group-1',
                    data: nodeData,
                },
            ],
            edges: [
                {
                    id: 'edge-1',
                    source_node_id: 'node-1',
                    target_node_id: 'node-2',
                    source_handle_id: 'source-1',
                    target_handle_id: 'target-1',
                    type: 'custom',
                    label: 'Edge',
                    animated: true,
                    style: edgeStyle,
                    data: edgeData,
                },
            ],
        };

        const result = decodeGraphEditorResponse(response);

        expect(result.graph).toMatchObject(response.graph);
        expect(result.nodes[0]).toMatchObject(response.nodes[0]);
        expect(result.edges[0]).toMatchObject(response.edges[0]);
        expect(result.nodes[0].data).toBe(nodeData);
        expect(result.edges[0].style).toBe(edgeStyle);
        expect(result.edges[0].data).toBe(edgeData);
    });

    it.each([
        {
            name: 'unsupported version',
            value: { ...minimalResponse(), version: 2 },
            message: 'Unsupported graph response version: 2',
        },
        {
            name: 'non-finite nested node position',
            value: {
                ...minimalResponse(),
                nodes: [{ ...minimalResponse().nodes[0], position_y: Number.POSITIVE_INFINITY }],
            },
            message: 'Invalid graph response value at nodes[0].position_y: expected a finite number',
        },
        {
            name: 'non-integer graph count',
            value: {
                ...minimalResponse(),
                graph: { ...minimalResponse().graph, node_count: 1.5 },
            },
            message: 'Invalid graph response value at graph.node_count: expected a safe integer',
        },
        {
            name: 'non-string custom instruction',
            value: {
                ...minimalResponse(),
                graph: { ...minimalResponse().graph, custom_instructions: ['valid', 42] },
            },
            message:
                'Invalid graph response value at graph.custom_instructions[1]: expected a string',
        },
        {
            name: 'unsupported reasoning effort',
            value: {
                ...minimalResponse(),
                graph: { ...minimalResponse().graph, reasoning_effort: 'extreme' },
            },
            message:
                'Invalid graph response value at graph.reasoning_effort: expected a supported reasoning effort or null',
        },
    ])('rejects $name with the existing exact error', ({ value, message }) => {
        expect(() => decodeGraphEditorResponse(value)).toThrow(message);
    });
});
