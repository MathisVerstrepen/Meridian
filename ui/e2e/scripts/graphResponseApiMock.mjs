import { createServer } from 'node:http';
import { gzipSync } from 'node:zlib';

const port = Number.parseInt(process.env.GRAPH_RESPONSE_MOCK_PORT ?? '4174', 10);
const token = 'graph-response-fixture-token';
const ids = {
    valid: '11111111-1111-4111-8111-111111111111',
    unsupported: '22222222-2222-4222-8222-222222222222',
    malformed: '33333333-3333-4333-8333-333333333333',
    gzip: '44444444-4444-4444-8444-444444444444',
};
const nodeCount = 3;
const replyChunk = [
    'Meridian graph response fixture — preserve Unicode, whitespace, and punctuation.\n',
    '```ts\nconst reply = "opaque";\n```\n',
    'Sentinel payload line: αβγ / 日本語 / emoji 🚀 / tabs\tremain.\n',
].join('');
const reply = replyChunk;

const fixture = {
    version: 1,
    graph: {
        id: ids.valid,
        name: 'Large graph response fixture',
        node_count: nodeCount,
    },
    nodes: [
        {
            id: 'node-0',
            type: 'textToText',
            position_x: 12.5,
            position_y: -7.25,
            data: {
                reply,
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

const requestCounts = new Map();

const sendJson = (response, value, gzip = false) => {
    const json = Buffer.from(JSON.stringify(value));
    const body = gzip ? gzipSync(json) : json;
    const headers = {
        'content-type': 'application/json',
        'content-length': String(body.length),
    };
    if (gzip) {
        Object.assign(headers, {
            'content-encoding': 'gzip',
            'x-fixture-upstream-encoding': 'gzip',
            'x-fixture-upstream-length': String(body.length),
        });
    }
    response.writeHead(200, headers);
    response.end(body);
};

const server = createServer((request, response) => {
    const url = new URL(request.url ?? '/', `http://${request.headers.host ?? '127.0.0.1'}`);
    if (url.pathname === '/__health') {
        sendJson(response, { ok: true });
        return;
    }
    if (url.pathname === '/__requests') {
        sendJson(response, Object.fromEntries(requestCounts));
        return;
    }

    requestCounts.set(url.pathname, (requestCounts.get(url.pathname) ?? 0) + 1);
    if (request.headers.authorization !== `Bearer ${token}`) {
        response.writeHead(401, { 'content-type': 'application/json' });
        response.end(JSON.stringify({ detail: 'Invalid fixture authorization' }));
        return;
    }

    const graphId = url.pathname.match(/^\/graph\/([^/]+)$/)?.[1];
    if (!graphId || !Object.values(ids).includes(graphId)) {
        response.writeHead(404, { 'content-type': 'application/json' });
        response.end(JSON.stringify({ detail: 'Unknown fixture path' }));
        return;
    }

    if (graphId === ids.unsupported) {
        sendJson(response, { version: 2, graph: {}, nodes: [], edges: [] });
        return;
    }
    if (graphId === ids.malformed) {
        sendJson(response, {
            version: 1,
            graph: { id: graphId, name: 'Malformed fixture', node_count: 1 },
            nodes: [
                { id: 'bad-node', type: 'textToText', position_x: 'bad', position_y: 0 },
            ],
            edges: [],
        });
        return;
    }

    sendJson(response, fixture, graphId === ids.gzip);
});

server.listen(port, '127.0.0.1');

const shutdown = () => server.close(() => process.exit(0));
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
