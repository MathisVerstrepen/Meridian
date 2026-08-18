import { describe, expect, it } from 'vitest';

import { NodeTypeEnum } from '@/types/enums';
import {
    calculateGraphAutoLayout,
    GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
    type GraphAutoLayoutEdge,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';
import type {
    LayoutConstraintEdge,
    LayoutHorizontalBlock,
} from '@/utils/graphAutoLayoutConstraints';
import { mergeSerialSpinePromptBlocks } from '@/utils/graphAutoLayoutSerialPrompts';

const node = (
    id: string,
    type: NodeTypeEnum,
    width: number,
    height: number,
): GraphAutoLayoutNode => ({ id, type, width, height, position: { x: 25, y: 45 } });

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

const centerX = (
    id: string,
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width / 2;

describe('graph auto-layout serial prompts', () => {
    it('keeps a downstream prompt handle-aligned in isolated and embedded serial stages', () => {
        const serialNodes = [
            node('generator', NodeTypeEnum.TEXT_TO_TEXT, 220, 110),
            node('prompt', NodeTypeEnum.PROMPT, 160, 80),
            node('downstream', NodeTypeEnum.TEXT_TO_TEXT, 300, 140),
        ];
        const serialEdges = [
            edge('generator-downstream', 'generator', 'downstream', 'context'),
            edge('prompt-downstream', 'prompt', 'downstream', 'prompt'),
        ];
        const originalNodes = structuredClone(serialNodes);
        const originalEdges = structuredClone(serialEdges);
        const isolated = calculateGraphAutoLayout(serialNodes, serialEdges);
        const embeddedNodes = [
            ...serialNodes,
            node('upstream', NodeTypeEnum.TEXT_TO_TEXT, 180, 90),
            node('side-1', NodeTypeEnum.TEXT_TO_TEXT, 150, 80),
            node('side-2', NodeTypeEnum.TEXT_TO_TEXT, 140, 70),
            node('side-3', NodeTypeEnum.TEXT_TO_TEXT, 160, 100),
        ];
        const embeddedEdges = [
            ...serialEdges,
            edge('upstream-generator', 'upstream', 'generator', 'context'),
            edge('upstream-side-1', 'upstream', 'side-1', 'context'),
            edge('side-1-side-2', 'side-1', 'side-2', 'context'),
            edge('side-2-side-3', 'side-2', 'side-3', 'context'),
        ];
        const embedded = calculateGraphAutoLayout(embeddedNodes, embeddedEdges);
        const reversed = calculateGraphAutoLayout(
            [...embeddedNodes].reverse(),
            [...embeddedEdges].reverse(),
        );
        const relative = (
            positions: ReadonlyMap<string, { x: number; y: number }>,
            id: string,
        ) => ({
            x: positions.get(id)!.x - positions.get('generator')!.x,
            y: positions.get(id)!.y - positions.get('generator')!.y,
        });

        expect(['generator', 'prompt', 'downstream'].map((id) => relative(embedded, id))).toEqual(
            ['generator', 'prompt', 'downstream'].map((id) => relative(isolated, id)),
        );
        expect([...reversed]).toEqual([...embedded]);
        expect(serialNodes).toEqual(originalNodes);
        expect(serialEdges).toEqual(originalEdges);
        expect(centerX('generator', embeddedNodes, embedded)).toBe(
            centerX('downstream', embeddedNodes, embedded),
        );
        expect(
            Math.abs(
                centerX('prompt', embeddedNodes, embedded) -
                    (embedded.get('downstream')!.x + 0.33 * 300),
            ),
        ).toBeLessThanOrEqual(1);
        expect(embedded.get('generator')!.y).toBeLessThan(embedded.get('prompt')!.y);
        expect(embedded.get('prompt')!.y).toBeLessThan(embedded.get('downstream')!.y);
        expect(embedded.size).toBe(embeddedNodes.length);
        expectNoOverlaps(embeddedNodes, embedded);
    });

    it('keeps downstream prompts rigid inside prompted fan-out tail blocks', () => {
        const nodes = [
            node('root', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
            node('branch-prompt-1', NodeTypeEnum.PROMPT, 140, 80),
            node('child-1', NodeTypeEnum.PARALLELIZATION, 200, 110),
            node('tail-prompt-1', NodeTypeEnum.PROMPT, 180, 80),
            node('tail-1', NodeTypeEnum.TEXT_TO_TEXT, 300, 130),
            node('branch-prompt-2', NodeTypeEnum.PROMPT, 230, 90),
            node('child-2', NodeTypeEnum.ROUTING, 180, 120),
            node('tail-prompt-2', NodeTypeEnum.PROMPT, 150, 70),
            node('tail-2', NodeTypeEnum.TEXT_TO_TEXT, 240, 110),
        ];
        const edges = [
            edge('root-child-1', 'root', 'child-1', 'context'),
            edge('root-child-2', 'root', 'child-2', 'context'),
            edge('branch-prompt-child-1', 'branch-prompt-1', 'child-1', 'prompt'),
            edge('branch-prompt-child-2', 'branch-prompt-2', 'child-2', 'prompt'),
            edge('child-tail-1', 'child-1', 'tail-1', 'context'),
            edge('child-tail-2', 'child-2', 'tail-2', 'context'),
            edge('tail-prompt-tail-1', 'tail-prompt-1', 'tail-1', 'prompt'),
            edge('tail-prompt-tail-2', 'tail-prompt-2', 'tail-2', 'prompt'),
        ];
        const positions = calculateGraphAutoLayout(nodes, edges);
        const targetOffset = (promptId: string, targetId: string) =>
            Math.abs(
                centerX(promptId, nodes, positions) -
                    (positions.get(targetId)!.x +
                        0.33 * nodes.find((candidate) => candidate.id === targetId)!.width),
            );

        expect(centerX('branch-prompt-1', nodes, positions)).toBe(
            centerX('child-1', nodes, positions),
        );
        expect(centerX('branch-prompt-2', nodes, positions)).toBe(
            centerX('child-2', nodes, positions),
        );
        expect(centerX('child-1', nodes, positions)).toBe(centerX('tail-1', nodes, positions));
        expect(centerX('child-2', nodes, positions)).toBe(centerX('tail-2', nodes, positions));
        expect(targetOffset('tail-prompt-1', 'tail-1')).toBeLessThanOrEqual(1);
        expect(targetOffset('tail-prompt-2', 'tail-2')).toBeLessThanOrEqual(1);

        const branchEnvelopes = [1, 2].map((index) => {
            const ids = [
                `branch-prompt-${index}`,
                `child-${index}`,
                `tail-prompt-${index}`,
                `tail-${index}`,
            ];
            return {
                left: Math.min(...ids.map((id) => positions.get(id)!.x)),
                right: Math.max(
                    ...ids.map(
                        (id) =>
                            positions.get(id)!.x +
                            nodes.find((candidate) => candidate.id === id)!.width,
                    ),
                ),
            };
        });
        expect(branchEnvelopes[1]!.left - branchEnvelopes[0]!.right).toBeGreaterThanOrEqual(
            GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        );
        expect(centerX('root', nodes, positions)).toBe(
            (branchEnvelopes[0]!.left + branchEnvelopes[1]!.right) / 2,
        );
        expect(positions.size).toBe(nodes.length);
        expectNoOverlaps(nodes, positions);
    });

    it('returns blocks unchanged for conservative serial-prompt fallbacks', () => {
        interface Fixture {
            nodes: GraphAutoLayoutNode[];
            edges: LayoutConstraintEdge[];
            blocks: LayoutHorizontalBlock[];
            rows: Map<string, number>;
        }
        const fixture = (): Fixture => ({
            nodes: [
                node('generator', NodeTypeEnum.TEXT_TO_TEXT, 200, 100),
                node('prompt', NodeTypeEnum.PROMPT, 140, 80),
                node('downstream', NodeTypeEnum.TEXT_TO_TEXT, 300, 120),
            ],
            edges: [
                { source: 'generator', target: 'downstream', category: 'context' },
                { source: 'prompt', target: 'downstream', category: 'prompt' },
            ],
            blocks: [
                {
                    id: 'generator',
                    preferredLeft: 400,
                    members: [
                        { id: 'generator', left: -100 },
                        { id: 'downstream', left: -150 },
                    ],
                },
                { id: 'prompt', preferredLeft: 20, members: [{ id: 'prompt', left: 0 }] },
            ],
            rows: new Map([
                ['generator', 0],
                ['prompt', 1],
                ['downstream', 2],
            ]),
        });
        const cases: Fixture[] = [];

        const multiple = fixture();
        multiple.nodes.push(node('prompt-2', NodeTypeEnum.PROMPT, 120, 70));
        multiple.edges.push({ source: 'prompt-2', target: 'downstream', category: 'prompt' });
        multiple.blocks.push({ id: 'prompt-2', preferredLeft: 0, members: [{ id: 'prompt-2', left: 0 }] });
        multiple.rows.set('prompt-2', 1);
        cases.push(multiple);

        const shared = fixture();
        shared.nodes.push(
            node('generator-2', NodeTypeEnum.TEXT_TO_TEXT, 180, 90),
            node('downstream-2', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
        );
        shared.edges.push(
            { source: 'generator-2', target: 'downstream-2', category: 'context' },
            { source: 'prompt', target: 'downstream-2', category: 'prompt' },
        );
        shared.blocks.push({
            id: 'generator-2',
            preferredLeft: 0,
            members: [
                { id: 'generator-2', left: -90 },
                { id: 'downstream-2', left: -110 },
            ],
        });
        shared.rows.set('generator-2', 0);
        shared.rows.set('downstream-2', 2);
        cases.push(shared);

        const nonPrompt = fixture();
        nonPrompt.nodes[1] = node('prompt', NodeTypeEnum.FILE_PROMPT, 140, 80);
        cases.push(nonPrompt);

        const multiPredecessor = fixture();
        multiPredecessor.nodes.push(node('other', NodeTypeEnum.TEXT_TO_TEXT, 180, 90));
        multiPredecessor.edges.push({ source: 'other', target: 'downstream', category: 'context' });
        cases.push(multiPredecessor);

        const multiSuccessor = fixture();
        multiSuccessor.nodes.push(node('other', NodeTypeEnum.TEXT_TO_TEXT, 180, 90));
        multiSuccessor.edges.push({ source: 'generator', target: 'other', category: 'context' });
        cases.push(multiSuccessor);

        const cycle = fixture();
        cycle.edges.push({ source: 'downstream', target: 'generator', category: 'context' });
        cases.push(cycle);

        const missingRow = fixture();
        missingRow.rows.delete('prompt');
        cases.push(missingRow);

        const missingBlock = fixture();
        missingBlock.blocks.pop();
        cases.push(missingBlock);

        const missingPrompt = fixture();
        missingPrompt.edges.pop();
        cases.push(missingPrompt);

        const reusedBlock = fixture();
        reusedBlock.nodes.push(node('prompt-2', NodeTypeEnum.PROMPT, 120, 70));
        reusedBlock.edges.push({ source: 'prompt-2', target: 'downstream', category: 'prompt' });
        reusedBlock.blocks[1]!.members.push({ id: 'prompt-2', left: 10 });
        reusedBlock.rows.set('prompt-2', 1);
        cases.push(reusedBlock);

        for (const input of cases) {
            const original = structuredClone({
                nodes: input.nodes,
                edges: input.edges,
                blocks: input.blocks,
                rows: [...input.rows],
            });
            const result = mergeSerialSpinePromptBlocks(
                input.nodes,
                input.edges,
                input.blocks,
                input.rows,
            );
            expect(result).toEqual(input.blocks);
            expect({
                nodes: input.nodes,
                edges: input.edges,
                blocks: input.blocks,
                rows: [...input.rows],
            }).toEqual(original);
        }
    });
});
