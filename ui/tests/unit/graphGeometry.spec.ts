import { describe, expect, it } from 'vitest';
import { NodeCategoryEnum } from '@/types/enums';
import {
    calculateOverlapTranslation,
    calculateQuickWorkflowPositionOffset,
    calculateWheelSectorGeometry,
} from '@/utils/graphGeometry';

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
