import { NodeTypeEnum } from '@/types/enums';

export type LayoutEdgeCategory = 'attachment' | 'context' | 'generic' | 'prompt';

export interface LayoutConstraintNode {
    id: string;
    type?: string;
}

export interface LayoutConstraintEdge {
    source: string;
    target: string;
    category: LayoutEdgeCategory;
}

export interface LayoutHorizontalBlock {
    id: string;
    preferredLeft: number;
    members: Array<{ id: string; left: number }>;
}

interface SizedConstraintNode extends LayoutConstraintNode {
    width: number;
}

interface RawLayoutEdge {
    sourceHandle?: string | null;
    targetHandle?: string | null;
}

const KNOWN_CATEGORIES: LayoutEdgeCategory[] = ['attachment', 'context', 'prompt'];
const GENERATOR_TYPES = new Set<string>([
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
]);

const canonicalCategory = (handle: string | null | undefined): LayoutEdgeCategory | undefined => {
    if (!isRuntimeString(handle)) return undefined;
    const separator = handle.indexOf('_');
    if (separator <= 0 || separator === handle.length - 1) return undefined;
    const prefix = handle.slice(0, separator);
    return KNOWN_CATEGORIES.find((category) => category === prefix);
};

const categoryForNodeType = (nodeType: string | undefined): LayoutEdgeCategory | undefined => {
    if (nodeType === NodeTypeEnum.PROMPT) return 'prompt';
    if (nodeType === NodeTypeEnum.FILE_PROMPT || nodeType === NodeTypeEnum.GITHUB) {
        return 'attachment';
    }
    if (
        nodeType === NodeTypeEnum.TEXT_TO_TEXT ||
        nodeType === NodeTypeEnum.PARALLELIZATION ||
        nodeType === NodeTypeEnum.ROUTING ||
        nodeType === NodeTypeEnum.CONTEXT_MERGER
    ) {
        return 'context';
    }
    return undefined;
};

export const isGeneratorNode = (node: LayoutConstraintNode | undefined): boolean =>
    !!node?.type && GENERATOR_TYPES.has(node.type);

export const classifyLayoutEdge = (
    edge: RawLayoutEdge,
    sourceNodeType: string | undefined,
): LayoutEdgeCategory => {
    const targetCategory = canonicalCategory(edge.targetHandle);
    if (!targetCategory) return 'generic';

    const sourceCategory =
        edge.sourceHandle === null || edge.sourceHandle === undefined
            ? categoryForNodeType(sourceNodeType)
            : canonicalCategory(edge.sourceHandle);
    return sourceCategory === targetCategory ? targetCategory : 'generic';
};

export const derivePromptStageConstraints = (
    nodes: readonly LayoutConstraintNode[],
    edges: readonly LayoutConstraintEdge[],
): LayoutConstraintEdge[] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const generatorPredecessors = new Map<string, Set<string>>();
    const promptSources = new Map<string, Set<string>>();
    for (const edge of edges) {
        const source = nodesById.get(edge.source);
        const target = nodesById.get(edge.target);
        if (
            edge.category === 'context' &&
            isGeneratorNode(source) &&
            isGeneratorNode(target)
        ) {
            if (!generatorPredecessors.has(edge.target)) {
                generatorPredecessors.set(edge.target, new Set());
            }
            generatorPredecessors.get(edge.target)?.add(edge.source);
        }
        if (
            edge.category === 'prompt' &&
            source?.type === NodeTypeEnum.PROMPT &&
            isGeneratorNode(target)
        ) {
            if (!promptSources.has(edge.target)) promptSources.set(edge.target, new Set());
            promptSources.get(edge.target)?.add(edge.source);
        }
    }

    const constraints: LayoutConstraintEdge[] = [];
    for (const generatorId of [...generatorPredecessors.keys()].sort()) {
        const promptId = [...(promptSources.get(generatorId) ?? [])].sort()[0];
        if (!promptId) continue;
        for (const predecessorId of [...(generatorPredecessors.get(generatorId) ?? [])].sort()) {
            if (predecessorId === promptId) continue;
            constraints.push({ source: predecessorId, target: promptId, category: 'generic' });
        }
    }
    return constraints;
};

export const deriveGeneratorSpines = (
    nodes: readonly LayoutConstraintNode[],
    edges: readonly LayoutConstraintEdge[],
): string[][] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const generatorEdges = edges.filter(
        (edge) =>
            edge.category === 'context' &&
            isGeneratorNode(nodesById.get(edge.source)) &&
            isGeneratorNode(nodesById.get(edge.target)),
    );
    const indegree = new Map<string, number>();
    const outdegree = new Map<string, number>();
    for (const edge of generatorEdges) {
        outdegree.set(edge.source, (outdegree.get(edge.source) ?? 0) + 1);
        indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
    }
    const nextById = new Map<string, string>();
    const previousIds = new Set<string>();
    for (const edge of generatorEdges) {
        if (outdegree.get(edge.source) !== 1 || indegree.get(edge.target) !== 1) continue;
        nextById.set(edge.source, edge.target);
        previousIds.add(edge.target);
    }

    const spines: string[][] = [];
    for (const start of [...nextById.keys()].filter((id) => !previousIds.has(id)).sort()) {
        const spine = [start];
        const visited = new Set(spine);
        let current = start;
        while (nextById.has(current)) {
            const next = nextById.get(current);
            if (!next || visited.has(next)) break;
            spine.push(next);
            visited.add(next);
            current = next;
        }
        if (spine.length > 1) spines.push(spine);
    }
    return spines;
};

export const mergeGeneratorSpineBlocks = (
    nodes: readonly SizedConstraintNode[],
    edges: readonly LayoutConstraintEdge[],
    blocks: readonly LayoutHorizontalBlock[],
    rowByNode: ReadonlyMap<string, number>,
): LayoutHorizontalBlock[] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const blockByMember = new Map<string, LayoutHorizontalBlock>();
    for (const block of blocks) {
        for (const member of block.members) blockByMember.set(member.id, block);
    }

    const consumed = new Set<LayoutHorizontalBlock>();
    const merged: LayoutHorizontalBlock[] = [];
    for (const spine of deriveGeneratorSpines(nodes, edges)) {
        const spineBlocks = spine.map((id) => blockByMember.get(id));
        if (spineBlocks.some((block) => !block || consumed.has(block))) continue;
        const concreteBlocks = spineBlocks.filter(
            (block): block is LayoutHorizontalBlock => block !== undefined,
        );
        if (new Set(concreteBlocks).size !== spine.length) continue;
        const rows = spine.map((id) => rowByNode.get(id));
        if (rows.some((row) => row === undefined) || new Set(rows).size !== spine.length) continue;
        if (
            concreteBlocks.some(
                (block) =>
                    block.members.filter((member) => isGeneratorNode(nodesById.get(member.id)))
                        .length !== 1,
            )
        ) {
            continue;
        }

        const anchorId = [...spine].sort(
            (left, right) =>
                (rowByNode.get(left) ?? 0) - (rowByNode.get(right) ?? 0) ||
                left.localeCompare(right),
        )[0]!;
        const anchorBlock = blockByMember.get(anchorId)!;
        const anchorMember = anchorBlock.members.find((member) => member.id === anchorId)!;
        const preferredCenter =
            anchorBlock.preferredLeft +
            anchorMember.left +
            (nodesById.get(anchorId)?.width ?? 0) / 2;
        const members: Array<{ id: string; left: number }> = [];
        for (let index = 0; index < spine.length; index += 1) {
            const generatorId = spine[index]!;
            const block = concreteBlocks[index]!;
            const generatorMember = block.members.find((member) => member.id === generatorId)!;
            const generatorCenter =
                generatorMember.left + (nodesById.get(generatorId)?.width ?? 0) / 2;
            for (const member of block.members) {
                members.push({ id: member.id, left: member.left - generatorCenter });
            }
            consumed.add(block);
        }
        merged.push({ id: spine[0]!, preferredLeft: preferredCenter, members });
    }

    return [...blocks.filter((block) => !consumed.has(block)), ...merged];
};
import { isRuntimeString } from '@/utils/runtimeTypes';
