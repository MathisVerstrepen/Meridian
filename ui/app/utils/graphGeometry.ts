import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { QuickWorkflowDirection } from '@/utils/quickWorkflow';

export interface GeometryPoint {
    x: number;
    y: number;
}

export interface GeometryRect extends GeometryPoint {
    width: number;
    height: number;
}

export type OverlapResolutionDirection = 'right' | 'below';

export interface QuickWorkflowPlacementInput {
    category: NodeCategoryEnum;
    direction: QuickWorkflowDirection;
    anchorWidth: number;
    anchorHeight: number;
    mainWidth: number;
    mainHeight: number;
    gap: number;
}

export interface GeneratorPlacementNode {
    id: string;
    type?: string;
    position: GeometryPoint;
    width: number;
    height: number;
}

export interface GeneratorPlacementEdge {
    source: string;
    target: string;
}

export interface GeneratorChildPlacementInput {
    parent: GeneratorPlacementNode;
    nodes: readonly GeneratorPlacementNode[];
    edges: readonly GeneratorPlacementEdge[];
    gap: number;
}

export interface WheelGeometryConfig {
    radius: number;
    innerRadius: number;
    centerX: number;
    centerY: number;
}

export interface WheelSectorGeometry {
    path: string;
    iconX: number;
    iconY: number;
}

const GENERATOR_NODE_TYPES = new Set<string>([
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
]);

export const calculateGeneratorChildPosition = (
    input: GeneratorChildPlacementInput,
): GeometryPoint => {
    const belowParent = {
        x: input.parent.position.x,
        y: input.parent.position.y + input.parent.height + input.gap,
    };
    if (!input.parent.type || !GENERATOR_NODE_TYPES.has(input.parent.type)) return belowParent;

    const directChildIds = new Set(
        input.edges
            .filter((edge) => edge.source === input.parent.id)
            .map((edge) => edge.target),
    );
    const directGeneratorChildren = input.nodes.filter(
        (node) =>
            directChildIds.has(node.id) &&
            !!node.type &&
            GENERATOR_NODE_TYPES.has(node.type),
    );
    const rightmostChild = directGeneratorChildren.reduce<GeneratorPlacementNode | undefined>(
        (rightmost, child) =>
            !rightmost || child.position.x + child.width > rightmost.position.x + rightmost.width
                ? child
                : rightmost,
        undefined,
    );

    return rightmostChild
        ? {
              x: rightmostChild.position.x + rightmostChild.width + input.gap,
              y: rightmostChild.position.y,
          }
        : belowParent;
};

export const calculateQuickWorkflowPositionOffset = (
    input: QuickWorkflowPlacementInput,
): GeometryPoint =>
    input.category === NodeCategoryEnum.ATTACHMENT
        ? {
              x:
                  input.direction === 'target'
                      ? -(input.mainWidth + input.gap)
                      : input.anchorWidth + input.gap,
              y: 0,
          }
        : {
              x: 0,
              y:
                  input.direction === 'target'
                      ? -(input.mainHeight + input.gap)
                      : input.anchorHeight + input.gap,
          };

export const calculateOverlapTranslation = (
    movableRects: readonly GeometryRect[],
    intersectingRect: GeometryRect,
    direction: OverlapResolutionDirection,
    gap: number,
): GeometryPoint => {
    const groupBounds = movableRects.reduce((bounds, memberRect) => {
        const right = Math.max(bounds.x + bounds.width, memberRect.x + memberRect.width);
        const bottom = Math.max(bounds.y + bounds.height, memberRect.y + memberRect.height);
        const x = Math.min(bounds.x, memberRect.x);
        const y = Math.min(bounds.y, memberRect.y);
        return { x, y, width: right - x, height: bottom - y };
    });

    return direction === 'below'
        ? {
              x: 0,
              y: intersectingRect.y + intersectingRect.height + gap - groupBounds.y,
          }
        : {
              x: intersectingRect.x + intersectingRect.width + gap - groupBounds.x,
              y: 0,
          };
};

export const calculateWheelSectorGeometry = (
    count: number,
    config: WheelGeometryConfig,
): WheelSectorGeometry[] => {
    if (count === 0) return [];
    const anglePerSlice = 180 / count;
    const toRad = (degrees: number) => (degrees * Math.PI) / 180;

    return Array.from({ length: count }, (_value, index) => {
        const startDeg = index * anglePerSlice;
        const endDeg = startDeg + anglePerSlice;
        const p1Outer = {
            x: config.centerX + config.radius * Math.cos(toRad(startDeg)),
            y: config.centerY + config.radius * Math.sin(toRad(startDeg)),
        };
        const p2Outer = {
            x: config.centerX + config.radius * Math.cos(toRad(endDeg)),
            y: config.centerY + config.radius * Math.sin(toRad(endDeg)),
        };
        const p1Inner = {
            x: config.centerX + config.innerRadius * Math.cos(toRad(endDeg)),
            y: config.centerY + config.innerRadius * Math.sin(toRad(endDeg)),
        };
        const p2Inner = {
            x: config.centerX + config.innerRadius * Math.cos(toRad(startDeg)),
            y: config.centerY + config.innerRadius * Math.sin(toRad(startDeg)),
        };
        const midDeg = startDeg + anglePerSlice / 2;
        const iconRadius = (config.innerRadius + config.radius) / 2;

        return {
            path: [
                `M ${p2Inner.x} ${p2Inner.y}`,
                `L ${p1Outer.x} ${p1Outer.y}`,
                `A ${config.radius} ${config.radius} 0 0 1 ${p2Outer.x} ${p2Outer.y}`,
                `L ${p1Inner.x} ${p1Inner.y}`,
                `A ${config.innerRadius} ${config.innerRadius} 0 0 0 ${p2Inner.x} ${p2Inner.y}`,
                'Z',
            ].join(' '),
            iconX: config.centerX + iconRadius * Math.cos(toRad(midDeg)),
            iconY: config.centerY + iconRadius * Math.sin(toRad(midDeg)),
        };
    });
};
