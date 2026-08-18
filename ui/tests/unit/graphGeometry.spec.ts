import { describe, expect, it } from 'vitest';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import {
    calculateGeneratorChildPosition,
    calculateOverlapTranslation,
    calculateQuickWorkflowPositionOffset,
    calculateWheelSectorGeometry,
} from '@/utils/graphGeometry';

describe('calculateGeneratorChildPosition', () => {
    const parent = {
        id: 'parent',
        type: NodeTypeEnum.TEXT_TO_TEXT,
        position: { x: 100, y: 200 },
        width: 320,
        height: 180,
    };

    it('keeps below-parent placement when no direct generator child exists', () => {
        expect(
            calculateGeneratorChildPosition({ parent, nodes: [parent], edges: [], gap: 150 }),
        ).toEqual({ x: 100, y: 530 });
    });

    it('uses right edge of rightmost direct generator child and ignores other topology', () => {
        const nodes = [
            parent,
            {
                id: 'wide-child',
                type: NodeTypeEnum.TEXT_TO_TEXT,
                position: { x: 450, y: 600 },
                width: 400,
                height: 100,
            },
            {
                id: 'higher-x-child',
                type: NodeTypeEnum.ROUTING,
                position: { x: 700, y: 650 },
                width: 100,
                height: 100,
            },
            {
                id: 'descendant',
                type: NodeTypeEnum.PARALLELIZATION,
                position: { x: 1200, y: 1000 },
                width: 300,
                height: 100,
            },
            {
                id: 'non-generator',
                type: NodeTypeEnum.PROMPT,
                position: { x: 1600, y: 1200 },
                width: 200,
                height: 100,
            },
            {
                id: 'incoming-generator',
                type: NodeTypeEnum.ROUTING,
                position: { x: 2000, y: 1400 },
                width: 200,
                height: 100,
            },
        ];
        const edges = [
            { source: parent.id, target: 'wide-child' },
            { source: parent.id, target: 'higher-x-child' },
            { source: 'wide-child', target: 'descendant' },
            { source: parent.id, target: 'non-generator' },
            { source: 'incoming-generator', target: parent.id },
        ];

        expect(calculateGeneratorChildPosition({ parent, nodes, edges, gap: 150 })).toEqual({
            x: 1000,
            y: 600,
        });
    });

    it.each([
        NodeTypeEnum.TEXT_TO_TEXT,
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
    ])('accepts direct %s children', (type) => {
        const child = {
            id: 'child',
            type,
            position: { x: 500, y: 700 },
            width: 250,
            height: 100,
        };

        expect(
            calculateGeneratorChildPosition({
                parent,
                nodes: [parent, child],
                edges: [{ source: parent.id, target: child.id }],
                gap: 150,
            }),
        ).toEqual({ x: 900, y: 700 });
    });

    it('keeps below-parent placement for a non-generator parent', () => {
        const promptParent = { ...parent, type: NodeTypeEnum.PROMPT };
        const child = {
            id: 'child',
            type: NodeTypeEnum.TEXT_TO_TEXT,
            position: { x: 500, y: 700 },
            width: 250,
            height: 100,
        };

        expect(
            calculateGeneratorChildPosition({
                parent: promptParent,
                nodes: [promptParent, child],
                edges: [{ source: promptParent.id, target: child.id }],
                gap: 150,
            }),
        ).toEqual({ x: 100, y: 530 });
    });
});

describe('calculateQuickWorkflowPositionOffset', () => {
    it.each([
        {
            name: 'attachment target',
            category: NodeCategoryEnum.ATTACHMENT,
            direction: 'target' as const,
            expected: { x: -390, y: 0 },
        },
        {
            name: 'attachment source',
            category: NodeCategoryEnum.ATTACHMENT,
            direction: 'source' as const,
            expected: { x: 470, y: 0 },
        },
        {
            name: 'context target',
            category: NodeCategoryEnum.CONTEXT,
            direction: 'target' as const,
            expected: { x: 0, y: -310 },
        },
        {
            name: 'prompt source',
            category: NodeCategoryEnum.PROMPT,
            direction: 'source' as const,
            expected: { x: 0, y: 330 },
        },
    ])('places a $name on the existing axis and gap', ({ category, direction, expected }) => {
        expect(
            calculateQuickWorkflowPositionOffset({
                category,
                direction,
                anchorWidth: 320,
                anchorHeight: 180,
                mainWidth: 240,
                mainHeight: 160,
                gap: 150,
            }),
        ).toEqual(expected);
    });
});

describe('calculateOverlapTranslation', () => {
    const movableRects = [
        { x: 100, y: 200, width: 50, height: 40 },
        { x: 50, y: 250, width: 20, height: 20 },
    ];
    const blocker = { x: 300, y: 400, width: 60, height: 80 };

    it('calculates one right translation from the group minimum and blocker far edge', () => {
        const delta = calculateOverlapTranslation(movableRects, blocker, 'right', 150);

        expect(delta).toEqual({ x: 460, y: 0 });
        expect(movableRects.map((rect) => ({ x: rect.x + delta.x, y: rect.y + delta.y })))
            .toEqual([
                { x: 560, y: 200 },
                { x: 510, y: 250 },
            ]);
    });

    it('calculates one below translation from the group minimum and blocker far edge', () => {
        const delta = calculateOverlapTranslation(movableRects, blocker, 'below', 150);

        expect(delta).toEqual({ x: 0, y: 430 });
        expect(movableRects.map((rect) => ({ x: rect.x + delta.x, y: rect.y + delta.y })))
            .toEqual([
                { x: 100, y: 630 },
                { x: 50, y: 680 },
            ]);
    });
});

describe('calculateWheelSectorGeometry', () => {
    const config = { centerX: 130, centerY: 0, radius: 120, innerRadius: 40 };

    it('returns no sectors for zero options', () => {
        expect(calculateWheelSectorGeometry(0, config)).toEqual([]);
    });

    it('retains the three-sector SVG arcs and symmetric icon geometry', () => {
        const sectors = calculateWheelSectorGeometry(3, config);

        expect(sectors).toHaveLength(3);
        sectors.forEach((sector) => {
            expect(sector.path).toContain('A 120 120 0 0 1');
            expect(sector.path).toContain('A 40 40 0 0 0');
            expect(Math.hypot(sector.iconX - config.centerX, sector.iconY - config.centerY))
                .toBeCloseTo(80);
        });
        expect(sectors[1].iconX).toBeCloseTo(130);
        expect(sectors[0].iconX - config.centerX).toBeCloseTo(
            config.centerX - sectors[2].iconX,
        );
        expect(sectors[0].iconY).toBeCloseTo(sectors[2].iconY);
    });
});
