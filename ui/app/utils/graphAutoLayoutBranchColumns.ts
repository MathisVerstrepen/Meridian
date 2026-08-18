import type {
    LayoutConstraintEdge,
    LayoutHorizontalBlock,
} from '@/utils/graphAutoLayoutConstraints';
import {
    discoverFanoutHierarchy,
    type FanoutHierarchyFamily,
} from '@/utils/graphAutoLayoutFanoutHierarchy';

interface BranchColumnNode {
    id: string;
    type?: string;
    width: number;
}

interface BaseRef {
    kind: 'base';
    block: LayoutHorizontalBlock;
    left: number;
    right: number;
    minimumRow: number;
    maximumRow: number;
}

interface CompositeRef {
    kind: 'composite';
    family: FanoutHierarchyFamily;
    id: string;
    preferredLeft: number;
    parts: Array<{ ref: LayoutRef; shift: number }>;
    left: number;
    right: number;
    minimumRow: number;
    maximumRow: number;
}

type LayoutRef = BaseRef | CompositeRef;
const shiftedBounds = (ref: LayoutRef, shift: number) => ({
    left: ref.left + shift,
    right: ref.right + shift,
});

export const mergePromptFanoutStageBlocks = (
    nodes: readonly BranchColumnNode[],
    edges: readonly LayoutConstraintEdge[],
    blocks: readonly LayoutHorizontalBlock[],
    rowByNode: ReadonlyMap<string, number>,
    spacing: { node: number },
): LayoutHorizontalBlock[] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const blockByMember = new Map<string, LayoutHorizontalBlock>();
    const centerByMember = new Map<string, number>();
    const baseByBlock = new Map<LayoutHorizontalBlock, BaseRef>();
    for (const block of blocks) {
        let left = Infinity;
        let right = -Infinity;
        let minimumRow = Infinity;
        let maximumRow = -Infinity;
        let valid = true;
        for (const member of block.members) {
            const node = nodesById.get(member.id);
            const row = rowByNode.get(member.id);
            if (!node || row === undefined || blockByMember.has(member.id)) {
                valid = false;
                break;
            }
            blockByMember.set(member.id, block);
            centerByMember.set(member.id, member.left + node.width / 2);
            left = Math.min(left, member.left);
            right = Math.max(right, member.left + node.width);
            minimumRow = Math.min(minimumRow, row);
            maximumRow = Math.max(maximumRow, row);
        }
        if (valid && block.members.length) {
            baseByBlock.set(block, { kind: 'base', block, left, right, minimumRow, maximumRow });
        }
    }

    const families = discoverFanoutHierarchy(nodes, edges, rowByNode);
    const composites = new Map<string, CompositeRef>();
    const claimed = new Map<LayoutHorizontalBlock, string>();
    const failed = new Set<string>();
    for (const family of families) {
        if (family.dependencies.some((id) => failed.has(id) || !composites.has(id))) {
            failed.add(family.id);
            continue;
        }
        const contextBlock = family.contextParentId
            ? blockByMember.get(family.contextParentId)
            : undefined;
        const promptBlock = family.promptParentId
            ? blockByMember.get(family.promptParentId)
            : undefined;
        const parentBlocks = [contextBlock, promptBlock].filter(
            (block): block is LayoutHorizontalBlock => block !== undefined,
        );
        const parentIds = [family.contextParentId, family.promptParentId].filter(
            (id): id is string => id !== undefined,
        );
        const newBlocks: LayoutHorizontalBlock[] = [...parentBlocks];
        const dependencyByParent = new Map(
            family.dependencies.map((id) => {
                const composite = composites.get(id)!;
                return [composite.family.contextParentId!, composite] as const;
            }),
        );
        const branchParts: Array<{
            parts: Array<{ ref: LayoutRef; shift: number }>;
            left: number;
            right: number;
        }> = [];
        let valid = parentBlocks.length === parentIds.length &&
            new Set(parentBlocks).size === parentBlocks.length;
        let preferredLeft = 0;
        for (let index = 0; valid && index < parentBlocks.length; index += 1) {
            const block = parentBlocks[index]!;
            const id = parentIds[index]!;
            const base = baseByBlock.get(block);
            const center = centerByMember.get(id);
            const row = rowByNode.get(id);
            if (
                !base || center === undefined || row === undefined || base.maximumRow > row ||
                (id === family.promptParentId &&
                    (block.members.length !== 1 || block.members[0]?.id !== id))
            ) {
                valid = false;
                break;
            }
            if (id === (family.contextParentId ?? family.promptParentId)) {
                preferredLeft = block.preferredLeft + center;
            }
        }
        for (const child of family.children) {
            if (!valid) break;
            const dependency = dependencyByParent.get(child.childId);
            const childBlock = blockByMember.get(child.childId);
            const childRef: LayoutRef | undefined = dependency ??
                (childBlock ? baseByBlock.get(childBlock) : undefined);
            const childCenter = dependency ? 0 : centerByMember.get(child.childId);
            const childRow = rowByNode.get(child.childId);
            if (
                !childRef || childCenter === undefined || childRow === undefined ||
                childRef.minimumRow < childRow
            ) {
                valid = false;
                break;
            }
            if (!dependency && childBlock) newBlocks.push(childBlock);
            const parts = [{ ref: childRef, shift: -childCenter }];
            let left = childRef.left - childCenter;
            let right = childRef.right - childCenter;
            if (child.dedicatedPromptId) {
                const dedicatedBlock = blockByMember.get(child.dedicatedPromptId);
                const dedicatedBase = dedicatedBlock ? baseByBlock.get(dedicatedBlock) : undefined;
                const dedicatedCenter = centerByMember.get(child.dedicatedPromptId);
                if (
                    !dedicatedBlock || !dedicatedBase || dedicatedCenter === undefined ||
                    dedicatedBlock.members.length !== 1 ||
                    dedicatedBlock.members[0]?.id !== child.dedicatedPromptId
                ) {
                    valid = false;
                    break;
                }
                newBlocks.push(dedicatedBlock);
                parts.push({ ref: dedicatedBase, shift: -dedicatedCenter });
                left = Math.min(left, dedicatedBase.left - dedicatedCenter);
                right = Math.max(right, dedicatedBase.right - dedicatedCenter);
            }
            branchParts.push({ parts, left, right });
        }
        if (
            !valid || new Set(newBlocks).size !== newBlocks.length ||
            newBlocks.some((block) => claimed.has(block))
        ) {
            failed.add(family.id);
            continue;
        }

        let cursor = 0;
        const packedParts: Array<{ ref: LayoutRef; shift: number }> = [];
        for (const branch of branchParts) {
            const shift = cursor - branch.left;
            for (const part of branch.parts) {
                packedParts.push({ ref: part.ref, shift: part.shift + shift });
            }
            cursor = branch.right + shift + spacing.node;
        }
        const envelopeCenter = (cursor - spacing.node) / 2;
        for (const part of packedParts) part.shift -= envelopeCenter;
        const parts: Array<{ ref: LayoutRef; shift: number }> = [];
        for (let index = 0; index < parentBlocks.length; index += 1) {
            parts.push({
                ref: baseByBlock.get(parentBlocks[index]!)!,
                shift: -centerByMember.get(parentIds[index]!)!,
            });
        }
        parts.push(...packedParts);
        let left = Infinity;
        let right = -Infinity;
        let minimumRow = Infinity;
        let maximumRow = -Infinity;
        for (const part of parts) {
            const bounds = shiftedBounds(part.ref, part.shift);
            left = Math.min(left, bounds.left);
            right = Math.max(right, bounds.right);
            minimumRow = Math.min(minimumRow, part.ref.minimumRow);
            maximumRow = Math.max(maximumRow, part.ref.maximumRow);
        }
        const composite: CompositeRef = {
            kind: 'composite',
            family,
            id: contextBlock?.id ?? promptBlock!.id,
            preferredLeft,
            parts,
            left,
            right,
            minimumRow,
            maximumRow,
        };
        composites.set(family.id, composite);
        for (const block of newBlocks) claimed.set(block, family.id);
    }

    const owned = new Set(
        [...composites.values()].flatMap(({ family }) =>
            family.dependencies.filter((id) => composites.has(id)),
        ),
    );
    const flattened: LayoutHorizontalBlock[] = [];
    for (const composite of [...composites.values()].filter(({ family }) => !owned.has(family.id))) {
        const members: Array<{ id: string; left: number }> = [];
        const pending: Array<{ ref: LayoutRef; shift: number }> = [{ ref: composite, shift: 0 }];
        while (pending.length) {
            const current = pending.pop()!;
            if (current.ref.kind === 'base') {
                for (const member of current.ref.block.members) {
                    members.push({ id: member.id, left: member.left + current.shift });
                }
            } else {
                for (let index = current.ref.parts.length - 1; index >= 0; index -= 1) {
                    const part = current.ref.parts[index]!;
                    pending.push({ ref: part.ref, shift: current.shift + part.shift });
                }
            }
        }
        flattened.push({ id: composite.id, preferredLeft: composite.preferredLeft, members });
    }
    return [...blocks.filter((block) => !claimed.has(block)), ...flattened];
};
