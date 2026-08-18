import { describe, expect, it } from 'vitest';

import { NodeTypeEnum } from '@/types/enums';
import {
    calculateGraphAutoLayout,
    type GraphAutoLayoutEdge,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';
import { mergePromptFanoutStageBlocks } from '@/utils/graphAutoLayoutBranchColumns';
import type { LayoutConstraintEdge, LayoutHorizontalBlock } from '@/utils/graphAutoLayoutConstraints';
import { discoverFanoutHierarchy } from '@/utils/graphAutoLayoutFanoutHierarchy';

const node = (id: string, type: NodeTypeEnum, width: number, height: number): GraphAutoLayoutNode => ({
    id,
    type,
    width,
    height,
    position: { x: 35, y: 55 },
});
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
const centerX = (
    id: string,
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width / 2;
const bounds = (
    ids: readonly string[],
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => ({
    left: Math.min(...ids.map((id) => positions.get(id)!.x)),
    right: Math.max(
        ...ids.map((id) =>
            positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width,
        ),
    ),
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
                `${left.id} overlaps ${right.id}`,
            ).toBe(false);
        }
    }
};

const screenshotCohort = () => {
    const nodes = [
        node('upper', NodeTypeEnum.TEXT_TO_TEXT, 240, 110),
        node('shared-prompt', NodeTypeEnum.PROMPT, 180, 80),
        node('child-a', NodeTypeEnum.TEXT_TO_TEXT, 170, 100),
        node('child-b', NodeTypeEnum.ROUTING, 220, 120),
        node('child-c', NodeTypeEnum.PARALLELIZATION, 260, 130),
        ...[1, 2, 3, 4].flatMap((index) => [
            node(`nested-prompt-${index}`, NodeTypeEnum.PROMPT, 120 + index * 20, 70),
            node(`nested-child-${index}`, NodeTypeEnum.TEXT_TO_TEXT, 150 + index * 25, 100),
        ]),
        node('serial-prompt', NodeTypeEnum.PROMPT, 150, 70),
        node('serial-tail', NodeTypeEnum.TEXT_TO_TEXT, 280, 120),
    ];
    const edges: GraphAutoLayoutEdge[] = [];
    for (const childId of ['child-a', 'child-b', 'child-c']) {
        edges.push(edge(`upper-${childId}`, 'upper', childId, 'context'));
        edges.push(edge(`shared-${childId}`, 'shared-prompt', childId, 'prompt'));
    }
    for (let index = 1; index <= 4; index += 1) {
        edges.push(edge(`nested-context-${index}`, 'child-c', `nested-child-${index}`, 'context'));
        edges.push(
            edge(
                `nested-prompt-edge-${index}`,
                `nested-prompt-${index}`,
                `nested-child-${index}`,
                'prompt',
            ),
        );
    }
    edges.push(edge('nested-4-tail', 'nested-child-4', 'serial-tail', 'context'));
    edges.push(edge('serial-prompt-tail', 'serial-prompt', 'serial-tail', 'prompt'));
    return { nodes, edges };
};

describe('graph auto-layout fan-out hierarchy', () => {
    it('centers screenshot-shaped nested co-parent families isolated and embedded', () => {
        const cohort = screenshotCohort();
        const originalNodes = structuredClone(cohort.nodes);
        const originalEdges = structuredClone(cohort.edges);
        const isolated = calculateGraphAutoLayout(cohort.nodes, cohort.edges);
        const embeddedNodes = [
            ...cohort.nodes,
            node('upstream', NodeTypeEnum.TEXT_TO_TEXT, 150, 70),
            ...Array.from({ length: 7 }, (_, index) =>
                node(`side-${index}`, NodeTypeEnum.TEXT_TO_TEXT, 100, 50),
            ),
        ];
        const embeddedEdges = [
            ...cohort.edges,
            edge('upstream-upper', 'upstream', 'upper', 'context'),
            edge('upstream-side-0', 'upstream', 'side-0', 'context'),
            ...Array.from({ length: 6 }, (_, index) =>
                edge(`side-edge-${index}`, `side-${index}`, `side-${index + 1}`, 'context'),
            ),
        ];
        const embedded = calculateGraphAutoLayout(embeddedNodes, embeddedEdges);
        const reversed = calculateGraphAutoLayout(
            [...embeddedNodes].reverse(),
            [...embeddedEdges].reverse(),
        );
        const relative = (positions: ReadonlyMap<string, { x: number; y: number }>, id: string) => ({
            x: positions.get(id)!.x - positions.get('upper')!.x,
            y: positions.get(id)!.y - positions.get('upper')!.y,
        });
        const cohortIds = cohort.nodes.map(({ id }) => id);

        expect(cohortIds.map((id) => relative(embedded, id))).toEqual(
            cohortIds.map((id) => relative(isolated, id)),
        );
        expect([...reversed]).toEqual([...embedded]);
        expect(cohort.nodes).toEqual(originalNodes);
        expect(cohort.edges).toEqual(originalEdges);
        const nestedIds = cohortIds.filter((id) => id.startsWith('nested-') || id.startsWith('serial-'));
        const upperBranches = [
            bounds(['child-a'], embeddedNodes, embedded),
            bounds(['child-b'], embeddedNodes, embedded),
            bounds(['child-c', ...nestedIds], embeddedNodes, embedded),
        ];
        const upperMidpoint = (upperBranches[0]!.left + upperBranches[2]!.right) / 2;
        expect(Math.abs(centerX('upper', embeddedNodes, embedded) - upperMidpoint)).toBeLessThanOrEqual(1);
        expect(Math.abs(centerX('shared-prompt', embeddedNodes, embedded) - upperMidpoint)).toBeLessThanOrEqual(1);

        const nestedBranches = [1, 2, 3, 4].map((index) =>
            bounds(
                index === 4
                    ? [`nested-prompt-${index}`, `nested-child-${index}`, 'serial-prompt', 'serial-tail']
                    : [`nested-prompt-${index}`, `nested-child-${index}`],
                embeddedNodes,
                embedded,
            ),
        );
        expect(Math.abs(
            centerX('child-c', embeddedNodes, embedded) -
                (nestedBranches[0]!.left + nestedBranches[3]!.right) / 2,
        )).toBeLessThanOrEqual(1);
        for (let index = 1; index <= 4; index += 1) {
            expect(Math.abs(
                centerX(`nested-prompt-${index}`, embeddedNodes, embedded) -
                    centerX(`nested-child-${index}`, embeddedNodes, embedded),
            )).toBeLessThanOrEqual(1);
        }
        expect(centerX('nested-child-4', embeddedNodes, embedded)).toBe(
            centerX('serial-tail', embeddedNodes, embedded),
        );
        expect(Math.abs(
            centerX('serial-prompt', embeddedNodes, embedded) -
                (embedded.get('serial-tail')!.x + 0.33 * 280),
        )).toBeLessThanOrEqual(1);
        expectNoOverlaps(embeddedNodes, embedded);
    });

    it('centers promptless and mixed generator fan-outs', () => {
        for (const withDedicatedPrompt of [false, true]) {
            const nodes = [
                node('parent', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
                node('a', NodeTypeEnum.TEXT_TO_TEXT, 140, 90),
                node('b', NodeTypeEnum.ROUTING, 260, 120),
                node('c', NodeTypeEnum.PARALLELIZATION, 180, 100),
            ];
            const edges = ['a', 'b', 'c'].map((id) => edge(`parent-${id}`, 'parent', id, 'context'));
            if (withDedicatedPrompt) {
                nodes.push(node('b-prompt', NodeTypeEnum.PROMPT, 200, 70));
                edges.push(edge('b-prompt-edge', 'b-prompt', 'b', 'prompt'));
            }
            const positions = calculateGraphAutoLayout(nodes, edges);
            const branchIds = withDedicatedPrompt ? ['a', 'b-prompt', 'b', 'c'] : ['a', 'b', 'c'];
            const envelope = bounds(branchIds, nodes, positions);
            expect(Math.abs(
                centerX('parent', nodes, positions) - (envelope.left + envelope.right) / 2,
            )).toBeLessThanOrEqual(1);
            if (withDedicatedPrompt) {
                expect(centerX('b-prompt', nodes, positions)).toBe(centerX('b', nodes, positions));
            }
            expectNoOverlaps(nodes, positions);
        }
    });

    it('centers a standalone prompt parent over full child composites', () => {
        const nodes = [
            node('prompt-parent', NodeTypeEnum.PROMPT, 190, 80),
            node('a', NodeTypeEnum.TEXT_TO_TEXT, 140, 90),
            node('b', NodeTypeEnum.ROUTING, 250, 110),
            node('c', NodeTypeEnum.PARALLELIZATION, 180, 100),
            node('tail', NodeTypeEnum.TEXT_TO_TEXT, 300, 120),
        ];
        const edges = ['a', 'b', 'c'].map((id) =>
            edge(`prompt-${id}`, 'prompt-parent', id, 'prompt'),
        );
        edges.push(edge('c-tail', 'c', 'tail', 'context'));
        const positions = calculateGraphAutoLayout(nodes, edges);
        const branches = [
            bounds(['a'], nodes, positions),
            bounds(['b'], nodes, positions),
            bounds(['c', 'tail'], nodes, positions),
        ];

        expect(Math.abs(
            centerX('prompt-parent', nodes, positions) -
                (branches[0]!.left + branches[2]!.right) / 2,
        )).toBeLessThanOrEqual(1);
        expect(positions.size).toBe(nodes.length);
        expectNoOverlaps(nodes, positions);
    });

    it('rejects partial co-parent ownership and malformed block families atomically', () => {
        const nodes = [
            node('parent', NodeTypeEnum.TEXT_TO_TEXT, 200, 100),
            node('shared', NodeTypeEnum.PROMPT, 160, 80),
            node('a', NodeTypeEnum.TEXT_TO_TEXT, 140, 90),
            node('b', NodeTypeEnum.TEXT_TO_TEXT, 160, 90),
            node('c', NodeTypeEnum.TEXT_TO_TEXT, 180, 90),
        ];
        const edges: LayoutConstraintEdge[] = [
            { source: 'parent', target: 'a', category: 'context' },
            { source: 'parent', target: 'b', category: 'context' },
            { source: 'parent', target: 'c', category: 'context' },
            { source: 'shared', target: 'a', category: 'prompt' },
            { source: 'shared', target: 'b', category: 'prompt' },
        ];
        const rows = new Map([
            ['parent', 0], ['shared', 1], ['a', 2], ['b', 2], ['c', 1],
        ]);
        expect(discoverFanoutHierarchy(nodes, edges, rows)).toEqual([]);

        const blocks: LayoutHorizontalBlock[] = nodes.map(({ id }) => ({
            id,
            preferredLeft: 10,
            members: [{ id, left: 0 }],
        }));
        blocks.find(({ id }) => id === 'shared')!.members.push({ id: 'missing', left: 20 });
        const original = structuredClone({ nodes, edges, blocks, rows: [...rows] });
        expect(mergePromptFanoutStageBlocks(nodes, edges, blocks, rows, { node: 160 })).toEqual(blocks);
        expect({ nodes, edges, blocks, rows: [...rows] }).toEqual(original);
    });
});
