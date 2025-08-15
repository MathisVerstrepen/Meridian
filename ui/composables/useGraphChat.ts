import { useVueFlow } from '@vue-flow/core';

import { DEFAULT_NODE_ID } from '@/constants';
import type { File } from '@/types/files';

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

    const addNodeFromNodeId = (input: string, fromNodeId: string) => {
        const { findNode } = useVueFlow('main-graph-' + graphId.value);

        const inputNode = findNode(fromNodeId);
        if (!inputNode) {
            console.error(`Cannot add nodes: Input node with ID ${fromNodeId} not found.`);
            error(`Failed to add nodes: Input node with ID ${fromNodeId} not found.`, {
                title: 'Error',
            });
            return;
        }

        const inputNodeHeight = getNodeHeight(inputNode.id);
        const inputNodeBaseX = inputNode.position?.x ?? 0;
        const inputNodeBaseY = inputNode.position?.y ?? 0;

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

        const newPromptNode = placeBlock(
            graphId.value,
            'primary-prompt-text',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: -200, y: inputNodeHeight + 25 },
            false,
            {
                prompt: input,
            },
        );

        placeEdge(
            graphId.value,
            inputNode.id,
            newTextToTextNode?.id,
            null,
            'context_' + newTextToTextNode?.id,
        );
        placeEdge(
            graphId.value,
            newPromptNode?.id,
            newTextToTextNode?.id,
            null,
            'prompt_' + newTextToTextNode?.id,
        );

        setTimeout(() => {
            resolveOverlaps(newTextToTextNode?.id, [newPromptNode?.id]);
        }, 1);

        return newTextToTextNode?.id;
    };

    const addNodeFromEmptyGraph = (input: string, forcedTextToTextNodeId: string | null) => {
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

        const newPromptNode = placeBlock(
            graphId.value,
            'primary-prompt-text',
            {
                x: -200,
                y: 25,
            },
            { x: 0, y: 0 },
            false,
            {
                prompt: input,
            },
        );

        placeEdge(
            graphId.value,
            newPromptNode?.id,
            newTextToTextNode?.id,
            null,
            'prompt_' + newTextToTextNode?.id,
        );

        return newTextToTextNode?.id;
    };

    const addTextToTextInputNodes = (
        input: string,
        fromNodeId: string | null,
        forcedTextToTextNodeId: string | null = null,
    ) => {
        if (!fromNodeId || forcedTextToTextNodeId || fromNodeId === DEFAULT_NODE_ID) {
            return addNodeFromEmptyGraph(input, forcedTextToTextNodeId);
        } else {
            return addNodeFromNodeId(input, fromNodeId);
        }
    };

    const addFilesPromptInputNodes = (files: File[], textToTextNodeId: string) => {
        const { findNode } = useVueFlow('main-graph-' + graphId.value);

        const textToTextNode = findNode(textToTextNodeId);
        if (!textToTextNode) {
            console.error(
                `Cannot add file prompt nodes: Text to Text node with ID ${textToTextNodeId} not found.`,
            );
            error(
                `Failed to add file prompt nodes: Text to Text node with ID ${textToTextNodeId} not found.`,
                { title: 'Error' },
            );
            return;
        }

        const newBlock = placeBlock(
            graphId.value,
            'primary-prompt-file',
            {
                x: -450,
                y: textToTextNode.position?.y ?? 0,
            },
            { x: 0, y: 0 },
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

    const addParallelizationInputNode = (input: string, fromNodeId: string | null) => {
        const { findNode } = useVueFlow('main-graph-' + graphId.value);

        const inputNode = findNode(fromNodeId);

        if (!inputNode) {
            console.error(
                `Cannot add parallelization node: Input node with ID ${fromNodeId} not found.`,
            );
            error(
                `Failed to add parallelization node: Input node with ID ${fromNodeId} not found.`,
                {
                    title: 'Error',
                },
            );
            return;
        }

        const inputNodeHeight = getNodeHeight(inputNode.id);
        const inputNodeBaseX = inputNode.position?.x ?? 0;
        const inputNodeBaseY = inputNode.position?.y ?? 0;

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

        const newPromptNode = placeBlock(
            graphId.value,
            'primary-prompt-text',
            {
                x: inputNodeBaseX,
                y: inputNodeBaseY,
            },
            { x: -200, y: inputNodeHeight + 25 },
            false,
            {
                prompt: input,
            },
        );

        placeEdge(
            graphId.value,
            inputNode.id,
            newParallelizationNode?.id,
            null,
            'context_' + newParallelizationNode?.id,
        );
        placeEdge(
            graphId.value,
            newPromptNode?.id,
            newParallelizationNode?.id,
            null,
            'prompt_' + newParallelizationNode?.id,
        );

        setTimeout(() => {
            resolveOverlaps(newParallelizationNode?.id, [newPromptNode?.id]);
        }, 1);

        return newParallelizationNode?.id;
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

    const createNodeFromVariant = (variant: string, fromNodeId: string) => {
        switch (variant) {
            case 'text-to-text-attachement':
                const textToTextNodeId = addTextToTextInputNodes('', fromNodeId);
                if (!textToTextNodeId) {
                    console.error('Failed to create Text to Text node.');
                    error('Failed to create Text to Text node.', { title: 'Error' });
                    return;
                }
                return addFilesPromptInputNodes([], textToTextNodeId);
            case 'text-to-text':
                return addTextToTextInputNodes('', fromNodeId);
            case 'parallelization':
                return addParallelizationInputNode('', fromNodeId);
            default:
                console.warn(`Unknown node variant: ${variant}`);
        }
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
