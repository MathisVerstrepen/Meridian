import type { GraphEditorResponseV1 } from '../../app/types/graphResponse';
import {
    GRAPH_RESPONSE_IDS,
    GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT,
    GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH,
} from './graphResponseFixture';

const replyChunk = [
    'Meridian graph response fixture — preserve Unicode, whitespace, and punctuation.\n',
    '```ts\nconst reply = "opaque";\n```\n',
    'Sentinel payload line: αβγ / 日本語 / emoji 🚀 / tabs\tremain.\n',
].join('');

const largeGraphReply = replyChunk
    .repeat(Math.ceil(GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH / replyChunk.length))
    .slice(0, GRAPH_RESPONSE_PERFORMANCE_REPLY_LENGTH);

const generatedNodes = Array.from(
    { length: GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT - 2 },
    (_, offset) => {
        const index = offset + 2;
        return {
            id: `node-${index}`,
            type: 'textToText',
            position_x: index * 1.25,
            position_y: -index * 0.5,
        };
    },
);

const generatedEdges = Array.from(
    { length: GRAPH_RESPONSE_PERFORMANCE_EDGE_COUNT - 2 },
    (_, offset) => {
        const index = offset + 2;
        return {
            id: `edge-${index}`,
            source_node_id: `node-${index % GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT}`,
            target_node_id: `node-${(index + 1) % GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT}`,
        };
    },
);

export const GRAPH_RESPONSE_PERFORMANCE_FIXTURE: GraphEditorResponseV1 = {
    version: 1,
    graph: {
        id: GRAPH_RESPONSE_IDS.valid,
        name: 'Large graph response fixture',
        node_count: GRAPH_RESPONSE_PERFORMANCE_NODE_COUNT,
    },
    nodes: [
        {
            id: 'node-0',
            type: 'textToText',
            position_x: 12.5,
            position_y: -7.25,
            data: {
                reply: largeGraphReply,
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
        ...generatedNodes,
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
        ...generatedEdges,
    ],
};
