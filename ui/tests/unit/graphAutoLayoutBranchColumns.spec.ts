import { describe, expect, it } from 'vitest';

import { NodeTypeEnum } from '@/types/enums';
import {
    calculateGraphAutoLayout,
    GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
    type GraphAutoLayoutEdge,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';

const node = (
    id: string,
    type: NodeTypeEnum,
    width: number,
    height: number,
): GraphAutoLayoutNode => ({ id, type, width, height, position: { x: 30, y: 50 } });

const edge = (
    id: string,
    source: string,
    target: string,
    category: 'context' | 'prompt',
): GraphAutoLayoutEdge => ({
    id,
    source,
    target,
    sourceHandle: null,
    targetHandle: `${category}_${target}`,
});

const fanout = (prefix = ''): { nodes: GraphAutoLayoutNode[]; edges: GraphAutoLayoutEdge[] } => {
    const root = `${prefix}root`;
    const promptWidths = [130, 210, 170, 250];
    const childWidths = [220, 160, 280, 190];
    const nodes = [node(root, NodeTypeEnum.TEXT_TO_TEXT, 240, 120)];
    const edges: GraphAutoLayoutEdge[] = [];
    for (let index = 1; index <= 4; index += 1) {
        const promptId = `${prefix}prompt-${index}`;
        const childId = `${prefix}child-${index}`;
        nodes.push(node(promptId, NodeTypeEnum.PROMPT, promptWidths[index - 1]!, 70 + index * 5));
        nodes.push(
            node(childId, NodeTypeEnum.TEXT_TO_TEXT, childWidths[index - 1]!, 100 + index * 10),
        );
        edges.push(edge(`${prefix}root-child-${index}`, root, childId, 'context'));
        edges.push(edge(`${prefix}prompt-child-${index}`, promptId, childId, 'prompt'));
    }
    return { nodes, edges };
};

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
            const overlaps =
                leftPosition.x < rightPosition.x + right.width &&
                leftPosition.x + left.width > rightPosition.x &&
                leftPosition.y < rightPosition.y + right.height &&
                leftPosition.y + left.height > rightPosition.y;
            expect(overlaps, `${left.id} overlaps ${right.id}`).toBe(false);
        }
    }
};

const expectFiniteCompleteLayout = (
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => {
    expect(positions.size).toBe(nodes.length);
    expect([...positions.values()].every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(
        true,
    );
    expectNoOverlaps(nodes, positions);
};

describe('graph auto-layout prompted branch columns', () => {
    it('keeps isolated fan-out geometry invariant inside connected rank-sharing topology', () => {
        const isolated = fanout();
        const originalNodes = structuredClone(isolated.nodes);
        const originalEdges = structuredClone(isolated.edges);
        const isolatedPositions = calculateGraphAutoLayout(isolated.nodes, isolated.edges);
        const embeddedNodes = [
            ...isolated.nodes,
            node('upstream', NodeTypeEnum.TEXT_TO_TEXT, 180, 90),
            node('side-1', NodeTypeEnum.TEXT_TO_TEXT, 150, 80),
            node('side-2', NodeTypeEnum.TEXT_TO_TEXT, 140, 70),
            node('side-3', NodeTypeEnum.TEXT_TO_TEXT, 160, 90),
        ];
        const embeddedEdges = [
            ...isolated.edges,
            edge('upstream-root', 'upstream', 'root', 'context'),
            edge('upstream-side-1', 'upstream', 'side-1', 'context'),
            edge('side-1-side-2', 'side-1', 'side-2', 'context'),
            edge('side-2-side-3', 'side-2', 'side-3', 'context'),
        ];
        const embeddedPositions = calculateGraphAutoLayout(embeddedNodes, embeddedEdges);
        const shuffledPositions = calculateGraphAutoLayout(
            [...embeddedNodes].reverse(),
            [...embeddedEdges].reverse(),
        );
        const cohortIds = [
            'root',
            ...Array.from({ length: 4 }, (_, index) => `prompt-${index + 1}`),
            ...Array.from({ length: 4 }, (_, index) => `child-${index + 1}`),
        ];
        const relative = (
            positions: ReadonlyMap<string, { x: number; y: number }>,
            id: string,
        ) => ({
            x: positions.get(id)!.x - positions.get('root')!.x,
            y: positions.get(id)!.y - positions.get('root')!.y,
        });
        const dimensions = (id: string) => embeddedNodes.find((candidate) => candidate.id === id)!;
        const centerX = (id: string) =>
            embeddedPositions.get(id)!.x + dimensions(id).width / 2;

        expect(cohortIds.map((id) => relative(embeddedPositions, id))).toEqual(
            cohortIds.map((id) => relative(isolatedPositions, id)),
        );
        expect([...shuffledPositions]).toEqual([...embeddedPositions]);
        expect(isolated.nodes).toEqual(originalNodes);
        expect(isolated.edges).toEqual(originalEdges);
        for (let index = 1; index <= 4; index += 1) {
            expect(centerX(`prompt-${index}`)).toBe(centerX(`child-${index}`));
        }

        const envelopes = Array.from({ length: 4 }, (_, index) => {
            const ids = [`prompt-${index + 1}`, `child-${index + 1}`];
            return {
                left: Math.min(...ids.map((id) => embeddedPositions.get(id)!.x)),
                right: Math.max(
                    ...ids.map((id) => embeddedPositions.get(id)!.x + dimensions(id).width),
                ),
            };
        });
        for (let index = 1; index < envelopes.length; index += 1) {
            expect(envelopes[index]!.left - envelopes[index - 1]!.right).toBeGreaterThanOrEqual(
                GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
            );
        }
        expect(centerX('root')).toBe((envelopes[0]!.left + envelopes[3]!.right) / 2);
        expectFiniteCompleteLayout(embeddedNodes, embeddedPositions);
    });

    it('preserves each child serial tail as part of its rigid branch', () => {
        const nodes = [
            node('root', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
            node('prompt-1', NodeTypeEnum.PROMPT, 140, 80),
            node('child-1', NodeTypeEnum.PARALLELIZATION, 200, 110),
            node('tail-1', NodeTypeEnum.TEXT_TO_TEXT, 260, 120),
            node('prompt-2', NodeTypeEnum.PROMPT, 230, 90),
            node('child-2', NodeTypeEnum.ROUTING, 180, 130),
            node('tail-2', NodeTypeEnum.TEXT_TO_TEXT, 150, 100),
        ];
        const edges = [
            edge('root-child-1', 'root', 'child-1', 'context'),
            edge('root-child-2', 'root', 'child-2', 'context'),
            edge('prompt-child-1', 'prompt-1', 'child-1', 'prompt'),
            edge('prompt-child-2', 'prompt-2', 'child-2', 'prompt'),
            edge('child-tail-1', 'child-1', 'tail-1', 'context'),
            edge('child-tail-2', 'child-2', 'tail-2', 'context'),
        ];
        const positions = calculateGraphAutoLayout(nodes, edges);
        const centerX = (id: string) =>
            positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width / 2;

        expect(centerX('prompt-1')).toBe(centerX('child-1'));
        expect(centerX('child-1')).toBe(centerX('tail-1'));
        expect(centerX('prompt-2')).toBe(centerX('child-2'));
        expect(centerX('child-2')).toBe(centerX('tail-2'));
        expect(centerX('child-1')).not.toBe(centerX('child-2'));
        expectFiniteCompleteLayout(nodes, positions);
    });

    it('falls back safely for multiple, missing, and multiply-parented prompts', () => {
        const cases = [
            () => {
                const graph = fanout('multiple-');
                graph.nodes.push(node('multiple-extra-prompt', NodeTypeEnum.PROMPT, 120, 80));
                graph.edges.push(
                    edge(
                        'multiple-extra-edge',
                        'multiple-extra-prompt',
                        'multiple-child-1',
                        'prompt',
                    ),
                );
                return graph;
            },
            () => {
                const graph = fanout('missing-');
                graph.edges = graph.edges.filter((candidate) => candidate.id !== 'missing-prompt-child-4');
                return graph;
            },
            () => {
                const graph = fanout('parented-');
                graph.nodes.push(node('parented-other', NodeTypeEnum.TEXT_TO_TEXT, 180, 100));
                graph.edges.push(
                    edge('parented-other-child', 'parented-other', 'parented-child-1', 'context'),
                );
                return graph;
            },
        ];

        for (const createGraph of cases) {
            const graph = createGraph();
            const positions = calculateGraphAutoLayout(graph.nodes, graph.edges);
            const shuffled = calculateGraphAutoLayout(
                [...graph.nodes].reverse(),
                [...graph.edges].reverse(),
            );
            expect([...shuffled]).toEqual([...positions]);
            expectFiniteCompleteLayout(graph.nodes, positions);
        }
    });

    it('lays out many disjoint qualifying cohorts completely and deterministically', () => {
        const nodes: GraphAutoLayoutNode[] = [];
        const edges: GraphAutoLayoutEdge[] = [];
        for (let index = 0; index < 10; index += 1) {
            const graph = fanout(`cohort-${index.toString().padStart(2, '0')}-`);
            nodes.push(...graph.nodes);
            edges.push(...graph.edges);
        }
        const positions = calculateGraphAutoLayout(nodes, edges);
        const shuffled = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());

        expect([...shuffled]).toEqual([...positions]);
        expectFiniteCompleteLayout(nodes, positions);
    });
});
