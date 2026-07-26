import type { GeometryPoint, GeometryRect } from '@/utils/graphGeometry';

const DEFAULT_BUCKET_SIZE = 512;

interface SpatialEntry<T> {
    order: number;
    value: T;
}

interface SpatialBucket<T> {
    cellX: number;
    cellY: number;
    entries: SpatialEntry<T>[];
}

export class SpatialBucketIndex<T> {
    private readonly buckets = new Map<string, SpatialBucket<T>>();
    private readonly bucketSize: number;
    private entryCount = 0;
    private minCellX = Infinity;
    private maxCellX = -Infinity;
    private minCellY = Infinity;
    private maxCellY = -Infinity;

    constructor(bucketSize = DEFAULT_BUCKET_SIZE) {
        if (!Number.isFinite(bucketSize) || bucketSize <= 0) {
            throw new Error('Spatial bucket size must be a positive finite number.');
        }

        this.bucketSize = bucketSize;
    }

    insert(rect: GeometryRect, value: T): void {
        const entry = { order: this.entryCount, value };
        this.entryCount++;

        const range = this.getCellRange(rect);
        this.minCellX = Math.min(this.minCellX, range.minX);
        this.maxCellX = Math.max(this.maxCellX, range.maxX);
        this.minCellY = Math.min(this.minCellY, range.minY);
        this.maxCellY = Math.max(this.maxCellY, range.maxY);

        for (let cellY = range.minY; cellY <= range.maxY; cellY++) {
            for (let cellX = range.minX; cellX <= range.maxX; cellX++) {
                const key = this.getCellKey(cellX, cellY);
                const bucket = this.buckets.get(key);

                if (bucket) {
                    bucket.entries.push(entry);
                } else {
                    this.buckets.set(key, { cellX, cellY, entries: [entry] });
                }
            }
        }
    }

    query(rect: GeometryRect): T[] {
        if (this.entryCount === 0) {
            return [];
        }

        const range = this.getCellRange(rect);
        const minX = Math.max(range.minX, this.minCellX);
        const maxX = Math.min(range.maxX, this.maxCellX);
        const minY = Math.max(range.minY, this.minCellY);
        const maxY = Math.min(range.maxY, this.maxCellY);
        if (minX > maxX || minY > maxY) {
            return [];
        }

        const entries = new Set<SpatialEntry<T>>();
        const rangeWidth = maxX - minX + 1;
        const rangeHeight = maxY - minY + 1;

        if (this.shouldScanCoordinateRange(rangeWidth, rangeHeight)) {
            for (let cellY = minY; cellY <= maxY; cellY++) {
                for (let cellX = minX; cellX <= maxX; cellX++) {
                    for (const entry of
                        this.buckets.get(this.getCellKey(cellX, cellY))?.entries ?? []) {
                        entries.add(entry);
                    }
                }
            }
        } else {
            for (const bucket of this.buckets.values()) {
                if (
                    bucket.cellX >= minX &&
                    bucket.cellX <= maxX &&
                    bucket.cellY >= minY &&
                    bucket.cellY <= maxY
                ) {
                    bucket.entries.forEach((entry) => entries.add(entry));
                }
            }
        }

        return [...entries]
            .sort((left, right) => left.order - right.order)
            .map((entry) => entry.value);
    }

    findNearest(point: GeometryPoint, getPoint: (value: T) => GeometryPoint): T | null {
        if (this.entryCount === 0) {
            return null;
        }

        const originCellX = this.getCellCoordinate(point.x);
        const originCellY = this.getCellCoordinate(point.y);
        const initialRadius = Math.max(
            this.distanceToRange(originCellX, this.minCellX, this.maxCellX),
            this.distanceToRange(originCellY, this.minCellY, this.maxCellY),
        );
        const maximumRadius = Math.max(
            Math.abs(originCellX - this.minCellX),
            Math.abs(originCellX - this.maxCellX),
            Math.abs(originCellY - this.minCellY),
            Math.abs(originCellY - this.maxCellY),
        );
        const visitedEntries = new Set<SpatialEntry<T>>();
        let nearestEntry: SpatialEntry<T> | null = null;
        let nearestSquaredDistance = Infinity;

        const visitEntry = (entry: SpatialEntry<T>) => {
            if (visitedEntries.has(entry)) {
                return;
            }

            visitedEntries.add(entry);
            const candidatePoint = getPoint(entry.value);
            const distanceX = point.x - candidatePoint.x;
            const distanceY = point.y - candidatePoint.y;
            const squaredDistance = distanceX * distanceX + distanceY * distanceY;

            if (
                squaredDistance < nearestSquaredDistance ||
                (squaredDistance === nearestSquaredDistance &&
                    nearestEntry !== null &&
                    entry.order < nearestEntry.order)
            ) {
                nearestEntry = entry;
                nearestSquaredDistance = squaredDistance;
            }
        };

        const occupiedWidth = this.maxCellX - this.minCellX + 1;
        const occupiedHeight = this.maxCellY - this.minCellY + 1;
        if (!this.shouldScanCoordinateRange(occupiedWidth, occupiedHeight)) {
            const bucketsByDistance = [...this.buckets.values()]
                .map((bucket) => ({
                    bucket,
                    squaredDistance: this.getSquaredDistanceToCell(
                        point,
                        bucket.cellX,
                        bucket.cellY,
                    ),
                }))
                .sort((left, right) => left.squaredDistance - right.squaredDistance);

            for (const candidate of bucketsByDistance) {
                if (candidate.squaredDistance > nearestSquaredDistance) {
                    break;
                }

                candidate.bucket.entries.forEach(visitEntry);
            }

            return nearestEntry?.value ?? null;
        }

        for (let radius = initialRadius; radius <= maximumRadius; radius++) {
            this.visitRing(originCellX, originCellY, radius, visitEntry);

            if (
                radius === maximumRadius ||
                (nearestEntry !== null &&
                    this.getSquaredDistanceToRingExterior(point, originCellX, originCellY, radius) >
                        nearestSquaredDistance)
            ) {
                break;
            }
        }

        return nearestEntry?.value ?? null;
    }

    private getCellCoordinate(coordinate: number): number {
        return Math.floor(coordinate / this.bucketSize);
    }

    private getCellKey(cellX: number, cellY: number): string {
        return `${cellX}:${cellY}`;
    }

    private getCellRange(rect: GeometryRect) {
        const left = Math.min(rect.x, rect.x + rect.width);
        const right = Math.max(rect.x, rect.x + rect.width);
        const top = Math.min(rect.y, rect.y + rect.height);
        const bottom = Math.max(rect.y, rect.y + rect.height);

        return {
            minX: this.getCellCoordinate(left),
            maxX: this.getCellCoordinate(right),
            minY: this.getCellCoordinate(top),
            maxY: this.getCellCoordinate(bottom),
        };
    }

    private distanceToRange(value: number, minimum: number, maximum: number): number {
        if (value < minimum) return minimum - value;
        if (value > maximum) return value - maximum;
        return 0;
    }

    private shouldScanCoordinateRange(width: number, height: number): boolean {
        return width <= (this.buckets.size * 4) / height;
    }

    private visitRing(
        originX: number,
        originY: number,
        radius: number,
        visit: (entry: SpatialEntry<T>) => void,
    ): void {
        const minX = Math.max(this.minCellX, originX - radius);
        const maxX = Math.min(this.maxCellX, originX + radius);

        if (radius === 0) {
            this.visitCell(originX, originY, visit);
            return;
        }

        const top = originY - radius;
        const bottom = originY + radius;
        for (let cellX = minX; cellX <= maxX; cellX++) {
            if (top >= this.minCellY && top <= this.maxCellY) {
                this.visitCell(cellX, top, visit);
            }
            if (bottom !== top && bottom >= this.minCellY && bottom <= this.maxCellY) {
                this.visitCell(cellX, bottom, visit);
            }
        }

        const left = originX - radius;
        const right = originX + radius;
        const sideMinY = Math.max(this.minCellY, top + 1);
        const sideMaxY = Math.min(this.maxCellY, bottom - 1);
        for (let cellY = sideMinY; cellY <= sideMaxY; cellY++) {
            if (left >= this.minCellX && left <= this.maxCellX) {
                this.visitCell(left, cellY, visit);
            }
            if (right !== left && right >= this.minCellX && right <= this.maxCellX) {
                this.visitCell(right, cellY, visit);
            }
        }
    }

    private visitCell(
        cellX: number,
        cellY: number,
        visit: (entry: SpatialEntry<T>) => void,
    ): void {
        for (const entry of this.buckets.get(this.getCellKey(cellX, cellY))?.entries ?? []) {
            visit(entry);
        }
    }

    private getSquaredDistanceToCell(
        point: GeometryPoint,
        cellX: number,
        cellY: number,
    ): number {
        const left = cellX * this.bucketSize;
        const right = (cellX + 1) * this.bucketSize;
        const top = cellY * this.bucketSize;
        const bottom = (cellY + 1) * this.bucketSize;
        const distanceX = point.x < left ? left - point.x : Math.max(0, point.x - right);
        const distanceY = point.y < top ? top - point.y : Math.max(0, point.y - bottom);

        return distanceX * distanceX + distanceY * distanceY;
    }

    private getSquaredDistanceToRingExterior(
        point: GeometryPoint,
        originCellX: number,
        originCellY: number,
        radius: number,
    ): number {
        const left = (originCellX - radius) * this.bucketSize;
        const right = (originCellX + radius + 1) * this.bucketSize;
        const top = (originCellY - radius) * this.bucketSize;
        const bottom = (originCellY + radius + 1) * this.bucketSize;
        const distance = Math.min(
            point.x - left,
            right - point.x,
            point.y - top,
            bottom - point.y,
        );

        return distance * distance;
    }
}
