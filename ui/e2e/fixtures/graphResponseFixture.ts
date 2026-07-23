import type { GraphEditorResponseV1 } from '../../app/types/graphResponse';

export const GRAPH_RESPONSE_FIXTURE_ROUTE = '/auth/graph-response-fixture';
export const GRAPH_RESPONSE_PERFORMANCE_FIXTURE_ROUTE =
    '/auth/graph-response-performance-fixture';
export const GRAPH_RESPONSE_FIXTURE_TOKEN = 'graph-response-fixture-token';
export const GRAPH_RESPONSE_MOCK_PORT = '4174';

export const GRAPH_RESPONSE_IDS = {
    valid: '11111111-1111-4111-8111-111111111111',
    unsupported: '22222222-2222-4222-8222-222222222222',
    malformed: '33333333-3333-4333-8333-333333333333',
    gzip: '44444444-4444-4444-8444-444444444444',
} as const;

export const GRAPH_RESPONSE_NODE_COUNT = 3;
export const GRAPH_RESPONSE_EDGE_COUNT = 2;
export const GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT = 500;
export const GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT = 650;
export const GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH = 4_350_000;

const replyChunk = [
    'Meridian graph response fixture — preserve Unicode, whitespace, and punctuation.\n',
    '```ts\nconst reply = "opaque";\n```\n',
    'Sentinel payload line: αβγ / 日本語 / emoji 🚀 / tabs\tremain.\n',
].join('');

export const GRAPH_RESPONSE_REPLY = replyChunk;
export const GRAPH_RESPONSE_REPLY_LENGTH = GRAPH_RESPONSE_REPLY.length;

export const GRAPH_RESPONSE_FIXTURE: GraphEditorResponseV1 = {
    version: 1,
    graph: {
        id: GRAPH_RESPONSE_IDS.valid,
        name: 'Large graph response fixture',
        node_count: GRAPH_RESPONSE_NODE_COUNT,
    },
    nodes: [
        {
            id: 'node-0',
            type: 'textToText',
            position_x: 12.5,
            position_y: -7.25,
            data: {
                reply: GRAPH_RESPONSE_REPLY,
                nested: {
                    nullValue: null,
                    falseValue: false,
                    zeroValue: 0,
                    emptyString: '',
                    emptyObject: {},
                    emptyArray: [],
                },
            },
        },
        {
            id: 'node-1',
            type: 'prompt',
            position_x: 320,
            position_y: 180,
            width: '240px',
            height: '160px',
            parent_node_id: 'node-0',
            data: { prompt: 'Fixture prompt', templateId: 'template-1' },
        },
        {
            id: 'node-2',
            type: 'textToText',
            position_x: 2.5,
            position_y: -1,
        },
    ],
    edges: [
        {
            id: 'edge-0',
            source_node_id: 'node-0',
            target_node_id: 'node-1',
            source_handle_id: 'context_output',
            target_handle_id: 'prompt_input',
            type: 'customEdge',
            label: 'Fixture edge',
            animated: true,
            style: { stroke: '#ff7a1a', strokeWidth: 2 },
            data: { weight: 0, enabled: false, tags: [] },
        },
        {
            id: 'edge-1',
            source_node_id: 'node-1',
            target_node_id: 'node-2',
        },
    ],
};

export const GRAPH_RESPONSE_UNSUPPORTED_FIXTURE = {
    ...GRAPH_RESPONSE_FIXTURE,
    version: 2,
};

export const GRAPH_RESPONSE_MALFORMED_FIXTURE = {
    ...GRAPH_RESPONSE_FIXTURE,
    nodes: [{ ...GRAPH_RESPONSE_FIXTURE.nodes[0], position_x: 'not-a-number' }],
};
