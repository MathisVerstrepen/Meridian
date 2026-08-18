import type { GraphNode, XYPosition } from '@vue-flow/core';

import type { GraphQuickAction } from '@/composables/useGraphQuickActions';
import type { QuickWorkflowCreatePayload } from '@/composables/useGraphEvents';
import { useNodePresets } from '@/composables/useNodePresets';
import { ExecutionPlanDirectionEnum, NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition } from '@/types/graph';
import type { WheelSlot } from '@/types/settings';
import type { User } from '@/types/user';
import { getQuickWorkflowSlots, type QuickWorkflowDirection } from '@/utils/quickWorkflow';

interface UseGraphQuickActionMenuOptions {
    graphId: Ref<string>;
    getNodes: Ref<GraphNode[]>;
    invocationPosition: () => XYPosition;
    executionActive: Ref<boolean>;
    deleteNode: (nodeId: string) => void;
    unlinkNode: (nodeId: string) => void;
    deleteGroup: (graphId: string, groupId: string) => void;
    fitGraph: () => unknown;
    autoLayoutGraph: () => unknown;
}

const GENERATOR_TYPES = new Set<string>([
    NodeTypeEnum.TEXT_TO_TEXT,
    NodeTypeEnum.PARALLELIZATION,
    NodeTypeEnum.ROUTING,
]);
const QUICK_WORKFLOW_ACTION_GROUPS: ReadonlyArray<
    readonly [NodeCategoryEnum, QuickWorkflowDirection]
> = [
    [NodeCategoryEnum.ATTACHMENT, 'target'],
    [NodeCategoryEnum.CONTEXT, 'target'],
    [NodeCategoryEnum.PROMPT, 'target'],
    [NodeCategoryEnum.ATTACHMENT, 'source'],
    [NodeCategoryEnum.CONTEXT, 'source'],
    [NodeCategoryEnum.PROMPT, 'source'],
];
const QUICK_WORKFLOW_CATEGORY_LABELS: Record<NodeCategoryEnum, string> = {
    [NodeCategoryEnum.PROMPT]: 'Prompt',
    [NodeCategoryEnum.CONTEXT]: 'Context',
    [NodeCategoryEnum.ATTACHMENT]: 'Attachment',
};

export const createAddQuickActionMetadata = (block: BlockDefinition, locked: boolean) => ({
    id: `add-${block.id}`,
    label: locked ? `${block.name} (Premium)` : block.name,
    icon: block.icon,
    accentColor: block.color,
    locked,
});

export const createQuickWorkflowActionMetadata = (
    slot: WheelSlot,
    category: NodeCategoryEnum,
    direction: QuickWorkflowDirection,
    index: number,
    getBlockByNodeType: (nodeType: NodeTypeEnum) => BlockDefinition | undefined,
) => {
    const mainBlock = slot.mainBloc ? getBlockByNodeType(slot.mainBloc) : undefined;
    const handleDirection = direction === 'target' ? 'input' : 'output';
    const mainNodeName = mainBlock?.name ?? slot.mainBloc ?? 'Workflow';
    return {
        id: `workflow-${category}-${direction}-${index}`,
        label: `${QUICK_WORKFLOW_CATEGORY_LABELS[category]} ${handleDirection} handle · ${mainNodeName} node`,
        icon: mainBlock?.icon ?? 'MaterialSymbolsAccountTreeOutlineRounded',
        accentColor: mainBlock?.color,
        compactHandle: { category, direction },
    };
};

export const useGraphQuickActionMenu = (options: UseGraphQuickActionMenuOptions) => {
    const { blockDefinitions, getBlockByNodeType } = useBlocks();
    const { placeBlock, copyNode, pasteNodes, duplicateNode, createCommentGroup } =
        useGraphActions();
    const { setExecutionPlan } = useExecutionPlan();
    const { canCreateQuickWorkflow, createQuickWorkflow } = useQuickWorkflow(options.graphId);
    const { blockSettings } = storeToRefs(useSettingsStore());
    const { user } = useUserSession();
    const { error } = useToast();
    const graphEvents = useGraphEvents();
    const { placeablePresets, placePreset } = useNodePresets(options.graphId);

    const nodeStillExists = (nodeId: string) =>
        options.getNodes.value.some((node) => node.id === nodeId);

    const stopAction = (): GraphQuickAction => ({
        id: 'stop-execution',
        label: 'Stop execution',
        icon: 'MaterialSymbolsStopRounded',
        danger: true,
        run: () => graphEvents.emit('stop-execution', { graphId: options.graphId.value }),
    });

    const createAddActions = (): GraphQuickAction[] =>
        Object.values(blockDefinitions.value)
            .flat()
            .map((block: BlockDefinition) => {
                const locked =
                    (user.value as User | null)?.plan_type === 'free' &&
                    block.nodeType === NodeTypeEnum.GITHUB;
                return {
                    ...createAddQuickActionMetadata(block, locked),
                    run: () => {
                        if (locked) {
                            error('GitHub nodes are available on the Premium plan.', {
                                title: 'Premium Feature',
                            });
                            return;
                        }
                        placeBlock({
                            graphId: options.graphId.value,
                            blocId: block.id,
                            positionFrom: options.invocationPosition(),
                            center: true,
                        });
                    },
                };
            });

    const createCanvasActions = (): GraphQuickAction[] => {
        const result: GraphQuickAction[] = [
            {
                id: 'add-node',
                label: 'Add node',
                icon: 'Fa6SolidPlus',
                childrenDisplay: 'external-fan',
                children: createAddActions(),
            },
        ];
        if (placeablePresets.value.length) {
            result.push({
                id: 'presets',
                label: 'Presets',
                icon: 'MaterialSymbolsDashboardCustomizeOutlineRounded',
                childrenDisplay: 'external-fan',
                children: placeablePresets.value.map(({ preset, locked }) => ({
                    id: `preset-${preset.id}`,
                    label: locked ? `${preset.name} (Premium)` : preset.name,
                    icon: 'MaterialSymbolsAccountTreeOutlineRounded',
                    accentColor: preset.accentColor,
                    locked,
                    run: () => placePreset(preset, options.invocationPosition()),
                })),
            });
        }
        if (localStorage.getItem('copiedNode')) {
            result.push({
                id: 'paste-here',
                label: 'Paste here',
                icon: 'MaterialSymbolsContentPasteRounded',
                run: () => pasteNodes(options.graphId.value, options.invocationPosition()),
            });
        }
        if (options.getNodes.value.length) {
            if (!options.executionActive.value) {
                result.push({
                    id: 'run-all',
                    label: 'Run all',
                    icon: 'CodiconRunAll',
                    run: () =>
                        setExecutionPlan(
                            options.graphId.value,
                            '',
                            ExecutionPlanDirectionEnum.ALL,
                        ),
                });
            }
            result.push({
                id: 'auto-layout',
                label: 'Auto layout',
                icon: 'MaterialSymbolsAccountTreeOutlineRounded',
                run: options.autoLayoutGraph,
            });
            result.push({
                id: 'fit-graph',
                label: 'Fit graph',
                icon: 'MdiFullscreen',
                run: options.fitGraph,
            });
        }
        if (options.executionActive.value) result.push(stopAction());
        return result;
    };

    const deleteCapturedNodes = (nodeIds: string[]) => {
        for (const nodeId of nodeIds) {
            if (!nodeStillExists(nodeId)) continue;
            if (nodeId.startsWith('group-')) options.deleteGroup(options.graphId.value, nodeId);
            else options.deleteNode(nodeId);
        }
    };

    const createSelectionActions = (capturedNodes: GraphNode[]): GraphQuickAction[] => {
        const nodeIds = capturedNodes.map((node) => node.id);
        const result: GraphQuickAction[] = [
            {
                id: 'copy-selection',
                label: 'Copy selected',
                icon: 'MaterialSymbolsContentCopyOutlineRounded',
                run: () => copyNode(options.graphId.value, [...nodeIds]),
            },
            {
                id: 'run-selection',
                label: 'Run selected',
                icon: 'CodiconRunAll',
                run: () =>
                    setExecutionPlan(
                        options.graphId.value,
                        nodeIds.filter(nodeStillExists).join(','),
                        ExecutionPlanDirectionEnum.MULTIPLE,
                    ),
            },
        ];
        if (capturedNodes.every((node) => !node.id.startsWith('group-') && !node.parentNode)) {
            result.push({
                id: 'create-group',
                label: 'Create group',
                icon: 'MajesticonsDuplicateLine',
                run: () => {
                    const nodes = nodeIds
                        .map((id) => options.getNodes.value.find((node) => node.id === id))
                        .filter((node): node is GraphNode => !!node);
                    if (nodes.length === nodeIds.length) {
                        void createCommentGroup(options.graphId.value, nodes);
                    }
                },
            });
        }
        if (capturedNodes.some((node) => node.parentNode)) {
            result.push({
                id: 'unlink-selection',
                label: 'Unlink grouped nodes',
                icon: 'MingcuteUnlinkLine',
                run: () => nodeIds.filter(nodeStillExists).forEach(options.unlinkNode),
            });
        }
        result.push({
            id: 'delete-selection',
            label: 'Delete selected',
            icon: 'MaterialSymbolsDeleteRounded',
            danger: true,
            run: () => deleteCapturedNodes(nodeIds),
        });
        if (options.executionActive.value) result.push(stopAction());
        return result;
    };

    const createQuickWorkflowActions = (nodeId: string): GraphQuickAction[] => {
        const result: GraphQuickAction[] = [];
        for (const [category, direction] of QUICK_WORKFLOW_ACTION_GROUPS) {
            const slots = getQuickWorkflowSlots(blockSettings.value, category, direction) ?? [];
            slots.forEach((slot, index) => {
                const payload: QuickWorkflowCreatePayload = {
                    fromNodeId: nodeId,
                    category,
                    direction,
                    slot,
                };
                if (!canCreateQuickWorkflow(payload)) return;
                result.push({
                    ...createQuickWorkflowActionMetadata(
                        slot,
                        category,
                        direction,
                        index,
                        getBlockByNodeType,
                    ),
                    run: () => createQuickWorkflow(payload),
                });
            });
        }
        return result;
    };

    const createNodeActions = (capturedNode: GraphNode): GraphQuickAction[] => {
        const nodeId = capturedNode.id;
        if (nodeId.startsWith('group-')) {
            const groupActions: GraphQuickAction[] = [
                {
                    id: 'copy-group',
                    label: 'Copy group',
                    icon: 'MaterialSymbolsContentCopyOutlineRounded',
                    run: () => copyNode(options.graphId.value, [nodeId]),
                },
                {
                    id: 'delete-group',
                    label: 'Delete group',
                    icon: 'MaterialSymbolsDeleteRounded',
                    danger: true,
                    run: () => {
                        if (nodeStillExists(nodeId)) options.deleteGroup(options.graphId.value, nodeId);
                    },
                },
            ];
            if (options.executionActive.value) groupActions.push(stopAction());
            return groupActions;
        }

        const result: GraphQuickAction[] = [];
        const workflows = createQuickWorkflowActions(nodeId);
        if (workflows.length) {
            result.push({
                id: 'quick-workflows',
                label: 'Quick workflows',
                icon: 'MaterialSymbolsAccountTreeOutlineRounded',
                childrenDisplay: 'external-fan',
                children: workflows,
            });
        }
        if (GENERATOR_TYPES.has(capturedNode.type ?? '')) {
            result.push(
                {
                    id: 'run-upstream',
                    label: 'Run upstream',
                    icon: 'CodiconRunAbove',
                    run: () =>
                        nodeStillExists(nodeId) &&
                        setExecutionPlan(
                            options.graphId.value,
                            nodeId,
                            ExecutionPlanDirectionEnum.UPSTREAM,
                        ),
                },
                {
                    id: 'run-node',
                    label: 'Run this node',
                    icon: 'CodiconRunAll',
                    run: () =>
                        nodeStillExists(nodeId) &&
                        setExecutionPlan(
                            options.graphId.value,
                            nodeId,
                            ExecutionPlanDirectionEnum.SELF,
                        ),
                },
            );
        }
        result.push({
            id: 'run-downstream',
            label: 'Run downstream',
            icon: 'CodiconRunBelow',
            run: () =>
                nodeStillExists(nodeId) &&
                setExecutionPlan(
                    options.graphId.value,
                    nodeId,
                    ExecutionPlanDirectionEnum.DOWNSTREAM,
                ),
        });
        result.push(
            {
                id: 'copy-node',
                label: 'Copy node',
                icon: 'MaterialSymbolsContentCopyOutlineRounded',
                run: () => copyNode(options.graphId.value, [nodeId]),
            },
            {
                id: 'duplicate-node',
                label: 'Duplicate node',
                icon: 'MaterialSymbolsControlPointDuplicateOutlineRounded',
                run: () =>
                    nodeStillExists(nodeId) && duplicateNode(options.graphId.value, nodeId),
            },
        );
        if (capturedNode.parentNode) {
            result.push({
                id: 'unlink-node',
                label: 'Unlink from group',
                icon: 'MingcuteUnlinkLine',
                run: () => nodeStillExists(nodeId) && options.unlinkNode(nodeId),
            });
        }
        result.push({
            id: 'delete-node',
            label: 'Delete node',
            icon: 'MaterialSymbolsDeleteRounded',
            danger: true,
            run: () => nodeStillExists(nodeId) && options.deleteNode(nodeId),
        });
        if (options.executionActive.value) result.push(stopAction());
        return result;
    };

    return { createCanvasActions, createSelectionActions, createNodeActions };
};
