import { describe, expect, it } from 'vitest';

import { NodeTypeEnum } from '@/types/enums';
import {
    calculateGraphAutoLayout,
    GRAPH_AUTO_LAYOUT_EDGE_SEPARATION,
    GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
    GRAPH_AUTO_LAYOUT_RANK_SEPARATION,
    type GraphAutoLayoutEdge,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';
import {
    partitionAttachmentStackSubgraphs,
    placeAttachmentStacks,
} from '@/utils/graphAutoLayoutAttachmentStacks';

const node = (
    id: string,
    type: NodeTypeEnum,
    width: number,
    height: number,
): GraphAutoLayoutNode => ({ id, type, width, height, position: { x: 40, y: 60 } });

const edge = (
    id: string,
    source: string,
    target: string,
    category: 'attachment' | 'context' | 'prompt',
): GraphAutoLayoutEdge => ({
    id,
    source,
    target,
    sourceHandle: null,
    targetHandle: `${category}_${target}`,
});

const expectNoOverlaps = (
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => {
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
            const left = nodes[leftIndex]!;
            const right = nodes[rightIndex]!;
            const leftPosition = positions.get(left.id)!;
            const rightPosition = positions.get(right.id)!;
            expect(
                leftPosition.x < rightPosition.x + right.width &&
                    leftPosition.x + left.width > rightPosition.x &&
                    leftPosition.y < rightPosition.y + right.height &&
                    leftPosition.y + left.height > rightPosition.y,
            ).toBe(false);
        }
    }
};

describe('graph auto-layout attachment stacks', () => {
    it('qualifies a direct singleton attachment group for target-local placement', () => {
        const nodes = [
            node('singleton-file', NodeTypeEnum.FILE_PROMPT, 140, 60),
            node('generator', NodeTypeEnum.TEXT_TO_TEXT, 220, 120),
        ];
        const subgraph = {
            members: ['generator', 'singleton-file'],
            edges: [
                { source: 'singleton-file', target: 'generator', category: 'attachment' as const },
            ],
        };

        expect(partitionAttachmentStackSubgraphs([subgraph], nodes, new Set(['generator']))).toEqual({
            stacks: [{ targetId: 'generator', sourceIds: ['singleton-file'] }],
            fallback: [],
        });
    });

    it('stacks production FilePrompt and GitHub inputs beside the generator spine', () => {
        const nodes = [
            node('prompt1', NodeTypeEnum.PROMPT, 280, 100),
            node('attachment-file', NodeTypeEnum.FILE_PROMPT, 140, 80),
            node('attachment-github', NodeTypeEnum.GITHUB, 200, 120),
            node('generator1', NodeTypeEnum.TEXT_TO_TEXT, 240, 140),
            node('prompt2', NodeTypeEnum.PROMPT, 180, 90),
            node('generator2', NodeTypeEnum.TEXT_TO_TEXT, 260, 160),
        ];
        const edges = [
            edge('prompt1-generator1', 'prompt1', 'generator1', 'prompt'),
            edge('file-generator1', 'attachment-file', 'generator1', 'attachment'),
            edge('github-generator1', 'attachment-github', 'generator1', 'attachment'),
            edge('generator1-generator2', 'generator1', 'generator2', 'context'),
            edge('prompt2-generator2', 'prompt2', 'generator2', 'prompt'),
        ];
        const originalNodes = structuredClone(nodes);
        const originalEdges = structuredClone(edges);
        const positions = calculateGraphAutoLayout(nodes, edges);
        const shuffled = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());
        const position = (id: string) => positions.get(id)!;
        const dimensions = (id: string) => nodes.find((candidate) => candidate.id === id)!;
        const centerX = (id: string) => position(id).x + dimensions(id).width / 2;
        const centerY = (id: string) => position(id).y + dimensions(id).height / 2;
        const right = (id: string) => position(id).x + dimensions(id).width;

        expect([...shuffled]).toEqual([...positions]);
        expect(nodes).toEqual(originalNodes);
        expect(edges).toEqual(originalEdges);
        expect(position('attachment-file').y + 80 + GRAPH_AUTO_LAYOUT_EDGE_SEPARATION).toBe(
            position('attachment-github').y,
        );
        expect(right('attachment-file')).toBe(right('attachment-github'));
        expect(
            (position('attachment-file').y + position('attachment-github').y + 120) / 2,
        ).toBe(centerY('generator1'));
        expect(position('generator1').x - right('attachment-file')).toBe(
            GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        );
        expect(centerX('generator1')).toBe(centerX('generator2'));
        expect(position('generator1').y - (position('prompt1').y + 100)).toBe(
            GRAPH_AUTO_LAYOUT_RANK_SEPARATION,
        );
        expect(position('prompt2').y - (position('generator1').y + 140)).toBe(
            GRAPH_AUTO_LAYOUT_RANK_SEPARATION,
        );
        expect(position('generator2').y - (position('prompt2').y + 90)).toBe(
            GRAPH_AUTO_LAYOUT_RANK_SEPARATION,
        );
        expectNoOverlaps(nodes, positions);
    });

    it('reserves local envelopes for mixed stacks inside a dense fan-out composite', () => {
        const nodes = [
            node('root', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('prompt-a', NodeTypeEnum.PROMPT, 500, 200),
            node('top-a', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('a-file', NodeTypeEnum.FILE_PROMPT, 500, 275),
            node('prompt-b', NodeTypeEnum.PROMPT, 500, 200),
            node('top-b', NodeTypeEnum.ROUTING, 600, 300),
            node('prompt-c', NodeTypeEnum.PROMPT, 500, 200),
            node('top-c', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('c-file', NodeTypeEnum.FILE_PROMPT, 500, 275),
            node('prompt-d', NodeTypeEnum.PROMPT, 500, 200),
            node('top-d', NodeTypeEnum.ROUTING, 600, 300),
            node('prompt-e', NodeTypeEnum.PROMPT, 500, 200),
            node('top-e', NodeTypeEnum.ROUTING, 600, 300),
            node('prompt-lower-d', NodeTypeEnum.PROMPT, 500, 200),
            node('lower-d', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('d-file', NodeTypeEnum.FILE_PROMPT, 500, 275),
            node('d-github', NodeTypeEnum.GITHUB, 500, 250),
            node('prompt-tail-d', NodeTypeEnum.PROMPT, 500, 200),
            node('tail-d', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('prompt-lower-e', NodeTypeEnum.PROMPT, 500, 200),
            node('lower-e', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
            node('e-file-a', NodeTypeEnum.FILE_PROMPT, 500, 275),
            node('e-file-b', NodeTypeEnum.FILE_PROMPT, 500, 275),
            node('e-github', NodeTypeEnum.GITHUB, 500, 250),
            node('prompt-tail-e', NodeTypeEnum.PROMPT, 500, 200),
            node('tail-e', NodeTypeEnum.TEXT_TO_TEXT, 600, 300),
        ];
        const edges = [
            ...['a', 'b', 'c', 'd', 'e'].flatMap((suffix) => [
                edge(`root-${suffix}`, 'root', `top-${suffix}`, 'context'),
                edge(`prompt-${suffix}-edge`, `prompt-${suffix}`, `top-${suffix}`, 'prompt'),
            ]),
            edge('top-d-lower-d', 'top-d', 'lower-d', 'context'),
            edge('prompt-lower-d-edge', 'prompt-lower-d', 'lower-d', 'prompt'),
            edge('lower-d-tail-d', 'lower-d', 'tail-d', 'context'),
            edge('prompt-tail-d-edge', 'prompt-tail-d', 'tail-d', 'prompt'),
            edge('top-e-lower-e', 'top-e', 'lower-e', 'context'),
            edge('prompt-lower-e-edge', 'prompt-lower-e', 'lower-e', 'prompt'),
            edge('lower-e-tail-e', 'lower-e', 'tail-e', 'context'),
            edge('prompt-tail-e-edge', 'prompt-tail-e', 'tail-e', 'prompt'),
            edge('a-file-edge', 'a-file', 'top-a', 'attachment'),
            edge('c-file-edge', 'c-file', 'top-c', 'attachment'),
            edge('d-file-edge', 'd-file', 'lower-d', 'attachment'),
            edge('d-github-edge', 'd-github', 'lower-d', 'attachment'),
            edge('e-file-a-edge', 'e-file-a', 'lower-e', 'attachment'),
            edge('e-file-b-edge', 'e-file-b', 'lower-e', 'attachment'),
            edge('e-github-edge', 'e-github', 'lower-e', 'attachment'),
        ];
        const originalNodes = structuredClone(nodes);
        const originalEdges = structuredClone(edges);
        const positions = calculateGraphAutoLayout(nodes, edges);
        const reversed = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());
        const dimensions = (id: string) => nodes.find((candidate) => candidate.id === id)!;
        const right = (id: string) => positions.get(id)!.x + dimensions(id).width;
        const centerY = (id: string) => positions.get(id)!.y + dimensions(id).height / 2;
        const groups = [
            { targetId: 'top-a', sourceIds: ['a-file'] },
            { targetId: 'top-c', sourceIds: ['c-file'] },
            { targetId: 'lower-d', sourceIds: ['d-file', 'd-github'] },
            { targetId: 'lower-e', sourceIds: ['e-file-a', 'e-file-b', 'e-github'] },
        ];

        expect([...reversed]).toEqual([...positions]);
        expect(nodes).toEqual(originalNodes);
        expect(edges).toEqual(originalEdges);
        for (const { targetId, sourceIds } of groups) {
            expect(new Set(sourceIds.map(right)).size).toBe(1);
            expect(positions.get(targetId)!.x - right(sourceIds[0]!), targetId).toBe(
                GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
            );
            const groupTop = positions.get(sourceIds[0]!)!.y;
            const lastSourceId = sourceIds[sourceIds.length - 1]!;
            const groupBottom = positions.get(lastSourceId)!.y + dimensions(lastSourceId).height;
            expect(
                Math.abs((groupTop + groupBottom) / 2 - centerY(targetId)),
                targetId,
            ).toBeLessThanOrEqual(0.5);
        }
        expectNoOverlaps(nodes, positions);
    });

    it('right-aligns three variable-sized sources in stable lexical order', () => {
        const nodes = [
            node('prompt', NodeTypeEnum.PROMPT, 500, 80),
            node('attachment-c', NodeTypeEnum.GITHUB, 120, 60),
            node('attachment-a', NodeTypeEnum.FILE_PROMPT, 180, 90),
            node('attachment-b', NodeTypeEnum.GITHUB, 100, 110),
            node('generator', NodeTypeEnum.TEXT_TO_TEXT, 220, 130),
        ];
        const edges = [
            edge('prompt-generator', 'prompt', 'generator', 'prompt'),
            edge('c-generator', 'attachment-c', 'generator', 'attachment'),
            edge('a-generator', 'attachment-a', 'generator', 'attachment'),
            edge('b-generator', 'attachment-b', 'generator', 'attachment'),
        ];
        const positions = calculateGraphAutoLayout(nodes, edges);
        const right = (id: string) =>
            positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width;

        expect(positions.get('attachment-a')!.y + 90 + 40).toBe(positions.get('attachment-b')!.y);
        expect(positions.get('attachment-b')!.y + 110 + 40).toBe(positions.get('attachment-c')!.y);
        expect(new Set(['attachment-a', 'attachment-b', 'attachment-c'].map(right)).size).toBe(1);
        expectNoOverlaps(nodes, positions);
    });

    it('assigns overlapping branch-target stacks to separate deterministic lanes', () => {
        const nodes = [
            node('root', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
            node('generator-a', NodeTypeEnum.PARALLELIZATION, 200, 120),
            node('generator-b', NodeTypeEnum.ROUTING, 200, 120),
            node('a-file', NodeTypeEnum.FILE_PROMPT, 140, 100),
            node('a-github', NodeTypeEnum.GITHUB, 160, 100),
            node('b-file', NodeTypeEnum.FILE_PROMPT, 180, 100),
            node('b-github', NodeTypeEnum.GITHUB, 120, 100),
        ];
        const edges = [
            edge('root-a', 'root', 'generator-a', 'context'),
            edge('root-b', 'root', 'generator-b', 'context'),
            edge('a-file-edge', 'a-file', 'generator-a', 'attachment'),
            edge('a-github-edge', 'a-github', 'generator-a', 'attachment'),
            edge('b-file-edge', 'b-file', 'generator-b', 'attachment'),
            edge('b-github-edge', 'b-github', 'generator-b', 'attachment'),
        ];
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());
        const right = (id: string) =>
            first.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width;

        expect([...second]).toEqual([...first]);
        expect(right('a-file')).toBe(right('a-github'));
        expect(right('b-file')).toBe(right('b-github'));
        expect(right('a-file')).not.toBe(right('b-file'));
        expectNoOverlaps(nodes, first);
    });

    it('keeps screenshot-shaped distant stacks beside their own targets', () => {
        const nodes = [
            node('far-left-core', NodeTypeEnum.TEXT_TO_TEXT, 220, 900),
            node('target-left', NodeTypeEnum.PARALLELIZATION, 240, 120),
            node('left-file', NodeTypeEnum.FILE_PROMPT, 140, 80),
            node('left-github', NodeTypeEnum.GITHUB, 180, 100),
            node('target-right', NodeTypeEnum.ROUTING, 260, 120),
            node('right-file', NodeTypeEnum.FILE_PROMPT, 160, 90),
            node('right-github', NodeTypeEnum.GITHUB, 120, 70),
        ];
        const stacks = [
            { targetId: 'target-left', sourceIds: ['left-file', 'left-github'] },
            { targetId: 'target-right', sourceIds: ['right-file', 'right-github'] },
        ];
        const corePositions = new Map([
            ['far-left-core', { x: -600, y: 0 }],
            ['target-left', { x: 400, y: 100 }],
            ['target-right', { x: 1300, y: 500 }],
        ]);
        const originalNodes = structuredClone(nodes);
        const first = placeAttachmentStacks(stacks, nodes, corePositions, {
            node: GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
            edge: GRAPH_AUTO_LAYOUT_EDGE_SEPARATION,
        });
        const second = placeAttachmentStacks(
            [...stacks].reverse(),
            [...nodes].reverse(),
            new Map([...corePositions].reverse()),
            {
                node: GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
                edge: GRAPH_AUTO_LAYOUT_EDGE_SEPARATION,
            },
        );
        const right = (id: string) =>
            first.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width;

        expect([...second]).toEqual([...first]);
        expect(nodes).toEqual(originalNodes);
        expect(right('left-file')).toBe(right('left-github'));
        expect(right('right-file')).toBe(right('right-github'));
        expect(corePositions.get('target-left')!.x - right('left-file')).toBe(
            GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        );
        expect(corePositions.get('target-right')!.x - right('right-file')).toBe(
            GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        );
        expect(right('right-file')).toBeGreaterThan(right('left-file'));
    });

    it('shifts a target-local stack left to clear an overlapping core node', () => {
        const nodes = [
            node('blocking-core', NodeTypeEnum.TEXT_TO_TEXT, 120, 160),
            node('target', NodeTypeEnum.TEXT_TO_TEXT, 240, 120),
            node('stack-file', NodeTypeEnum.FILE_PROMPT, 140, 80),
            node('stack-github', NodeTypeEnum.GITHUB, 180, 100),
        ];
        const corePositions = new Map([
            ['blocking-core', { x: 500, y: 80 }],
            ['target', { x: 900, y: 100 }],
        ]);
        const positions = placeAttachmentStacks(
            [{ targetId: 'target', sourceIds: ['stack-file', 'stack-github'] }],
            nodes,
            corePositions,
            {
                node: GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
                edge: GRAPH_AUTO_LAYOUT_EDGE_SEPARATION,
            },
        );
        const right = positions.get('stack-file')!.x + 140;

        expect(right).toBe(corePositions.get('blocking-core')!.x - GRAPH_AUTO_LAYOUT_NODE_SEPARATION);
        expect(positions.get('stack-github')!.x + 180).toBe(right);
        expectNoOverlaps(nodes, new Map([...corePositions, ...positions]));
    });

    it('keeps an ambiguous shared attachment source in the LR fallback', () => {
        const nodes = [
            node('root', NodeTypeEnum.TEXT_TO_TEXT, 200, 100),
            node('generator-a', NodeTypeEnum.PARALLELIZATION, 180, 120),
            node('generator-b', NodeTypeEnum.ROUTING, 220, 120),
            node('shared-file', NodeTypeEnum.FILE_PROMPT, 140, 80),
            node('github-a', NodeTypeEnum.GITHUB, 160, 100),
        ];
        const edges = [
            edge('root-a', 'root', 'generator-a', 'context'),
            edge('root-b', 'root', 'generator-b', 'context'),
            edge('shared-a', 'shared-file', 'generator-a', 'attachment'),
            edge('shared-b', 'shared-file', 'generator-b', 'attachment'),
            edge('github-a', 'github-a', 'generator-a', 'attachment'),
        ];
        const positions = calculateGraphAutoLayout(nodes, edges);
        const centerY = (id: string) =>
            positions.get(id)!.y + nodes.find((candidate) => candidate.id === id)!.height / 2;

        expect(centerY('shared-file')).toBe(centerY('generator-a'));
        expect(centerY('github-a')).toBe(centerY('generator-a'));
        expect(positions.get('shared-file')!.x).not.toBe(positions.get('github-a')!.x);
        expectNoOverlaps(nodes, positions);
    });

    it('keeps direct-star qualification bounded across many deterministic stacks', () => {
        const nodes: GraphAutoLayoutNode[] = [];
        const edges: GraphAutoLayoutEdge[] = [];
        for (let index = 0; index < 24; index += 1) {
            const suffix = index.toString().padStart(2, '0');
            nodes.push(node(`generator-${suffix}`, NodeTypeEnum.TEXT_TO_TEXT, 180, 100));
            nodes.push(node(`file-${suffix}`, NodeTypeEnum.FILE_PROMPT, 120, 70));
            nodes.push(node(`github-${suffix}`, NodeTypeEnum.GITHUB, 140, 90));
            edges.push(edge(`file-edge-${suffix}`, `file-${suffix}`, `generator-${suffix}`, 'attachment'));
            edges.push(edge(`github-edge-${suffix}`, `github-${suffix}`, `generator-${suffix}`, 'attachment'));
            if (index > 0) {
                const previous = (index - 1).toString().padStart(2, '0');
                edges.push(
                    edge(
                        `context-${suffix}`,
                        `generator-${previous}`,
                        `generator-${suffix}`,
                        'context',
                    ),
                );
            }
        }
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());

        expect(first.size).toBe(nodes.length);
        expect([...second]).toEqual([...first]);
        expect([...first.values()].every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
    });
});
