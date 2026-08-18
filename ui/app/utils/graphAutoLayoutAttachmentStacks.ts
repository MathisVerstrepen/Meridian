import type { XYPosition } from '@vue-flow/core';

import { NodeTypeEnum } from '@/types/enums';
import {
    isGeneratorNode,
    type LayoutConstraintEdge,
    type LayoutHorizontalBlock,
} from '@/utils/graphAutoLayoutConstraints';

export interface AttachmentStackNode {
    id: string;
    type?: string;
    width: number;
    height: number;
}

export interface AttachmentLateralSubgraph {
    members: string[];
    edges: LayoutConstraintEdge[];
}

export interface AttachmentStack {
    targetId: string;
    sourceIds: string[];
}

export interface AttachmentEnvelopeReservation {
    blocks: LayoutHorizontalBlock[];
    rowByNode: Map<string, number>;
}

interface StackInterval extends AttachmentStack {
    top: number;
    bottom: number;
    width: number;
}

interface PlacementObstacle {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

const compareIds = (left: string, right: string) => left.localeCompare(right);

const isAttachmentSource = (node: AttachmentStackNode | undefined): boolean =>
    node?.type === NodeTypeEnum.FILE_PROMPT || node?.type === NodeTypeEnum.GITHUB;

const intervalsOverlap = (
    firstTop: number,
    firstBottom: number,
    secondTop: number,
    secondBottom: number,
): boolean => firstTop < secondBottom && firstBottom > secondTop;

const nearestCollisionFreeRight = (
    preferredRight: number,
    interval: StackInterval,
    obstacles: readonly PlacementObstacle[],
    separation: number,
): number => {
    let right = preferredRight;
    while (true) {
        const left = right - interval.width;
        const blockingLefts = obstacles
            .filter(
                (obstacle) =>
                    intervalsOverlap(interval.top, interval.bottom, obstacle.top, obstacle.bottom) &&
                    right > obstacle.left &&
                    left < obstacle.right,
            )
            .map((obstacle) => obstacle.left);
        if (!blockingLefts.length) return right;
        right = Math.min(...blockingLefts) - separation;
    }
};

export const partitionAttachmentStackSubgraphs = (
    subgraphs: readonly AttachmentLateralSubgraph[],
    nodes: readonly AttachmentStackNode[],
    verticalParticipantIds: ReadonlySet<string>,
): { stacks: AttachmentStack[]; fallback: AttachmentLateralSubgraph[] } => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const stacks: AttachmentStack[] = [];
    const fallback: AttachmentLateralSubgraph[] = [];
    for (const subgraph of subgraphs) {
        const targetIds = subgraph.members.filter((id) => verticalParticipantIds.has(id));
        const targetId = targetIds[0];
        const sourceIds = subgraph.members.filter((id) => id !== targetId).sort(compareIds);
        const directSourceIds = new Set(
            subgraph.edges
                .filter((edge) => edge.target === targetId && edge.source !== targetId)
                .map((edge) => edge.source),
        );
        const qualifies =
            targetIds.length === 1 &&
            !!targetId &&
            isGeneratorNode(nodesById.get(targetId)) &&
            sourceIds.length > 0 &&
            sourceIds.every((id) => isAttachmentSource(nodesById.get(id))) &&
            subgraph.edges.length === sourceIds.length &&
            directSourceIds.size === sourceIds.length &&
            sourceIds.every((id) => directSourceIds.has(id));
        if (qualifies) stacks.push({ targetId, sourceIds });
        else fallback.push(subgraph);
    }
    stacks.sort((left, right) => compareIds(left.targetId, right.targetId));
    return { stacks, fallback };
};

export const reserveAttachmentStackEnvelopes = (
    stacks: readonly AttachmentStack[],
    nodes: readonly AttachmentStackNode[],
    blocks: readonly LayoutHorizontalBlock[],
    rowByNode: ReadonlyMap<string, number>,
    spacing: { node: number },
): AttachmentEnvelopeReservation => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const stackByTarget = new Map(stacks.map((stack) => [stack.targetId, stack]));
    const reservedRows = new Map(rowByNode);
    const reservedBlocks = blocks.map((block) => {
        const targetMember = block.members.find((member) => stackByTarget.has(member.id));
        if (!targetMember) return block;
        const stack = stackByTarget.get(targetMember.id)!;
        const targetRow = rowByNode.get(stack.targetId);
        const right = targetMember.left - spacing.node;
        const sourceMembers = stack.sourceIds.map((id) => {
            if (targetRow !== undefined) reservedRows.set(id, targetRow);
            return { id, left: right - (nodesById.get(id)?.width ?? 0) };
        });
        return {
            ...block,
            members: [...block.members.map((member) => ({ ...member })), ...sourceMembers],
        };
    });
    return { blocks: reservedBlocks, rowByNode: reservedRows };
};

export const placeAttachmentStacks = (
    stacks: readonly AttachmentStack[],
    nodes: readonly AttachmentStackNode[],
    corePositions: ReadonlyMap<string, XYPosition>,
    spacing: { node: number; edge: number },
): Map<string, XYPosition> => {
    if (!stacks.length) return new Map();
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const intervals: StackInterval[] = stacks.map((stack) => {
        const target = nodesById.get(stack.targetId)!;
        const targetPosition = corePositions.get(stack.targetId)!;
        const totalHeight = stack.sourceIds.reduce(
            (height, id, index) =>
                height + (nodesById.get(id)?.height ?? 0) + (index ? spacing.edge : 0),
            0,
        );
        const top = targetPosition.y + target.height / 2 - totalHeight / 2;
        const width = Math.max(...stack.sourceIds.map((id) => nodesById.get(id)?.width ?? 0));
        return { ...stack, top, bottom: top + totalHeight, width };
    });
    intervals.sort((left, right) => left.top - right.top || compareIds(left.targetId, right.targetId));

    const obstacles: PlacementObstacle[] = [...corePositions]
        .sort(([leftId], [rightId]) => compareIds(leftId, rightId))
        .map(([id, position]) => {
            const node = nodesById.get(id)!;
            return {
                left: position.x,
                right: position.x + node.width,
                top: position.y,
                bottom: position.y + node.height,
            };
        });

    const positions = new Map<string, XYPosition>();
    for (const interval of intervals) {
        const targetPosition = corePositions.get(interval.targetId)!;
        const right = nearestCollisionFreeRight(
            targetPosition.x - spacing.node,
            interval,
            obstacles,
            spacing.node,
        );
        let top = interval.top;
        for (const id of interval.sourceIds) {
            const node = nodesById.get(id)!;
            positions.set(id, { x: right - node.width, y: top });
            top += node.height + spacing.edge;
        }
        obstacles.push({
            left: right - interval.width,
            right,
            top: interval.top,
            bottom: interval.bottom,
        });
    }
    return positions;
};
