import { describe, expect, it } from 'vitest';

import { NodeTypeEnum } from '@/types/enums';
import {
    calculateGraphAutoLayout,
    GRAPH_AUTO_LAYOUT_COMPONENT_SEPARATION,
    GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
    type GraphAutoLayoutEdge,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';

const node = (
    id: string,
    width = 100,
    height = 100,
    position = { x: 40, y: 60 },
    parentNode?: string,
): GraphAutoLayoutNode => ({ id, width, height, position, parentNode });

const typedNode = (
    id: string,
    type: NodeTypeEnum,
    width = 100,
    height = 100,
): GraphAutoLayoutNode => ({ ...node(id, width, height), type });

const edge = (
    id: string,
    source: string,
    target: string,
    sourceHandle?: string | null,
    targetHandle?: string | null,
): GraphAutoLayoutEdge => ({
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
});

const overlap = (
    left: GraphAutoLayoutNode,
    leftPosition: { x: number; y: number },
    right: GraphAutoLayoutNode,
    rightPosition: { x: number; y: number },
) =>
    leftPosition.x < rightPosition.x + right.width &&
    leftPosition.x + left.width > rightPosition.x &&
    leftPosition.y < rightPosition.y + right.height &&
    leftPosition.y + left.height > rightPosition.y;

const expectNoOverlaps = (
    nodes: readonly GraphAutoLayoutNode[],
    positions: ReadonlyMap<string, { x: number; y: number }>,
) => {
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
            const left = nodes[leftIndex];
            const right = nodes[rightIndex];
            if (!left || !right) continue;
            const leftPosition = positions.get(left.id);
            const rightPosition = positions.get(right.id);
            expect(leftPosition).toBeDefined();
            expect(rightPosition).toBeDefined();
            expect(overlap(left, leftPosition!, right, rightPosition!)).toBe(false);
        }
    }
};

describe('calculateGraphAutoLayout', () => {
    it('lays out production GraphChat edges as ordered stages with a generator spine', () => {
        const nodes = [
            typedNode('prompt1', NodeTypeEnum.PROMPT, 180, 100),
            typedNode('attachment', NodeTypeEnum.FILE_PROMPT, 140, 80),
            typedNode('generator1', NodeTypeEnum.TEXT_TO_TEXT, 240, 140),
            typedNode('prompt2', NodeTypeEnum.PROMPT, 200, 90),
            typedNode('generator2', NodeTypeEnum.TEXT_TO_TEXT, 260, 160),
        ];
        const edges = [
            edge('prompt1-generator1', 'prompt1', 'generator1', null, 'prompt_generator1'),
            edge('attachment-generator1', 'attachment', 'generator1', null, 'attachment_generator1'),
            edge('generator1-generator2', 'generator1', 'generator2', null, 'context_generator2'),
            edge('prompt2-generator2', 'prompt2', 'generator2', null, 'prompt_generator2'),
        ];
        const originalNodes = structuredClone(nodes);
        const originalEdges = structuredClone(edges);

        const positions = calculateGraphAutoLayout(nodes, edges);
        const shuffled = calculateGraphAutoLayout(
            [nodes[4]!, nodes[2]!, nodes[0]!, nodes[3]!, nodes[1]!],
            [edges[2]!, edges[0]!, edges[3]!, edges[1]!],
        );
        const position = (id: string) => positions.get(id)!;
        const dimensions = (id: string) => nodes.find((candidate) => candidate.id === id)!;
        const centerX = (id: string) => position(id).x + dimensions(id).width / 2;
        const centerY = (id: string) => position(id).y + dimensions(id).height / 2;

        expect([...shuffled]).toEqual([...positions]);
        expect(nodes).toEqual(originalNodes);
        expect(edges).toEqual(originalEdges);
        expect(position('generator1').y).toBeGreaterThan(
            position('prompt1').y + dimensions('prompt1').height,
        );
        expect(centerY('attachment')).toBe(centerY('generator1'));
        expect(
            position('attachment').x +
                dimensions('attachment').width +
                GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        ).toBeLessThanOrEqual(position('generator1').x);
        expect(centerX('generator1')).toBe(centerX('generator2'));
        expect(position('prompt2').y).toBeGreaterThan(
            position('generator1').y + dimensions('generator1').height,
        );
        expect(position('generator2').y).toBeGreaterThan(
            position('prompt2').y + dimensions('prompt2').height,
        );
        expectNoOverlaps(nodes, positions);
    });

    it('aligns mixed serial generator types on one exact center-X spine', () => {
        const nodes = [
            typedNode('text', NodeTypeEnum.TEXT_TO_TEXT, 220, 120),
            typedNode('parallel', NodeTypeEnum.PARALLELIZATION, 260, 140),
            typedNode('routing', NodeTypeEnum.ROUTING, 180, 100),
        ];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('text-parallel', 'text', 'parallel', null, 'context_parallel'),
            edge('parallel-routing', 'parallel', 'routing', null, 'context_routing'),
        ]);
        const centerX = (id: string) =>
            positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width / 2;

        expect(centerX('text')).toBe(centerX('parallel'));
        expect(centerX('parallel')).toBe(centerX('routing'));
        expect(positions.get('parallel')!.y).toBeGreaterThan(positions.get('text')!.y + 120);
        expect(positions.get('routing')!.y).toBeGreaterThan(positions.get('parallel')!.y + 140);
        expectNoOverlaps(nodes, positions);
    });

    it('infers only compatible missing-source categories from production node types', () => {
        const cases: Array<{ type: NodeTypeEnum; category: string; lateral: boolean }> = [
            { type: NodeTypeEnum.PROMPT, category: 'prompt', lateral: false },
            { type: NodeTypeEnum.FILE_PROMPT, category: 'attachment', lateral: true },
            { type: NodeTypeEnum.GITHUB, category: 'attachment', lateral: true },
            { type: NodeTypeEnum.TEXT_TO_TEXT, category: 'context', lateral: false },
            { type: NodeTypeEnum.PARALLELIZATION, category: 'context', lateral: false },
            { type: NodeTypeEnum.ROUTING, category: 'context', lateral: false },
            { type: NodeTypeEnum.CONTEXT_MERGER, category: 'context', lateral: false },
        ];
        for (const { type, category, lateral } of cases) {
            const nodes = [typedNode('source', type), node('target')];
            const positions = calculateGraphAutoLayout(nodes, [
                edge('edge', 'source', 'target', null, `${category}_target`),
            ]);
            if (lateral) {
                expect(positions.get('source')!.y).toBe(positions.get('target')!.y);
                expect(positions.get('source')!.x + 100).toBeLessThan(positions.get('target')!.x);
            } else {
                expect(positions.get('target')!.y).toBeGreaterThan(positions.get('source')!.y + 100);
            }
            expectNoOverlaps(nodes, positions);
        }
    });

    it('keeps attachment-only chains on one row in left-to-right order', () => {
        const nodes = [node('a', 80, 120), node('b', 160, 80), node('c', 110, 140)];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('a-b', 'a', 'b', 'attachment_a', 'attachment_b'),
            edge('b-c', 'b', 'c', 'attachment_b', 'attachment_c'),
        ]);
        const centerY = (id: string) =>
            positions.get(id)!.y + nodes.find((candidate) => candidate.id === id)!.height / 2;

        expect(centerY('a')).toBe(centerY('b'));
        expect(centerY('b')).toBe(centerY('c'));
        expect(positions.get('a')!.x + 80).toBeLessThan(positions.get('b')!.x);
        expect(positions.get('b')!.x + 160).toBeLessThan(positions.get('c')!.x);
        expectNoOverlaps(nodes, positions);
    });

    it('flattens attachment fan-out and fan-in without overlap', () => {
        const nodes = [node('source'), node('branch-a'), node('branch-b'), node('target')];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('source-a', 'source', 'branch-a', 'attachment_source', 'attachment_branch-a'),
            edge('source-b', 'source', 'branch-b', 'attachment_source', 'attachment_branch-b'),
            edge('a-target', 'branch-a', 'target', 'attachment_branch-a', 'attachment_target'),
            edge('b-target', 'branch-b', 'target', 'attachment_branch-b', 'attachment_target'),
        ]);
        const yValues = new Set([...positions.values()].map(({ y }) => y));

        expect(yValues.size).toBe(1);
        expect(positions.get('branch-a')!.x).toBeGreaterThan(positions.get('source')!.x + 100);
        expect(positions.get('branch-b')!.x).toBeGreaterThan(positions.get('source')!.x + 100);
        expect(positions.get('target')!.x).toBeGreaterThan(positions.get('branch-a')!.x + 100);
        expect(positions.get('target')!.x).toBeGreaterThan(positions.get('branch-b')!.x + 100);
        expectNoOverlaps(nodes, positions);
    });

    it('uses vertical fallback for incomplete, malformed, unknown, and mixed handles', () => {
        const handlePairs: Array<[string | null | undefined, string | null | undefined]> = [
            [undefined, undefined],
            ['attachment_source', undefined],
            ['attachment_', 'attachment_target'],
            ['unknown_source', 'unknown_target'],
            ['attachment_source', 'prompt_target'],
        ];

        for (const [sourceHandle, targetHandle] of handlePairs) {
            const nodes = [node('source'), node('target')];
            const positions = calculateGraphAutoLayout(nodes, [
                edge('edge', 'source', 'target', sourceHandle, targetHandle),
            ]);
            expect(positions.get('target')!.y).toBeGreaterThan(positions.get('source')!.y + 100);
            expectNoOverlaps(nodes, positions);
        }

        const typedSource = typedNode('source', NodeTypeEnum.FILE_PROMPT);
        const unsupportedHandlePairs = [
            ['', 'attachment_target'],
            ['attachment_', 'attachment_target'],
            ['prompt_source', 'attachment_target'],
            [null, 'attachment_'],
            [null, 'unknown_target'],
        ] satisfies Array<[string | null, string]>;
        for (const [sourceHandle, targetHandle] of unsupportedHandlePairs) {
            const positions = calculateGraphAutoLayout([typedSource, node('target')], [
                edge('edge', 'source', 'target', sourceHandle, targetHandle),
            ]);
            expect(positions.get('target')!.y).toBeGreaterThan(positions.get('source')!.y + 100);
        }
    });

    it('keeps generator branches translated while aligning downstream serial segments', () => {
        const nodes = [
            typedNode('root', NodeTypeEnum.TEXT_TO_TEXT, 200, 100),
            typedNode('branch-a', NodeTypeEnum.PARALLELIZATION, 180, 120),
            typedNode('branch-b', NodeTypeEnum.ROUTING, 240, 120),
            typedNode('after-a', NodeTypeEnum.TEXT_TO_TEXT, 220, 100),
            typedNode('after-b', NodeTypeEnum.TEXT_TO_TEXT, 160, 100),
        ];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('root-a', 'root', 'branch-a', null, 'context_branch-a'),
            edge('root-b', 'root', 'branch-b', null, 'context_branch-b'),
            edge('a-after', 'branch-a', 'after-a', null, 'context_after-a'),
            edge('b-after', 'branch-b', 'after-b', null, 'context_after-b'),
        ]);
        const centerX = (id: string) =>
            positions.get(id)!.x + nodes.find((candidate) => candidate.id === id)!.width / 2;

        expect(centerX('branch-a')).toBe(centerX('after-a'));
        expect(centerX('branch-b')).toBe(centerX('after-b'));
        expect(centerX('branch-a')).not.toBe(centerX('branch-b'));
        expectNoOverlaps(nodes, positions);
    });

    it('falls back deterministically for generator cycles and conflicting prompt stages', () => {
        const nodes = [
            typedNode('generator-a', NodeTypeEnum.TEXT_TO_TEXT),
            typedNode('generator-b', NodeTypeEnum.ROUTING),
            typedNode('prompt-a', NodeTypeEnum.PROMPT),
            typedNode('prompt-b', NodeTypeEnum.PROMPT),
        ];
        const edges = [
            edge('a-b', 'generator-a', 'generator-b', null, 'context_generator-b'),
            edge('b-a', 'generator-b', 'generator-a', null, 'context_generator-a'),
            edge('prompt-a', 'prompt-a', 'generator-b', null, 'prompt_generator-b'),
            edge('prompt-b', 'prompt-b', 'generator-b', null, 'prompt_generator-b'),
        ];
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout(nodes, edges);

        expect([...second]).toEqual([...first]);
        expect([...first.values()].every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
        expectNoOverlaps(nodes, first);
    });

    it('preserves vertical participant rows and uses stable nearest-anchor ties', () => {
        const nodes = [node('anchor-a'), node('anchor-b'), node('middle', 120, 80)];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('vertical', 'anchor-a', 'anchor-b', 'prompt_anchor-a', 'prompt_anchor-b'),
            edge(
                'lateral-a',
                'anchor-a',
                'middle',
                'attachment_anchor-a',
                'attachment_middle',
            ),
            edge(
                'lateral-b',
                'middle',
                'anchor-b',
                'attachment_middle',
                'attachment_anchor-b',
            ),
        ]);
        const centerY = (id: string) =>
            positions.get(id)!.y + nodes.find((candidate) => candidate.id === id)!.height / 2;

        expect(centerY('middle')).toBe(centerY('anchor-a'));
        expect(centerY('anchor-b')).toBeGreaterThan(centerY('anchor-a'));
        expectNoOverlaps(nodes, positions);
    });

    it('keeps same-pair mixed constraints and lateral cycles deterministic', () => {
        const nodes = [node('a'), node('b'), node('c')];
        const edges = [
            edge('vertical-a-b', 'a', 'b', 'context_a', 'context_b'),
            edge('lateral-a-b', 'a', 'b', 'attachment_a', 'attachment_b'),
            edge('lateral-b-c', 'b', 'c', 'attachment_b', 'attachment_c'),
            edge('lateral-c-a', 'c', 'a', 'attachment_c', 'attachment_a'),
        ];
        const originalEdges = structuredClone(edges);
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout(nodes, edges);

        expect([...second]).toEqual([...first]);
        expect(first.get('b')!.y).toBeGreaterThan(first.get('a')!.y + 100);
        expect(edges).toEqual(originalEdges);
        expectNoOverlaps(nodes, first);
    });

    it('lays out a branched DAG top-to-bottom and ignores order and layout-only edge noise', () => {
        const nodes = [node('root', 180, 80), node('left', 120, 140), node('right', 240, 90)];
        const edges = [
            edge('root-left', 'root', 'left'),
            edge('root-right', 'root', 'right'),
            edge('duplicate', 'root', 'right'),
            edge('self', 'left', 'left'),
            edge('dangling', 'missing', 'right'),
        ];
        const originalEdges = structuredClone(edges);

        const positions = calculateGraphAutoLayout(nodes, edges);
        const shuffled = calculateGraphAutoLayout(
            [nodes[2]!, nodes[0]!, nodes[1]!],
            [edges[4]!, edges[2]!, edges[1]!, edges[3]!, edges[0]!],
        );

        expect([...shuffled]).toEqual([...positions]);
        expect(edges).toEqual(originalEdges);
        expect(positions.get('left')!.y).toBeGreaterThan(
            positions.get('root')!.y + nodes[0]!.height,
        );
        expect(positions.get('right')!.y).toBeGreaterThan(
            positions.get('root')!.y + nodes[0]!.height,
        );
        expect(positions.get('left')!.x).not.toBe(positions.get('right')!.x);
        expectNoOverlaps(nodes, positions);
    });

    it('places multiple roots before their shared descendant', () => {
        const nodes = [node('root-a'), node('root-b'), node('shared', 160, 120)];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('a-shared', 'root-a', 'shared'),
            edge('b-shared', 'root-b', 'shared'),
        ]);

        expect(positions.get('root-a')!.y).toBe(positions.get('root-b')!.y);
        expect(positions.get('shared')!.y).toBeGreaterThan(positions.get('root-a')!.y + 100);
        expectNoOverlaps(nodes, positions);
    });

    it('produces finite deterministic non-overlapping positions for directed cycles', () => {
        const nodes = [node('a', 110, 80), node('b', 160, 120), node('c', 90, 150)];
        const edges = [edge('a-b', 'a', 'b'), edge('b-c', 'b', 'c'), edge('c-a', 'c', 'a')];
        const originalEdges = structuredClone(edges);
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout(nodes, edges);

        expect([...second]).toEqual([...first]);
        expect(edges).toEqual(originalEdges);
        for (const position of first.values()) {
            expect(Number.isFinite(position.x)).toBe(true);
            expect(Number.isFinite(position.y)).toBe(true);
        }
        expectNoOverlaps(nodes, first);
    });

    it('packs disconnected components and isolated nodes into deterministic shelves', () => {
        const nodes = Array.from({ length: 9 }, (_, index) =>
            node(`isolated-${index}`, 100, 100, { x: -30, y: 15 }),
        );
        const positions = calculateGraphAutoLayout(nodes, []);
        const xValues = [...new Set([...positions.values()].map(({ x }) => x))];
        const yValues = [...new Set([...positions.values()].map(({ y }) => y))];

        expect(xValues.length).toBeGreaterThan(1);
        expect(yValues.length).toBeGreaterThan(1);
        expect(Math.min(...xValues)).toBe(-30);
        expect(Math.min(...yValues)).toBe(15);
        expect(Math.max(...xValues) - Math.min(...xValues)).toBeLessThan(
            nodes.length * (100 + GRAPH_AUTO_LAYOUT_COMPONENT_SEPARATION),
        );
        expectNoOverlaps(nodes, positions);
    });

    it('treats outer groups atomically and maps child edges to the group', () => {
        const group = node('group', 420, 300, { x: 250, y: 175 });
        const child = {
            ...node('child', 100, 80, { x: 40, y: 50 }, 'group'),
            type: NodeTypeEnum.FILE_PROMPT,
        };
        const external = node('external', 180, 100, { x: 900, y: 900 });
        const positions = calculateGraphAutoLayout(
            [child, external, group],
            [edge('child-external', 'child', 'external'), edge('internal', 'group', 'child')],
        );

        expect([...positions.keys()].sort()).toEqual(['external', 'group']);
        expect(positions.has('child')).toBe(false);
        expect(positions.get('group')).toEqual({ x: 250, y: 175 });
        expect(positions.get('external')!.y).toBeGreaterThan(175 + group.height);
        expectNoOverlaps([group, external], positions);

        const lateralPositions = calculateGraphAutoLayout(
            [child, external, group],
            [
                edge(
                    'external-child',
                    'child',
                    'external',
                    null,
                    'attachment_external',
                ),
            ],
        );
        expect([...lateralPositions.keys()].sort()).toEqual(['external', 'group']);
        expect(lateralPositions.has('child')).toBe(false);
        expect(
            lateralPositions.get('external')!.y + external.height / 2,
        ).toBe(lateralPositions.get('group')!.y + group.height / 2);
        expect(lateralPositions.get('group')!.x + group.width).toBeLessThan(
            lateralPositions.get('external')!.x,
        );
        expectNoOverlaps([group, external], lateralPositions);
    });

    it('accounts for variable dimensions and preserves the finite canvas anchor', () => {
        const nodes = [
            node('wide', 500, 70, { x: 400, y: 300 }),
            node('tall', 90, 500, { x: 600, y: 700 }),
            node('small', 40, 30, { x: 800, y: 900 }),
        ];
        const positions = calculateGraphAutoLayout(nodes, [
            edge('wide-tall', 'wide', 'tall'),
            edge('wide-small', 'wide', 'small'),
        ]);

        expect(Math.min(...[...positions.values()].map(({ x }) => x))).toBe(400);
        expect(Math.min(...[...positions.values()].map(({ y }) => y))).toBe(300);
        expectNoOverlaps(nodes, positions);
    });

    it('handles a sizable deterministic graph with finite branch geometry', () => {
        const nodes = Array.from({ length: 120 }, (_, index) =>
            typedNode(`node-${index.toString().padStart(3, '0')}`, NodeTypeEnum.TEXT_TO_TEXT, 120, 80),
        );
        const edges = nodes.slice(1).map((target, index) =>
            edge(
                `edge-${index}`,
                nodes[Math.floor(index / 2)]!.id,
                target.id,
                null,
                `context_${target.id}`,
            ),
        );
        const first = calculateGraphAutoLayout(nodes, edges);
        const second = calculateGraphAutoLayout([...nodes].reverse(), [...edges].reverse());

        expect(first.size).toBe(nodes.length);
        expect([...second]).toEqual([...first]);
        expect([...first.values()].every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
        expect(new Set([...first.values()].map(({ x }) => x)).size).toBeGreaterThan(2);
    });
});
