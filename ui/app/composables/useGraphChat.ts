import { type GraphNode } from '@vue-flow/core';

import { DEFAULT_NODE_ID } from '@/constants';
import { AUTO_PLACEMENT_GAP } from '@/composables/useGraphOverlaps';
import { NodeTypeEnum } from '@/types/enums';
import type { ChatInputSubmission } from '@/types/chat';
import type { RepoContent } from '@/types/github';
import {
    calculateGeneratorChildPosition,
    type GeneratorPlacementNode,
} from '@/utils/graphGeometry';

type CreatedChatNodes = {
    generatorNodeId: string | undefined;
    promptNodeId: string | undefined;
};

export const useGraphChat = () => {
    const route = useRoute();
    const graphId = computed(() => firstRouteString(route.params.id) ?? '');

    const chatStore = useChatStore();
    const { error } = useToast();
    const { placeBlock, placeEdge } = useGraphActions();
    const { getBlockByNodeType } = useBlocks();

    const { upcomingModelData } = storeToRefs(chatStore);

    const { resolveOverlaps } = useGraphOverlaps();

    const getNodeHeight = (nodeId: string) => {
        const element = document.querySelector(`[data-id="${nodeId}"]`);
        if (element) {
            const style = window.getComputedStyle(element);
            const height = parseFloat(style.height);
            return height;
        }

        return 0;
    };

    const getNodeRect = (nodeId: string) => {
        const { findNode } = useGraphFlow('main-graph-' + graphId.value);

        const node = findNode(nodeId);

        if (!node) {
            console.error(`Node with ID ${nodeId} not found.`);
            error(`Node with ID ${nodeId} not found.`, { title: 'Error' });
            return {
                x: 0,
                y: 0,
                height: 0,
            };
        }

        const inputNodeHeight = getNodeHeight(node.id);
        const inputNodeBaseX = node.position?.x ?? 0;
        const inputNodeBaseY = node.position?.y ?? 0;

        return {
            x: inputNodeBaseX,
            y: inputNodeBaseY,
            height: inputNodeHeight,
        };
    };

    const getNodeWidth = (node: GraphNode): number => {
        const dimensionsWidth = node.dimensions.width;
        if (dimensionsWidth && dimensionsWidth > 0) return dimensionsWidth;
        if (isRuntimeNumber(node.width) && node.width > 0) return node.width;
        return getBlockByNodeType(nodeTypeOrUndefined(node.type))?.minSize.width ?? 0;
    };

    const getGeneratorPlacement = (fromNodeId: string) => {
        const parentRect = getNodeRect(fromNodeId);
        const { findNode, getNodes, getEdges } = useGraphFlow('main-graph-' + graphId.value);
        const parentNode = findNode(fromNodeId);
        const normalizedNodes: GeneratorPlacementNode[] = getNodes.value.map((node) => ({
            id: node.id,
            type: node.type,
            position: node.position,
            width: getNodeWidth(node),
            height:
                node.dimensions.height ??
                (isRuntimeNumber(node.height) ? node.height : 0),
        }));
        const normalizedParent: GeneratorPlacementNode = {
            id: fromNodeId,
            type: parentNode?.type,
            position: { x: parentRect.x, y: parentRect.y },
            width: parentNode ? getNodeWidth(parentNode) : 0,
            height: parentRect.height,
        };

        return calculateGeneratorChildPosition({
            parent: normalizedParent,
            nodes: normalizedNodes,
            edges: getEdges.value.map((edge) => ({ source: edge.source, target: edge.target })),
            gap: AUTO_PLACEMENT_GAP,
        });
    };

    const addTextToTextFromNodeId = (input: string, fromNodeId: string) => {
        const position = getGeneratorPlacement(fromNodeId);

        const newTextToTextNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-text-to-text',
            fromNodeId: fromNodeId,
            positionFrom: position,
            data: {
                ...upcomingModelData.value.data,
                reply: '',
            },
        });

        placeEdge(
            graphId.value,
            fromNodeId,
            newTextToTextNode?.id,
            null,
            'context_' + newTextToTextNode?.id,
        );

        return newTextToTextNode?.id;
    };

    const addTextToTextFromEmptyGraph = (input: string, forcedTextToTextNodeId: string | null) => {
        const newTextToTextNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-text-to-text',
            positionFrom: { x: 0, y: 350 },
            data: {
                ...upcomingModelData.value.data,
                reply: '',
            },
            forcedId: forcedTextToTextNodeId,
        });

        return newTextToTextNode?.id;
    };

    const addTextToTextInputNodes = (
        input: string,
        fromNodeId: string | null,
        forcedTextToTextNodeId: string | null = null,
    ) => {
        if (!fromNodeId || forcedTextToTextNodeId || fromNodeId === DEFAULT_NODE_ID) {
            return addTextToTextFromEmptyGraph(input, forcedTextToTextNodeId);
        } else {
            return addTextToTextFromNodeId(input, fromNodeId);
        }
    };

    const addPromptFromNodeId = (input: string, fromNodeId: string) => {
        const { x: inputNodeBaseX, y: inputNodeBaseY, height: _ } = getNodeRect(fromNodeId);

        const newPromptNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-prompt-text',
            fromNodeId: fromNodeId,
            positionFrom: { x: inputNodeBaseX, y: inputNodeBaseY },
            positionOffset: { x: -200, y: -300 },
            data: {
                prompt: input,
            },
        });

        placeEdge(graphId.value, newPromptNode?.id, fromNodeId, null, 'prompt_' + fromNodeId);

        return newPromptNode?.id;
    };

    const addGithubInputNodes = (context: RepoContent, fromNodeId: string) => {
        const { x: inputNodeBaseX, y: inputNodeBaseY, height: _ } = getNodeRect(fromNodeId);

        const newGithubNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-github-context',
            fromNodeId: fromNodeId,
            positionFrom: { x: inputNodeBaseX, y: inputNodeBaseY },
            positionOffset: { x: -600, y: 0 },
            data: {
                repo: context.repo,
                files: context.selectedFiles,
                selectedIssues: context.selectedIssues ?? [],
                branch: context.currentBranch,
            },
        });

        placeEdge(graphId.value, newGithubNode?.id, fromNodeId, null, 'attachment_' + fromNodeId);

        return newGithubNode?.id;
    };

    const addFilesPromptInputNodes = (files: FileSystemObject[], textToTextNodeId: string) => {
        const { x: inputNodeBaseX, y: inputNodeBaseY, height: _ } = getNodeRect(textToTextNodeId);

        const newBlock = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-prompt-file',
            fromNodeId: textToTextNodeId,
            positionFrom: { x: inputNodeBaseX, y: inputNodeBaseY },
            positionOffset: { x: -650, y: 0 },
            data: {
                files: files,
            },
        });

        placeEdge(
            graphId.value,
            newBlock?.id,
            textToTextNodeId,
            null,
            'attachment_' + textToTextNodeId,
        );

        return newBlock?.id;
    };

    const addParallelizationFromEmptyGraph = (
        input: string,
        forcedParallelizationNodeId: string | null,
    ) => {
        const newParallelizationNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-parallelization',
            positionFrom: { x: 0, y: 350 },
            data: {
                ...upcomingModelData.value.data,
            },
            forcedId: forcedParallelizationNodeId,
        });

        return newParallelizationNode?.id;
    };

    const addRoutingFromEmptyGraph = (input: string, forcedRoutingNodeId: string | null) => {
        const newRoutingNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-routing',
            positionFrom: { x: 0, y: 350 },
            forcedId: forcedRoutingNodeId,
            data: {
                ...upcomingModelData.value.data,
            },
        });

        return newRoutingNode?.id;
    };

    const addParallelizationInputNode = (
        input: string,
        fromNodeId: string | null,
        forcedParallelizationNodeId: string | null = null,
    ) => {
        if (!fromNodeId || forcedParallelizationNodeId || fromNodeId === DEFAULT_NODE_ID) {
            return addParallelizationFromEmptyGraph(input, forcedParallelizationNodeId);
        }

        const position = getGeneratorPlacement(fromNodeId);

        const newParallelizationNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-parallelization',
            fromNodeId: fromNodeId,
            positionFrom: position,
            data: {
                ...upcomingModelData.value.data,
            },
        });

        placeEdge(
            graphId.value,
            fromNodeId,
            newParallelizationNode?.id,
            null,
            'context_' + newParallelizationNode?.id,
        );

        return newParallelizationNode?.id;
    };

    const addRoutingInputNode = (
        input: string,
        fromNodeId: string | null,
        forcedRoutingNodeId: string | null = null,
    ) => {
        if (!fromNodeId || forcedRoutingNodeId || fromNodeId === DEFAULT_NODE_ID) {
            return addRoutingFromEmptyGraph(input, forcedRoutingNodeId);
        }

        const position = getGeneratorPlacement(fromNodeId);

        const newRoutingNode = placeBlock({
            graphId: graphId.value,
            blocId: 'primary-model-routing',
            fromNodeId: fromNodeId,
            positionFrom: position,
            data: {
                ...upcomingModelData.value.data,
            },
        });

        placeEdge(
            graphId.value,
            fromNodeId,
            newRoutingNode?.id,
            null,
            'context_' + newRoutingNode?.id,
        );

        return newRoutingNode?.id;
    };

    const updatePromptNodeText = (nodeId: string, text: string) => {
        const { updateNode, findNode } = useGraphFlow('main-graph-' + graphId.value);
        const node = findNode(nodeId);
        if (node) {
            node.data.prompt = text;
            updateNode(nodeId, {
                data: {
                    ...node.data,
                    prompt: text,
                },
            });
        } else {
            console.error(`Node with ID ${nodeId} not found.`);
            error(`Node with ID ${nodeId} not found.`, { title: 'Error' });
        }
    };

    const isCanvasEmpty = () => {
        const { nodes } = useGraphFlow('main-graph-' + graphId.value);
        return nodes.value.length === 0;
    };

    const createNodeFromVariant = (
        generatorNode: NodeTypeEnum,
        fromNodeId: string,
        options: { submission: ChatInputSubmission; forcedNodeId?: string | null },
    ): CreatedChatNodes => {
        let newNodeId: string | undefined;
        let promptNodeId: string | undefined;
        const optionIds: string[] = [];
        const { submission, forcedNodeId = null } = options;

        switch (generatorNode) {
            case NodeTypeEnum.TEXT_TO_TEXT:
                newNodeId = addTextToTextInputNodes(submission.message, fromNodeId, forcedNodeId);
                break;
            case NodeTypeEnum.PARALLELIZATION:
                newNodeId = addParallelizationInputNode(submission.message, fromNodeId, forcedNodeId);
                break;
            case NodeTypeEnum.ROUTING:
                newNodeId = addRoutingInputNode(submission.message, fromNodeId, forcedNodeId);
                break;
            default:
                console.warn(`Unknown node variant: ${generatorNode}`);
                break;
        }

        if (newNodeId) {
            promptNodeId = addPromptFromNodeId(submission.message, newNodeId);
            if (promptNodeId) optionIds.push(promptNodeId);

            if (submission.files.length > 0) {
                const fileNodeId = addFilesPromptInputNodes(submission.files, newNodeId);
                if (fileNodeId) optionIds.push(fileNodeId);
            }

            const githubContext = submission.githubContext;
            if (
                githubContext &&
                (githubContext.selectedFiles.length > 0 ||
                    (githubContext.selectedIssues?.length ?? 0) > 0)
            ) {
                const githubNodeId = addGithubInputNodes(githubContext, newNodeId);
                if (githubNodeId) optionIds.push(githubNodeId);
            }
        }

        setTimeout(() => {
            resolveOverlaps(newNodeId, optionIds, { direction: 'below' });
        }, 1);

        return {
            generatorNodeId: newNodeId,
            promptNodeId,
        };
    };

    /**
     * Waits for the Vue Flow graph to render completely.
     * This is useful when you need to ensure that all nodes are initialized before performing actions.
     * @returns A promise that resolves when the graph is rendered.
     */
    const waitForRender = async () => {
        const { onNodesInitialized } = useGraphFlow('main-graph-' + graphId.value);

        return new Promise<void>((resolve) => {
            const unsubscribe = onNodesInitialized(async () => {
                await nextTick();
                resolve();
                unsubscribe.off();
            });
        });
    };

    return {
        addTextToTextInputNodes,
        addFilesPromptInputNodes,
        addGithubInputNodes,
        addParallelizationInputNode,
        updatePromptNodeText,
        isCanvasEmpty,
        createNodeFromVariant,
        waitForRender,
    };
};
