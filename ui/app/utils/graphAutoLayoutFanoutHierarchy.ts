import { NodeTypeEnum } from '@/types/enums';
import { isGeneratorNode, type LayoutConstraintEdge } from '@/utils/graphAutoLayoutConstraints';

export interface FanoutHierarchyNode {
    id: string;
    type?: string;
    width: number;
}

export interface FanoutHierarchyChild {
    childId: string;
    dedicatedPromptId?: string;
}

export interface FanoutHierarchyFamily {
    id: string;
    contextParentId?: string;
    promptParentId?: string;
    children: FanoutHierarchyChild[];
    dependencies: string[];
}

interface CandidateFamily extends Omit<FanoutHierarchyFamily, 'dependencies'> {
    childKey: string;
}

const compareIds = (left: string, right: string) => left.localeCompare(right);
const addToSetMap = (map: Map<string, Set<string>>, key: string, value: string) => {
    if (!map.has(key)) map.set(key, new Set());
    map.get(key)?.add(value);
};

const graphIndexes = (edges: readonly LayoutConstraintEdge[]) => {
    const contextSuccessors = new Map<string, Set<string>>();
    const contextPredecessors = new Map<string, Set<string>>();
    const promptTargets = new Map<string, Set<string>>();
    const promptSources = new Map<string, Set<string>>();
    for (const edge of edges) {
        if (edge.category === 'context') {
            addToSetMap(contextSuccessors, edge.source, edge.target);
            addToSetMap(contextPredecessors, edge.target, edge.source);
        } else if (edge.category === 'prompt') {
            addToSetMap(promptTargets, edge.source, edge.target);
            addToSetMap(promptSources, edge.target, edge.source);
        }
    }
    return { contextSuccessors, contextPredecessors, promptTargets, promptSources };
};

export const discoverFanoutHierarchy = (
    nodes: readonly FanoutHierarchyNode[],
    edges: readonly LayoutConstraintEdge[],
    rowByNode: ReadonlyMap<string, number>,
): FanoutHierarchyFamily[] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const indexes = graphIndexes(edges);
    const candidates: CandidateFamily[] = [];
    const blockedChildren = new Set<string>();
    const coParentKeys = new Set<string>();

    for (const parentId of [...indexes.contextSuccessors.keys()].sort(compareIds)) {
        const childIds = [...(indexes.contextSuccessors.get(parentId) ?? [])].sort(compareIds);
        const parentRow = rowByNode.get(parentId);
        if (
            !isGeneratorNode(nodesById.get(parentId)) ||
            childIds.length < 2 ||
            parentRow === undefined ||
            childIds.some((id) =>
                !isGeneratorNode(nodesById.get(id)) ||
                indexes.contextPredecessors.get(id)?.size !== 1 ||
                !indexes.contextPredecessors.get(id)?.has(parentId) ||
                rowByNode.get(id) === undefined ||
                parentRow >= (rowByNode.get(id) ?? -Infinity),
            )
        ) continue;

        const children: FanoutHierarchyChild[] = [];
        const sharedPromptIds = new Set<string>();
        let valid = true;
        for (const childId of childIds) {
            const sourceIds = [...(indexes.promptSources.get(childId) ?? [])].sort(compareIds);
            if (sourceIds.length > 1) {
                valid = false;
                break;
            }
            const promptId = sourceIds[0];
            if (!promptId) {
                children.push({ childId });
                continue;
            }
            const promptRow = rowByNode.get(promptId);
            const childRow = rowByNode.get(childId)!;
            if (
                nodesById.get(promptId)?.type !== NodeTypeEnum.PROMPT ||
                promptRow === undefined ||
                !(parentRow < promptRow && promptRow < childRow)
            ) {
                valid = false;
                break;
            }
            const targets = indexes.promptTargets.get(promptId) ?? new Set();
            if (targets.size === 1 && targets.has(childId)) {
                children.push({ childId, dedicatedPromptId: promptId });
            } else {
                sharedPromptIds.add(promptId);
                children.push({ childId });
            }
        }
        const childKey = childIds.join('\0');
        let promptParentId: string | undefined;
        if (valid && sharedPromptIds.size) {
            const sharedId = [...sharedPromptIds][0]!;
            const targets = [...(indexes.promptTargets.get(sharedId) ?? [])].sort(compareIds);
            if (
                sharedPromptIds.size !== 1 ||
                children.some(({ childId }) => !indexes.promptSources.get(childId)?.has(sharedId)) ||
                targets.join('\0') !== childKey
            ) valid = false;
            else promptParentId = sharedId;
        }
        if (!valid) {
            for (const childId of childIds) blockedChildren.add(childId);
            continue;
        }
        candidates.push({
            id: `context:${parentId}`,
            contextParentId: parentId,
            promptParentId,
            children,
            childKey,
        });
        if (promptParentId) coParentKeys.add(`${promptParentId}\0${childKey}`);
    }

    for (const promptId of [...indexes.promptTargets.keys()].sort(compareIds)) {
        const childIds = [...(indexes.promptTargets.get(promptId) ?? [])].sort(compareIds);
        const promptRow = rowByNode.get(promptId);
        const childKey = childIds.join('\0');
        if (
            childIds.length < 2 ||
            nodesById.get(promptId)?.type !== NodeTypeEnum.PROMPT ||
            promptRow === undefined ||
            coParentKeys.has(`${promptId}\0${childKey}`) ||
            childIds.some((id) =>
                !isGeneratorNode(nodesById.get(id)) ||
                indexes.promptSources.get(id)?.size !== 1 ||
                !indexes.promptSources.get(id)?.has(promptId) ||
                rowByNode.get(id) === undefined ||
                promptRow >= (rowByNode.get(id) ?? -Infinity),
            )
        ) continue;
        candidates.push({
            id: `prompt:${promptId}`,
            promptParentId: promptId,
            children: childIds.map((childId) => ({ childId })),
            childKey,
        });
    }

    const owners = new Map<string, CandidateFamily[]>();
    for (const candidate of candidates) {
        for (const { childId } of candidate.children) {
            if (!owners.has(childId)) owners.set(childId, []);
            owners.get(childId)?.push(candidate);
        }
    }
    const rejected = new Set<string>();
    for (const candidate of candidates) {
        if (candidate.children.some(({ childId }) =>
            blockedChildren.has(childId) || (owners.get(childId)?.length ?? 0) > 1,
        )) rejected.add(candidate.id);
    }
    const byContextParent = new Map(
        candidates.filter(({ contextParentId }) => contextParentId)
            .map((family) => [family.contextParentId!, family]),
    );
    const dependentIds = new Map<string, string[]>();
    for (const candidate of candidates) {
        for (const { childId } of candidate.children) {
            const dependency = byContextParent.get(childId);
            if (!dependency) continue;
            if (!dependentIds.has(dependency.id)) dependentIds.set(dependency.id, []);
            dependentIds.get(dependency.id)?.push(candidate.id);
        }
    }
    const rejectedQueue = [...rejected].sort(compareIds);
    let rejectedIndex = 0;
    while (rejectedIndex < rejectedQueue.length) {
        const rejectedId = rejectedQueue[rejectedIndex++]!;
        for (const dependentId of dependentIds.get(rejectedId) ?? []) {
            if (rejected.has(dependentId)) continue;
            rejected.add(dependentId);
            rejectedQueue.push(dependentId);
        }
    }

    const valid = candidates.filter(({ id }) => !rejected.has(id));
    const validByContextParent = new Map(
        valid.filter(({ contextParentId }) => contextParentId)
            .map((family) => [family.contextParentId!, family]),
    );
    const families = valid.map((candidate): FanoutHierarchyFamily => ({
        id: candidate.id,
        contextParentId: candidate.contextParentId,
        promptParentId: candidate.promptParentId,
        children: candidate.children,
        dependencies: candidate.children
            .map(({ childId }) => validByContextParent.get(childId)?.id)
            .filter((id): id is string => id !== undefined)
            .sort(compareIds),
    }));
    const byId = new Map(families.map((family) => [family.id, family]));
    const pendingCount = new Map(families.map((family) => [family.id, family.dependencies.length]));
    const dependents = new Map<string, string[]>();
    for (const family of families) {
        for (const dependency of family.dependencies) {
            if (!dependents.has(dependency)) dependents.set(dependency, []);
            dependents.get(dependency)?.push(family.id);
        }
    }
    let frontier = families.filter(({ id }) => pendingCount.get(id) === 0)
        .map(({ id }) => id).sort(compareIds);
    const ordered: FanoutHierarchyFamily[] = [];
    while (frontier.length) {
        const next: string[] = [];
        for (const id of frontier) {
            ordered.push(byId.get(id)!);
            for (const dependent of dependents.get(id) ?? []) {
                const count = (pendingCount.get(dependent) ?? 1) - 1;
                pendingCount.set(dependent, count);
                if (count === 0) next.push(dependent);
            }
        }
        frontier = next.sort(compareIds);
    }
    return ordered;
};
