import { useVueFlow, type GraphNode } from '@vue-flow/core';
import type { ComputedRef, Ref } from 'vue';

import type { QuickWorkflowCreatePayload } from '@/composables/useGraphEvents';
import { AUTO_PLACEMENT_GAP } from '@/composables/useGraphOverlaps';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition, NodeWithDimensions } from '@/types/graph';
import { calculateQuickWorkflowPositionOffset } from '@/utils/graphGeometry';
import {
    getQuickWorkflowBlockId,
    getQuickWorkflowHandleId,
    isValidQuickWorkflowSlot,
    nodeHasQuickWorkflowHandle,
} from '@/utils/quickWorkflow';

type GraphIdRef = Ref<string> | ComputedRef<string>;

const LINKED_NODE_OFFSETS: Partial<Record<NodeTypeEnum, { x: number; y: number }>> = {
    [NodeTypeEnum.PROMPT]: { x: -200, y: -300 },
    [NodeTypeEnum.FILE_PROMPT]: { x: -650, y: 0 },
    [NodeTypeEnum.GITHUB]: { x: -600, y: 0 },
};

export const useQuickWorkflow = (graphIdOverride?: GraphIdRef) => {
    const route = useRoute();
    const graphId = computed(() => graphIdOverride?.value ?? (route.params.id as string) ?? '');
    const { getNodes, getEdges } = useVueFlow('main-graph-' + graphId.value);
    const { placeBlock, placeEdge } = useGraphActions();
    const { getBlockByNodeType } = useBlocks();
    const { acceptsMultipleInputEdges } = useEdgeCompatibility();
    const { resolveOverlaps } = useGraphOverlaps(graphId);

    const targetIsAvailable = (payload: QuickWorkflowCreatePayload, anchor: GraphNode): boolean => {
        if (payload.direction !== 'target') return true;
        const explicitMultiple =
            payload.category === NodeCategoryEnum.CONTEXT &&
            [
                NodeTypeEnum.TEXT_TO_TEXT,
                NodeTypeEnum.PARALLELIZATION,
                NodeTypeEnum.ROUTING,
            ].includes(anchor.type as NodeTypeEnum);
        if (acceptsMultipleInputEdges(payload.category, anchor.type, explicitMultiple)) return true;
        const handleId = getQuickWorkflowHandleId(payload.category, anchor.id);
        return !getEdges.value.some(
            (edge) => edge.target === anchor.id && edge.targetHandle === handleId,
        );
    };

    const resolveDefinitions = (
        payload: QuickWorkflowCreatePayload,
    ): { main: BlockDefinition; options: BlockDefinition[] } | null => {
        if (!isValidQuickWorkflowSlot(payload.slot, payload.category, payload.direction)) return null;
        const mainType = payload.slot.mainBloc;
        if (!mainType || !getQuickWorkflowBlockId(mainType)) return null;
        const main = getBlockByNodeType(mainType);
        const options = payload.slot.options.map((option) => getBlockByNodeType(option));
        if (!main || options.some((option) => !option)) return null;
        return { main, options: options.filter((option): option is BlockDefinition => !!option) };
    };

    const placeLinkedNode = (
        definition: BlockDefinition,
        mainNode: NodeWithDimensions,
    ): NodeWithDimensions | undefined => {
        const offset = LINKED_NODE_OFFSETS[definition.nodeType];
        if (!offset) return;
        const linkedNode = placeBlock({
            graphId: graphId.value,
            blocId: definition.id,
            fromNodeId: mainNode.id,
            positionFrom: mainNode.position,
            positionOffset: offset,
        });
        if (!linkedNode) return;
        const category =
            definition.nodeType === NodeTypeEnum.PROMPT
                ? NodeCategoryEnum.PROMPT
                : NodeCategoryEnum.ATTACHMENT;
        placeEdge(
            graphId.value,
            linkedNode.id,
            mainNode.id,
            getQuickWorkflowHandleId(category, linkedNode.id),
            getQuickWorkflowHandleId(category, mainNode.id),
        );
        return linkedNode;
    };

    const createQuickWorkflow = (payload: QuickWorkflowCreatePayload): string | undefined => {
        if (!canCreateQuickWorkflow(payload)) return;
        const anchor = getNodes.value.find((node) => node.id === payload.fromNodeId);
        if (!anchor) return;
        const definitions = resolveDefinitions(payload);
        if (!definitions) return;

        const anchorHeight =
            (anchor as NodeWithDimensions).dimensions?.height ??
            (typeof anchor.height === 'number' ? anchor.height : 0);
        const anchorWidth =
            (anchor as NodeWithDimensions).dimensions?.width ??
            (typeof anchor.width === 'number'
                ? anchor.width
                : (getBlockByNodeType(anchor.type as NodeTypeEnum)?.minSize.width ?? 0));
        const mainHeight = definitions.main.minSize.height ?? 0;
        const mainWidth = definitions.main.minSize.width ?? 0;
        const positionOffset = calculateQuickWorkflowPositionOffset({
            category: payload.category,
            direction: payload.direction,
            anchorWidth,
            anchorHeight,
            mainWidth,
            mainHeight,
            gap: AUTO_PLACEMENT_GAP,
        });
        const mainNode = placeBlock({
            graphId: graphId.value,
            blocId: definitions.main.id,
            fromNodeId: anchor.id,
            positionFrom: anchor.position,
            positionOffset,
        });
        if (!mainNode) return;

        const anchorHandle = getQuickWorkflowHandleId(payload.category, anchor.id);
        const mainHandle = getQuickWorkflowHandleId(payload.category, mainNode.id);
        if (payload.direction === 'target') {
            placeEdge(graphId.value, mainNode.id, anchor.id, mainHandle, anchorHandle);
        } else {
            placeEdge(graphId.value, anchor.id, mainNode.id, anchorHandle, mainHandle);
        }

        const linkedNodes = definitions.options
            .map((definition) => placeLinkedNode(definition, mainNode))
            .filter((node): node is NodeWithDimensions => !!node);
        const linkedNodeIds = linkedNodes.map((node) => node.id);
        setTimeout(() => {
            if (
                payload.category === NodeCategoryEnum.ATTACHMENT ||
                payload.direction === 'source'
            ) {
                resolveOverlaps(mainNode.id, linkedNodeIds, {
                    direction: 'below',
                });
                return;
            }
            resolveOverlaps(mainNode.id, linkedNodeIds);
        }, 1);
        return mainNode.id;
    };

    function canCreateQuickWorkflow(payload: QuickWorkflowCreatePayload): boolean {
        if (!graphId.value) return false;
        const anchor = getNodes.value.find((node) => node.id === payload.fromNodeId);
        return !!(
            anchor &&
            nodeHasQuickWorkflowHandle(anchor.type, payload.category, payload.direction) &&
            targetIsAvailable(payload, anchor) &&
            resolveDefinitions(payload)
        );
    }

    return { createQuickWorkflow, canCreateQuickWorkflow };
};
