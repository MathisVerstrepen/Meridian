import { NodeTypeEnum } from '@/types/enums';
import {
    deriveGeneratorSpines,
    type LayoutConstraintEdge,
    type LayoutHorizontalBlock,
} from '@/utils/graphAutoLayoutConstraints';

interface SerialPromptNode {
    id: string;
    type?: string;
    width: number;
}

interface SerialPromptCandidate {
    targetId: string;
    promptId: string;
    spineBlock: LayoutHorizontalBlock;
    promptBlock: LayoutHorizontalBlock;
    promptLeft: number;
}

const PROMPT_TARGET_RATIO = 0.33;
const compareIds = (left: string, right: string) => left.localeCompare(right);

const addToSetMap = (map: Map<string, Set<string>>, key: string, value: string) => {
    if (!map.has(key)) map.set(key, new Set());
    map.get(key)?.add(value);
};

export const mergeSerialSpinePromptBlocks = (
    nodes: readonly SerialPromptNode[],
    edges: readonly LayoutConstraintEdge[],
    blocks: readonly LayoutHorizontalBlock[],
    rowByNode: ReadonlyMap<string, number>,
): LayoutHorizontalBlock[] => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    const blockByMember = new Map<string, LayoutHorizontalBlock>();
    const memberLeftById = new Map<string, number>();
    for (const block of blocks) {
        for (const member of block.members) {
            blockByMember.set(member.id, block);
            memberLeftById.set(member.id, member.left);
        }
    }

    const promptSources = new Map<string, Set<string>>();
    const promptTargets = new Map<string, Set<string>>();
    for (const edge of edges) {
        if (edge.category !== 'prompt') continue;
        addToSetMap(promptSources, edge.target, edge.source);
        addToSetMap(promptTargets, edge.source, edge.target);
    }

    const candidates: SerialPromptCandidate[] = [];
    for (const spine of deriveGeneratorSpines(nodes, edges)) {
        for (let index = 1; index < spine.length; index += 1) {
            const predecessorId = spine[index - 1]!;
            const targetId = spine[index]!;
            const sourceIds = [...(promptSources.get(targetId) ?? [])].sort(compareIds);
            const promptId = sourceIds[0];
            if (!promptId || sourceIds.length !== 1) continue;
            const spineBlock = blockByMember.get(targetId);
            const promptBlock = blockByMember.get(promptId);
            const target = nodesById.get(targetId);
            const prompt = nodesById.get(promptId);
            const targetLeft = memberLeftById.get(targetId);
            const predecessorRow = rowByNode.get(predecessorId);
            const promptRow = rowByNode.get(promptId);
            const targetRow = rowByNode.get(targetId);
            if (
                !spineBlock ||
                spineBlock !== blockByMember.get(predecessorId) ||
                !promptBlock ||
                promptBlock === spineBlock ||
                promptBlock.members.length !== 1 ||
                promptBlock.members[0]?.id !== promptId ||
                prompt?.type !== NodeTypeEnum.PROMPT ||
                promptTargets.get(promptId)?.size !== 1 ||
                !promptTargets.get(promptId)?.has(targetId) ||
                !target ||
                targetLeft === undefined ||
                predecessorRow === undefined ||
                promptRow === undefined ||
                targetRow === undefined ||
                !(predecessorRow < promptRow && promptRow < targetRow)
            ) {
                continue;
            }
            candidates.push({
                targetId,
                promptId,
                spineBlock,
                promptBlock,
                promptLeft: targetLeft + PROMPT_TARGET_RATIO * target.width - prompt.width / 2,
            });
        }
    }
    candidates.sort(
        (left, right) =>
            compareIds(left.targetId, right.targetId) || compareIds(left.promptId, right.promptId),
    );

    const candidateCountByPromptBlock = new Map<LayoutHorizontalBlock, number>();
    for (const candidate of candidates) {
        candidateCountByPromptBlock.set(
            candidate.promptBlock,
            (candidateCountByPromptBlock.get(candidate.promptBlock) ?? 0) + 1,
        );
    }
    const candidatesBySpine = new Map<LayoutHorizontalBlock, SerialPromptCandidate[]>();
    for (const candidate of candidates) {
        if (candidateCountByPromptBlock.get(candidate.promptBlock) !== 1) continue;
        if (!candidatesBySpine.has(candidate.spineBlock)) {
            candidatesBySpine.set(candidate.spineBlock, []);
        }
        candidatesBySpine.get(candidate.spineBlock)?.push(candidate);
    }

    const consumedPrompts = new Set<LayoutHorizontalBlock>();
    const mergedBySpine = new Map<LayoutHorizontalBlock, LayoutHorizontalBlock>();
    for (const [spineBlock, spineCandidates] of candidatesBySpine) {
        mergedBySpine.set(spineBlock, {
            id: spineBlock.id,
            preferredLeft: spineBlock.preferredLeft,
            members: [
                ...spineBlock.members.map((member) => ({ ...member })),
                ...spineCandidates.map(({ promptId, promptLeft }) => ({
                    id: promptId,
                    left: promptLeft,
                })),
            ],
        });
        for (const candidate of spineCandidates) consumedPrompts.add(candidate.promptBlock);
    }

    return blocks
        .filter((block) => !consumedPrompts.has(block))
        .map((block) => mergedBySpine.get(block) ?? block);
};
