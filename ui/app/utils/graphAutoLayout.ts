import type { XYPosition } from '@vue-flow/core';

import {
    layoutGraphComponent,
    type ComponentLayout,
    type LayoutComponentInput,
    type NormalizedEdge,
} from '@/utils/graphAutoLayoutComponent';
import { classifyLayoutEdge } from '@/utils/graphAutoLayoutConstraints';

export const GRAPH_AUTO_LAYOUT_NODE_SEPARATION = 160;
export const GRAPH_AUTO_LAYOUT_RANK_SEPARATION = 100;
export const GRAPH_AUTO_LAYOUT_EDGE_SEPARATION = 40;
export const GRAPH_AUTO_LAYOUT_COMPONENT_SEPARATION = 240;

export interface GraphAutoLayoutNode {
    id: string;
    position: XYPosition;
    width: number;
    height: number;
    type?: string;
    parentNode?: string;
}

export interface GraphAutoLayoutEdge {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
}

const compareIds = (left: string, right: string) => left.localeCompare(right);

const getOuterUnitId = (
    nodeId: string,
    nodesById: ReadonlyMap<string, GraphAutoLayoutNode>,
): string => {
    let currentId = nodeId;
    const visited = new Set<string>();

    while (true) {
        if (visited.has(currentId)) return nodeId;
        visited.add(currentId);
        const parentId = nodesById.get(currentId)?.parentNode;
        if (!parentId || !nodesById.has(parentId)) return currentId;
        currentId = parentId;
    }
};

const normalizeGraph = (nodes: readonly GraphAutoLayoutNode[], edges: readonly GraphAutoLayoutEdge[]) => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const outerUnitByNode = new Map<string, string>();
    for (const node of nodes) outerUnitByNode.set(node.id, getOuterUnitId(node.id, nodesById));

    const units = [...new Set(outerUnitByNode.values())]
        .map((id) => nodesById.get(id))
        .filter((node): node is GraphAutoLayoutNode => node !== undefined)
        .sort((left, right) => compareIds(left.id, right.id));
    const seenConstraints = new Set<string>();
    const normalizedEdges: NormalizedEdge[] = [];
    const sortedEdges = [...edges].sort(
        (left, right) =>
            compareIds(left.source, right.source) ||
            compareIds(left.target, right.target) ||
            compareIds(left.id, right.id),
    );
    for (const edge of sortedEdges) {
        const source = outerUnitByNode.get(edge.source);
        const target = outerUnitByNode.get(edge.target);
        if (!source || !target || source === target) continue;
        const category = classifyLayoutEdge(edge, nodesById.get(edge.source)?.type);
        const constraint = `${category}\u0000${source}\u0000${target}`;
        if (seenConstraints.has(constraint)) continue;
        seenConstraints.add(constraint);
        normalizedEdges.push({ source, target, category });
    }
    normalizedEdges.sort(
        (left, right) =>
            compareIds(left.category, right.category) ||
            compareIds(left.source, right.source) ||
            compareIds(left.target, right.target),
    );

    return { units, edges: normalizedEdges };
};

const splitComponents = (
    units: readonly GraphAutoLayoutNode[],
    edges: readonly NormalizedEdge[],
): LayoutComponentInput[] => {
    const adjacency = new Map(units.map((unit) => [unit.id, new Set<string>()]));
    for (const edge of edges) {
        adjacency.get(edge.source)?.add(edge.target);
        adjacency.get(edge.target)?.add(edge.source);
    }

    const unitsById = new Map(units.map((unit) => [unit.id, unit]));
    const componentByUnit = new Map<string, number>();
    const componentUnits: GraphAutoLayoutNode[][] = [];
    for (const unit of units) {
        if (componentByUnit.has(unit.id)) continue;
        const componentIndex = componentUnits.length;
        const pending = [unit.id];
        let pendingIndex = 0;
        const members: GraphAutoLayoutNode[] = [];
        componentByUnit.set(unit.id, componentIndex);
        while (pendingIndex < pending.length) {
            const id = pending[pendingIndex];
            pendingIndex += 1;
            if (!id) continue;
            const member = unitsById.get(id);
            if (member) members.push(member);
            for (const neighbor of [...(adjacency.get(id) ?? [])].sort(compareIds)) {
                if (componentByUnit.has(neighbor)) continue;
                componentByUnit.set(neighbor, componentIndex);
                pending.push(neighbor);
            }
        }
        members.sort((left, right) => compareIds(left.id, right.id));
        componentUnits.push(members);
    }

    const componentEdges = componentUnits.map((): NormalizedEdge[] => []);
    for (const edge of edges) {
        const componentIndex = componentByUnit.get(edge.source);
        if (componentIndex !== undefined) componentEdges[componentIndex]?.push(edge);
    }
    return componentUnits.map((members, index) => ({
        units: members,
        edges: componentEdges[index] ?? [],
    }));
};

const packComponents = (components: readonly ComponentLayout[]): Map<string, XYPosition> => {
    const totalArea = components.reduce(
        (area, component) => area + component.width * component.height,
        0,
    );
    const widestComponent = Math.max(...components.map((component) => component.width));
    const targetRowWidth = Math.max(widestComponent, 1.6 * Math.sqrt(totalArea));
    const packed = new Map<string, XYPosition>();
    let rowX = 0;
    let rowY = 0;
    let rowHeight = 0;

    for (const component of components) {
        if (rowX > 0 && rowX + component.width > targetRowWidth) {
            rowX = 0;
            rowY += rowHeight + GRAPH_AUTO_LAYOUT_COMPONENT_SEPARATION;
            rowHeight = 0;
        }
        for (const [id, position] of component.positions) {
            packed.set(id, { x: rowX + position.x, y: rowY + position.y });
        }
        rowX += component.width + GRAPH_AUTO_LAYOUT_COMPONENT_SEPARATION;
        rowHeight = Math.max(rowHeight, component.height);
    }
    return packed;
};

export const calculateGraphAutoLayout = (
    nodes: readonly GraphAutoLayoutNode[],
    edges: readonly GraphAutoLayoutEdge[],
): ReadonlyMap<string, XYPosition> => {
    if (!nodes.length) return new Map();
    const normalized = normalizeGraph(nodes, edges);
    if (!normalized.units.length) return new Map();
    const componentSpacing = {
        node: GRAPH_AUTO_LAYOUT_NODE_SEPARATION,
        rank: GRAPH_AUTO_LAYOUT_RANK_SEPARATION,
        edge: GRAPH_AUTO_LAYOUT_EDGE_SEPARATION,
    };
    const components = splitComponents(normalized.units, normalized.edges).map((component) =>
        layoutGraphComponent(component, componentSpacing),
    );
    const positions = packComponents(components);
    const finiteUnitPositions = normalized.units.filter(
        (unit) => Number.isFinite(unit.position.x) && Number.isFinite(unit.position.y),
    );
    const anchorX = finiteUnitPositions.length
        ? Math.min(...finiteUnitPositions.map((unit) => unit.position.x))
        : 0;
    const anchorY = finiteUnitPositions.length
        ? Math.min(...finiteUnitPositions.map((unit) => unit.position.y))
        : 0;

    return new Map(
        [...positions.entries()].map(([id, position]) => [
            id,
            { x: Math.round(position.x + anchorX), y: Math.round(position.y + anchorY) },
        ]),
    );
};
