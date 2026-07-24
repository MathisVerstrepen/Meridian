import { describe, expect, it, vi } from 'vitest';
import { SpatialBucketIndex } from '@/utils/spatialIndex';

interface IndexedPoint {
    id: string;
    x: number;
    y: number;
}

const insertPoint = (index: SpatialBucketIndex<IndexedPoint>, point: IndexedPoint) => {
    index.insert({ x: point.x, y: point.y, width: 0, height: 0 }, point);
};

describe('SpatialBucketIndex query', () => {
    it('returns broad-phase cell candidates in insertion order without duplicates', () => {
        const index = new SpatialBucketIndex<string>(10);
        index.insert({ x: 5, y: 5, width: 20, height: 20 }, 'spanning');
        index.insert({ x: 15, y: 15, width: 1, height: 1 }, 'inside');
        index.insert({ x: 50, y: 50, width: 1, height: 1 }, 'far');

        expect(index.query({ x: 9, y: 9, width: 12, height: 12 })).toEqual([
            'spanning',
            'inside',
        ]);
    });

    it('covers boundaries, zero-size rectangles, and negative coordinates', () => {
        const index = new SpatialBucketIndex<string>(10);
        index.insert({ x: -20, y: -10, width: 10, height: 10 }, 'negative');
        index.insert({ x: 10, y: 10, width: 0, height: 0 }, 'point');

        expect(index.query({ x: -10, y: 0, width: 0, height: 0 })).toEqual(['negative']);
        expect(index.query({ x: 10, y: 10, width: 0, height: 0 })).toEqual(['point']);
        expect(index.query({ x: -100, y: -100, width: 1, height: 1 })).toEqual([]);
    });

    it('returns no values from an empty index', () => {
        expect(new SpatialBucketIndex<string>(10).query({ x: 0, y: 0, width: 10, height: 10 }))
            .toEqual([]);
    });

    it('bounds huge sparse queries by occupied buckets instead of coordinate span', () => {
        const index = new SpatialBucketIndex<string>(10);
        index.insert({ x: -1_000_000_000_000, y: 0, width: 1, height: 1 }, 'left');
        index.insert({ x: 1_000_000_000_000, y: 0, width: 1, height: 1 }, 'right');

        expect(
            index.query({
                x: -2_000_000_000_000,
                y: -100,
                width: 4_000_000_000_000,
                height: 200,
            }),
        ).toEqual(['left', 'right']);
    });
});

describe('SpatialBucketIndex findNearest', () => {
    it('returns null from an empty index', () => {
        expect(new SpatialBucketIndex<IndexedPoint>(10).findNearest({ x: 0, y: 0 }, (item) => item))
            .toBeNull();
    });

    it('finds the exact nearest point across cells and with negative coordinates', () => {
        const index = new SpatialBucketIndex<IndexedPoint>(10);
        const points = [
            { id: 'negative', x: -15, y: -15 },
            { id: 'diagonal', x: 11, y: 11 },
            { id: 'same-cell', x: 9, y: 0 },
        ];
        points.forEach((point) => insertPoint(index, point));

        expect(index.findNearest({ x: -13, y: -12 }, (item) => item)?.id).toBe('negative');
        expect(index.findNearest({ x: 10, y: 10 }, (item) => item)?.id).toBe('diagonal');
    });

    it('uses insertion order to resolve equal-distance ties', () => {
        const index = new SpatialBucketIndex<IndexedPoint>(10);
        insertPoint(index, { id: 'first', x: -10, y: 0 });
        insertPoint(index, { id: 'second', x: 10, y: 0 });

        expect(index.findNearest({ x: 0, y: 0 }, (item) => item)?.id).toBe('first');
    });

    it('prunes far buckets after proving the nearest distance', () => {
        const index = new SpatialBucketIndex<IndexedPoint>(10);
        insertPoint(index, { id: 'near', x: 1, y: 1 });
        for (let coordinate = 100; coordinate <= 1000; coordinate += 100) {
            insertPoint(index, { id: `far-${coordinate}`, x: coordinate, y: coordinate });
        }
        const getPoint = vi.fn((item: IndexedPoint) => item);

        expect(index.findNearest({ x: 0, y: 0 }, getPoint)?.id).toBe('near');
        expect(getPoint).toHaveBeenCalledTimes(1);
    });

    it('jumps to occupied bounds when the query starts far from every cell', () => {
        const index = new SpatialBucketIndex<IndexedPoint>(10);
        insertPoint(index, { id: 'first', x: 1000, y: 1000 });
        insertPoint(index, { id: 'second', x: 1020, y: 1000 });

        expect(index.findNearest({ x: -1000, y: -1000 }, (item) => item)?.id).toBe('first');
    });

    it('searches sparse occupied buckets exactly when the query is inside distant bounds', () => {
        const index = new SpatialBucketIndex<IndexedPoint>(10);
        insertPoint(index, { id: 'far-left', x: -1_000_000_000_000, y: 0 });
        insertPoint(index, { id: 'near', x: 1, y: 1 });
        insertPoint(index, { id: 'far-right', x: 1_000_000_000_000, y: 0 });
        const getPoint = vi.fn((item: IndexedPoint) => item);

        expect(index.findNearest({ x: 0, y: 0 }, getPoint)?.id).toBe('near');
        expect(getPoint).toHaveBeenCalledTimes(1);
    });
});
