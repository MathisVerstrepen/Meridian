import { useVueFlow } from '@vue-flow/core';

import { DEFAULT_NODE_ID } from '@/constants';
import { NodeTypeEnum } from '@/types/enums';

export const useGraphChat = () => {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const chatStore = useChatStore();
    const settingsStore = useSettingsStore();
    const { error } = useToast();
    const { placeBlock, placeEdge } = useGraphActions();

    const { currentModel } = storeToRefs(chatStore);
    const { blockParallelizationSettings } = storeToRefs(settingsStore);

    const { generateId } = useUniqueId();
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
        const { findNode } = useVueFlow('main-graph-' + graphId.value);

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

    const addTextToTextFromNodeId = (input: string, fromNodeId: string) => {
        const {
            x: inputNodeBaseX,
            y: inputNodeBaseY,
            height: inputNodeHeight,
        } = getNodeRect(fromNodeId);

        const newTextToTextNode = placeBlock(
            graphId.value,
            'primary-model-text-to-text',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: 0, y: inputNodeHeight + 350 },
            false,
            {
                model: currentModel.value,
            },
        );

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
        const newTextToTextNode = placeBlock(
            graphId.value,
            'primary-model-text-to-text',
            {
                x: 0,
                y: 350,
            },
            { x: 0, y: 0 },
            false,
            {
                model: currentModel.value,
            },
            forcedTextToTextNodeId,
        );

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

        const newPromptNode = placeBlock(
            graphId.value,
            'primary-prompt-text',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: -200, y: -300 },
            false,
            {
                prompt: input,
            },
        );

        placeEdge(graphId.value, newPromptNode?.id, fromNodeId, null, 'prompt_' + fromNodeId);

        return newPromptNode?.id;
    };

    const addGithubInputNodes = (fromNodeId: string) => {
        const { x: inputNodeBaseX, y: inputNodeBaseY, height: _ } = getNodeRect(fromNodeId);

        const newGithubNode = placeBlock(
            graphId.value,
            'primary-github-context',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: -600, y: 0 },
            false,
        );

        placeEdge(graphId.value, newGithubNode?.id, fromNodeId, null, 'attachment_' + fromNodeId);

        return newGithubNode?.id;
    };

    const addFilesPromptInputNodes = (files: FileSystemObject[], textToTextNodeId: string) => {
        const {
            x: inputNodeBaseX,
            y: inputNodeBaseY,
            height: inputNodeHeight,
        } = getNodeRect(textToTextNodeId);

        console.log(inputNodeBaseX, inputNodeBaseY, inputNodeHeight);

        const newBlock = placeBlock(
            graphId.value,
            'primary-prompt-file',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: -650, y: 0 },
            false,
            {
                files: files,
            },
        );

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
        const newParallelizationNode = placeBlock(
            graphId.value,
            'primary-model-parallelization',
            {
                x: 0,
                y: 350,
            },
            { x: 0, y: 0 },
            false,
            {
                models:
                    blockParallelizationSettings.value?.models.map(({ model }) => ({
                        model: model,
                        reply: '',
                        id: generateId(),
                    })) ?? [],
                aggregator: {
                    prompt: blockParallelizationSettings.value.aggregator.prompt,
                    model: blockParallelizationSettings.value.aggregator.model,
                    reply: '',
                    usageData: null,
                },
            },
            forcedParallelizationNodeId,
        );

        return newParallelizationNode?.id;
    };

    const addRoutingFromEmptyGraph = (input: string, forcedRoutingNodeId: string | null) => {
        const newRoutingNode = placeBlock(
            graphId.value,
            'primary-model-routing',
            {
                x: 0,
                y: 350,
            },
            { x: 0, y: 0 },
            false,
            {},
            forcedRoutingNodeId,
        );

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

        const {
            x: inputNodeBaseX,
            y: inputNodeBaseY,
            height: inputNodeHeight,
        } = getNodeRect(fromNodeId);

        const newParallelizationNode = placeBlock(
            graphId.value,
            'primary-model-parallelization',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: 0, y: inputNodeHeight + 350 },
            false,
            {
                models:
                    blockParallelizationSettings.value?.models.map(({ model }) => ({
                        model: model,
                        reply: '',
                        id: generateId(),
                    })) ?? [],
                aggregator: {
                    prompt: blockParallelizationSettings.value.aggregator.prompt,
                    model: blockParallelizationSettings.value.aggregator.model,
                    reply: '',
                    usageData: null,
                },
            },
        );

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

        const {
            x: inputNodeBaseX,
            y: inputNodeBaseY,
            height: inputNodeHeight,
        } = getNodeRect(fromNodeId);

        const newRoutingNode = placeBlock(
            graphId.value,
            'primary-model-routing',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: 0, y: inputNodeHeight + 350 },
            false,
            {},
        );

        placeEdge(
            graphId.value,
            fromNodeId,
            newRoutingNode?.id,
            null,
            'context_' + newRoutingNode?.id,
        );

        return newRoutingNode?.id;
    };

    const updateNodeModel = (nodeId: string, model: string) => {
        const { updateNode, findNode } = useVueFlow('main-graph-' + graphId.value);
        const node = findNode(nodeId);
        if (node) {
            node.data.model = model;
            updateNode(nodeId, {
                data: {
                    ...node.data,
                    model: model,
                },
            });
        } else {
            console.error(`Node with ID ${nodeId} not found.`);
            error(`Node with ID ${nodeId} not found.`, { title: 'Error' });
        }
    };

    const updatePromptNodeText = (nodeId: string, text: string) => {
        const { updateNode, findNode } = useVueFlow('main-graph-' + graphId.value);
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
        const { nodes } = useVueFlow('main-graph-' + graphId.value);
        return nodes.value.length === 0;
    };

    const createNodeFromVariant = (
        generatorNode: NodeTypeEnum,
        fromNodeId: string,
        options: NodeTypeEnum[] | undefined = undefined,
        inputText: string = '',
        forcedNodeId: string | null = null,
    ) => {
        let newNodeId: string | undefined;
        const optionIds: string[] = [];

        switch (generatorNode) {
            case NodeTypeEnum.TEXT_TO_TEXT:
                newNodeId = addTextToTextInputNodes(inputText, fromNodeId, forcedNodeId);
                break;
            case NodeTypeEnum.PARALLELIZATION:
                newNodeId = addParallelizationInputNode(inputText, fromNodeId, forcedNodeId);
                break;
            case NodeTypeEnum.ROUTING:
                newNodeId = addRoutingInputNode(inputText, fromNodeId, forcedNodeId);
                break;
            default:
                console.warn(`Unknown node variant: ${generatorNode}`);
                break;
        }

        for (const option of options ?? []) {
            if (option === NodeTypeEnum.FILE_PROMPT && newNodeId) {
                const optionId = addFilesPromptInputNodes([], newNodeId);
                if (optionId) optionIds.push(optionId);
            } else if (option === NodeTypeEnum.PROMPT && newNodeId) {
                const optionId = addPromptFromNodeId(inputText, newNodeId);
                if (optionId) optionIds.push(optionId);
            } else if (option === NodeTypeEnum.GITHUB && newNodeId) {
                const optionId = addGithubInputNodes(newNodeId);
                if (optionId) optionIds.push(optionId);
            }
        }

        setTimeout(() => {
            resolveOverlaps(newNodeId, optionIds);
        }, 1);

        return newNodeId;
    };

    /**
     * Waits for the Vue Flow graph to render completely.
     * This is useful when you need to ensure that all nodes are initialized before performing actions.
     * @returns A promise that resolves when the graph is rendered.
     */
    const waitForRender = async () => {
        const { onNodesInitialized, fitView } = useVueFlow('main-graph-' + graphId.value);

        return new Promise<void>((resolve) => {
            const unsubscribe = onNodesInitialized(async () => {
                await nextTick();
                fitView({
                    maxZoom: 1,
                    minZoom: 0.4,
                    padding: 0.2,
                });
                resolve();
                unsubscribe.off();
            });
        });
    };

    return {
        addTextToTextInputNodes,
        addFilesPromptInputNodes,
        addParallelizationInputNode,
        updateNodeModel,
        updatePromptNodeText,
        isCanvasEmpty,
        createNodeFromVariant,
        waitForRender,
    };
};
