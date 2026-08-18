import { graphlib, layout } from '@dagrejs/dagre';
import type { XYPosition } from '@vue-flow/core';

import {
    partitionAttachmentStackSubgraphs,
    placeAttachmentStacks,
    reserveAttachmentStackEnvelopes,
} from '@/utils/graphAutoLayoutAttachmentStacks';
import { mergePromptFanoutStageBlocks } from '@/utils/graphAutoLayoutBranchColumns';
import {
    derivePromptStageConstraints,
    mergeGeneratorSpineBlocks,
    type LayoutConstraintEdge,
    type LayoutHorizontalBlock,
} from '@/utils/graphAutoLayoutConstraints';
import { mergeSerialSpinePromptBlocks } from '@/utils/graphAutoLayoutSerialPrompts';

interface ComponentLayoutNode {
    id: string;
    position: XYPosition;
    width: number;
    height: number;
    type?: string;
    parentNode?: string;
}

export type NormalizedEdge = LayoutConstraintEdge;

export interface LayoutComponentInput {
    units: ComponentLayoutNode[];
    edges: NormalizedEdge[];
}

export interface ComponentLayout {
    positions: Map<string, XYPosition>;
    width: number;
    height: number;
}

interface ComponentSpacing {
    node: number;
    rank: number;
    edge: number;
}

const compareIds = (left: string, right: string) => left.localeCompare(right);

const dagreCenters = (
    units: readonly ComponentLayoutNode[],
    edges: readonly NormalizedEdge[],
    rankdir: 'LR' | 'TB',
    spacing: ComponentSpacing,
): Map<string, XYPosition> => {
    const graph = new graphlib.Graph();
    graph.setGraph({
        rankdir,
        ranker: 'network-simplex',
        acyclicer: 'greedy',
        nodesep: spacing.node,
        ranksep: spacing.rank,
        edgesep: spacing.edge,
        marginx: 0,
        marginy: 0,
    });
    graph.setDefaultEdgeLabel(() => ({}));
    for (const unit of units) graph.setNode(unit.id, { width: unit.width, height: unit.height });
    for (const edge of edges) graph.setEdge(edge.source, edge.target);
    layout(graph);
    return new Map(
        units.map((unit) => {
            const position = graph.node(unit.id);
            return [unit.id, { x: position.x, y: position.y }];
        }),
    );
};

const splitLateralSubgraphs = (
    lateralEdges: readonly NormalizedEdge[],
): { members: string[]; edges: NormalizedEdge[] }[] => {
    const adjacency = new Map<string, Set<string>>();
    for (const edge of lateralEdges) {
        if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
        if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
        adjacency.get(edge.source)?.add(edge.target);
        adjacency.get(edge.target)?.add(edge.source);
    }

    const subgraphByUnit = new Map<string, number>();
    const memberGroups: string[][] = [];
    for (const start of [...adjacency.keys()].sort(compareIds)) {
        if (subgraphByUnit.has(start)) continue;
        const subgraphIndex = memberGroups.length;
        const pending = [start];
        let pendingIndex = 0;
        const members: string[] = [];
        subgraphByUnit.set(start, subgraphIndex);
        while (pendingIndex < pending.length) {
            const id = pending[pendingIndex];
            pendingIndex += 1;
            if (!id) continue;
            members.push(id);
            for (const neighbor of [...(adjacency.get(id) ?? [])].sort(compareIds)) {
                if (subgraphByUnit.has(neighbor)) continue;
                subgraphByUnit.set(neighbor, subgraphIndex);
                pending.push(neighbor);
            }
        }
        members.sort(compareIds);
        memberGroups.push(members);
    }

    const edgeGroups = memberGroups.map((): NormalizedEdge[] => []);
    for (const edge of lateralEdges) {
        const subgraphIndex = subgraphByUnit.get(edge.source);
        if (subgraphIndex !== undefined) edgeGroups[subgraphIndex]?.push(edge);
    }
    return memberGroups.map((members, index) => ({ members, edges: edgeGroups[index] ?? [] }));
};

const assignNearestParticipantRows = (
    members: readonly string[],
    edges: readonly NormalizedEdge[],
    participantRows: ReadonlyMap<string, number>,
): Map<string, number> => {
    const participants = members.filter((id) => participantRows.has(id)).sort(compareIds);
    if (!participants.length) return new Map(members.map((id) => [id, 0]));

    const adjacency = new Map(members.map((id) => [id, new Set<string>()]));
    for (const edge of edges) {
        adjacency.get(edge.source)?.add(edge.target);
        adjacency.get(edge.target)?.add(edge.source);
    }
    const assignedAnchor = new Map<string, string>();
    const pending = [...participants];
    let pendingIndex = 0;
    for (const participant of participants) assignedAnchor.set(participant, participant);
    while (pendingIndex < pending.length) {
        const id = pending[pendingIndex];
        pendingIndex += 1;
        if (!id) continue;
        const anchor = assignedAnchor.get(id);
        if (!anchor) continue;
        for (const neighbor of [...(adjacency.get(id) ?? [])].sort(compareIds)) {
            if (assignedAnchor.has(neighbor)) continue;
            assignedAnchor.set(neighbor, anchor);
            pending.push(neighbor);
        }
    }
    return new Map(
        members.map((id) => {
            const anchor = assignedAnchor.get(id) ?? participants[0]!;
            return [id, participantRows.get(anchor) ?? 0];
        }),
    );
};

export const layoutGraphComponent = (
    { units, edges }: LayoutComponentInput,
    spacing: ComponentSpacing,
): ComponentLayout => {
    const singleton = units[0];
    if (units.length === 1 && singleton) {
        return {
            positions: new Map([[singleton.id, { x: 0, y: 0 }]]),
            width: singleton.width,
            height: singleton.height,
        };
    }

    const unitsById = new Map(units.map((unit) => [unit.id, unit]));
    const verticalEdges = edges.filter((edge) => edge.category !== 'attachment');
    const verticalLayoutEdges = [
        ...verticalEdges,
        ...derivePromptStageConstraints(units, edges),
    ];
    const lateralEdges = edges.filter((edge) => edge.category === 'attachment');
    const verticalParticipantIds = new Set(
        verticalLayoutEdges.flatMap((edge) => [edge.source, edge.target]),
    );
    const verticalParticipants = units.filter((unit) => verticalParticipantIds.has(unit.id));
    const verticalCenters = verticalParticipants.length
        ? dagreCenters(verticalParticipants, verticalLayoutEdges, 'TB', spacing)
        : new Map<string, XYPosition>();
    const rowCenterValues = [
        ...new Set([...verticalCenters.values()].map((position) => position.y)),
    ].sort((left, right) => left - right);
    const rowByCenter = new Map(rowCenterValues.map((center, index) => [center, index]));
    const rowByUnit = new Map<string, number>();
    for (const [id, position] of verticalCenters) {
        rowByUnit.set(id, rowByCenter.get(position.y) ?? 0);
    }

    const lateralSubgraphs = splitLateralSubgraphs(lateralEdges);
    const { stacks: attachmentStacks, fallback: fallbackLateralSubgraphs } =
        partitionAttachmentStackSubgraphs(lateralSubgraphs, units, verticalParticipantIds);
    const attachmentStackSourceIds = new Set(
        attachmentStacks.flatMap((stack) => stack.sourceIds),
    );
    const lateralMemberIds = new Set<string>();
    for (const subgraph of fallbackLateralSubgraphs) {
        for (const id of subgraph.members) lateralMemberIds.add(id);
        const assignedRows = assignNearestParticipantRows(
            subgraph.members,
            subgraph.edges,
            rowByUnit,
        );
        for (const [id, row] of assignedRows) {
            if (!rowByUnit.has(id)) rowByUnit.set(id, row);
        }
    }
    for (const unit of units) {
        if (!rowByUnit.has(unit.id)) rowByUnit.set(unit.id, 0);
    }

    const initialBlocks: LayoutHorizontalBlock[] = [];
    for (const subgraph of fallbackLateralSubgraphs) {
        const members = subgraph.members
            .map((id) => unitsById.get(id))
            .filter((unit): unit is ComponentLayoutNode => unit !== undefined);
        const lateralCenters = dagreCenters(members, subgraph.edges, 'LR', spacing);
        const orderedMembers = [...members].sort(
            (left, right) =>
                (lateralCenters.get(left.id)?.x ?? 0) -
                    (lateralCenters.get(right.id)?.x ?? 0) || compareIds(left.id, right.id),
        );
        let nextLeft = 0;
        const packedMembers = orderedMembers.map((unit) => {
            const member = { id: unit.id, left: nextLeft };
            nextLeft += unit.width + spacing.node;
            return member;
        });
        const anchorId = subgraph.members
            .filter((id) => verticalParticipantIds.has(id))
            .sort(compareIds)[0];
        const anchorMember = packedMembers.find((member) => member.id === anchorId);
        const anchorUnit = anchorId ? unitsById.get(anchorId) : undefined;
        const preferredLeft =
            anchorId && anchorMember && anchorUnit
                ? (verticalCenters.get(anchorId)?.x ?? 0) -
                  (anchorMember.left + anchorUnit.width / 2)
                : 0;
        initialBlocks.push({
            id: subgraph.members[0] ?? '',
            preferredLeft,
            members: packedMembers,
        });
    }
    for (const unit of verticalParticipants) {
        if (lateralMemberIds.has(unit.id)) continue;
        initialBlocks.push({
            id: unit.id,
            preferredLeft: (verticalCenters.get(unit.id)?.x ?? 0) - unit.width / 2,
            members: [{ id: unit.id, left: 0 }],
        });
    }

    const { blocks, rowByNode: reservedRowByUnit } = reserveAttachmentStackEnvelopes(
        attachmentStacks,
        units,
        initialBlocks,
        rowByUnit,
        spacing,
    );

    const rows = new Map<number, ComponentLayoutNode[]>();
    for (const unit of units) {
        if (attachmentStackSourceIds.has(unit.id)) continue;
        const row = reservedRowByUnit.get(unit.id) ?? 0;
        if (!rows.has(row)) rows.set(row, []);
        rows.get(row)?.push(unit);
    }
    const rowIndexes = [...rows.keys()].sort((left, right) => left - right);
    const centerYByRow = new Map<number, number>();
    let nextTop = 0;
    for (const row of rowIndexes) {
        const rowHeight = Math.max(...(rows.get(row) ?? []).map((unit) => unit.height));
        centerYByRow.set(row, nextTop + rowHeight / 2);
        nextTop += rowHeight + spacing.rank;
    }

    const spineBlocks = mergeGeneratorSpineBlocks(units, edges, blocks, reservedRowByUnit);
    const serialPromptBlocks = mergeSerialSpinePromptBlocks(
        units,
        edges,
        spineBlocks,
        reservedRowByUnit,
    );
    const constrainedBlocks = mergePromptFanoutStageBlocks(
        units,
        edges,
        serialPromptBlocks,
        reservedRowByUnit,
        spacing,
    );
    constrainedBlocks.sort(
        (left, right) => left.preferredLeft - right.preferredLeft || compareIds(left.id, right.id),
    );
    const rightBoundaryByRow = new Map<number, number>();
    const positions = new Map<string, XYPosition>();
    for (const block of constrainedBlocks) {
        const boundsByRow = new Map<number, { left: number; right: number }>();
        for (const member of block.members) {
            const unit = unitsById.get(member.id);
            if (!unit) continue;
            const row = reservedRowByUnit.get(member.id) ?? 0;
            const bounds = boundsByRow.get(row);
            boundsByRow.set(row, {
                left: Math.min(bounds?.left ?? Infinity, member.left),
                right: Math.max(bounds?.right ?? -Infinity, member.left + unit.width),
            });
        }
        let shift = block.preferredLeft;
        for (const [row, bounds] of boundsByRow) {
            const occupiedRight = rightBoundaryByRow.get(row);
            if (occupiedRight !== undefined) {
                shift = Math.max(shift, occupiedRight + spacing.node - bounds.left);
            }
        }
        for (const member of block.members) {
            const unit = unitsById.get(member.id);
            if (!unit) continue;
            const row = reservedRowByUnit.get(member.id) ?? 0;
            positions.set(member.id, {
                x: member.left + shift,
                y: (centerYByRow.get(row) ?? 0) - unit.height / 2,
            });
        }
        for (const [row, bounds] of boundsByRow) {
            rightBoundaryByRow.set(
                row,
                Math.max(rightBoundaryByRow.get(row) ?? -Infinity, bounds.right + shift),
            );
        }
    }

    const corePositions = new Map(
        [...positions].filter(([id]) => !attachmentStackSourceIds.has(id)),
    );
    for (const [id, position] of placeAttachmentStacks(
        attachmentStacks,
        units,
        corePositions,
        spacing,
    )) {
        positions.set(id, position);
    }

    const minimumX = Math.min(...units.map((unit) => positions.get(unit.id)?.x ?? 0));
    const minimumY = Math.min(...units.map((unit) => positions.get(unit.id)?.y ?? 0));
    const maximumX = Math.max(
        ...units.map((unit) => (positions.get(unit.id)?.x ?? 0) + unit.width),
    );
    const maximumY = Math.max(
        ...units.map((unit) => (positions.get(unit.id)?.y ?? 0) + unit.height),
    );
    return {
        positions: new Map(
            [...positions].map(([id, position]) => [
                id,
                { x: position.x - minimumX, y: position.y - minimumY },
            ]),
        ),
        width: maximumX - minimumX,
        height: maximumY - minimumY,
    };
};
