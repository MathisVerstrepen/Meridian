import { useVueFlow } from '@vue-flow/core';
import type { Node, Edge } from '@vue-flow/core';

import { DEFAULT_NODE_ID } from '@/constants';
import { NodeTypeEnum } from '@/types/enums';
import type { File } from '@/types/files';
import type { DataFilePrompt, NodeWithDimensions } from '@/types/graph';

export const useGraphChat = () => {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const chatStore = useChatStore();
    const settingsStore = useSettingsStore();
    const { getBlockById } = useBlocks();
    const { error } = useToast();

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
        const { findNode, addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

        const inputNode = findNode(fromNodeId);

        if (!inputNode) {
            console.error(`Cannot add nodes: Input node with ID ${fromNodeId} not found.`);
            error(`Failed to add nodes: Input node with ID ${fromNodeId} not found.`, {
                title: 'Error',
            });
            return;
        }

        const verticalDistance = 350;
        const horizontalDistance = 200;
        const verticalOffsetForPrompt = 25;

        const inputNodeHeight = getNodeHeight(inputNode.id);
        const inputNodeBaseX = inputNode.position?.x ?? 0;
        const inputNodeBaseY = inputNode.position?.y ?? 0;

        const textToTextNodeId = generateId();
        const promptNodeId = generateId();

        const newTextToTextNode: Node = {
            id: textToTextNodeId,
            type: NodeTypeEnum.TEXT_TO_TEXT,
            position: {
                x: inputNodeBaseX,
                y: inputNodeBaseY + inputNodeHeight + verticalDistance,
            },
            data: {
                model: currentModel.value,
                reply: '',
            },
        };

        const newPromptNode: Node = {
            id: promptNodeId,
            type: NodeTypeEnum.PROMPT,
            position: {
                x: inputNodeBaseX - horizontalDistance,
                y: inputNodeBaseY + inputNodeHeight + verticalOffsetForPrompt,
            },
            data: {
                prompt: input,
            },
        };

        const edge1: Edge = {
            id: `e-${inputNode.id}-${textToTextNodeId}`,
            source: inputNode.id,
            target: textToTextNodeId,
            targetHandle: 'context_' + textToTextNodeId,
            type: 'custom',
        };
        const edge2: Edge = {
            id: `e-${promptNodeId}-${textToTextNodeId}`,
            source: promptNodeId,
            target: textToTextNodeId,
            targetHandle: 'prompt_' + textToTextNodeId,
            type: 'custom',
        };

        addNodes([newTextToTextNode, newPromptNode]);
        addEdges([edge1, edge2]);

        setTimeout(() => {
            resolveOverlaps(textToTextNodeId, [promptNodeId]);
        }, 1);

        return textToTextNodeId;
    };

    const addNodeFromEmptyGraph = (input: string, forcedTextToTextNodeId: string | null) => {
        const { addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

        const verticalDistance = 350;
        const horizontalDistance = 200;
        const verticalOffsetForPrompt = 25;

        const textToTextNodeId = forcedTextToTextNodeId || generateId();
        const promptNodeId = generateId();

        const newTextToTextNode: Node = {
            id: textToTextNodeId,
            type: NodeTypeEnum.TEXT_TO_TEXT,
            position: {
                x: 0,
                y: verticalDistance,
            },
            data: {
                model: currentModel.value,
                reply: '',
            },
        };

        const newPromptNode: Node = {
            id: promptNodeId,
            type: NodeTypeEnum.PROMPT,
            position: {
                x: -horizontalDistance,
                y: verticalOffsetForPrompt,
            },
            data: {
                prompt: input,
            },
        };

        const edge1: Edge = {
            id: `e-${promptNodeId}-${textToTextNodeId}`,
            source: promptNodeId,
            target: textToTextNodeId,
            targetHandle: 'prompt_' + textToTextNodeId,
            type: 'custom',
        };

        addNodes([newTextToTextNode, newPromptNode]);
        addEdges([edge1]);

        return textToTextNodeId;
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
        const { findNode, addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

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

        const horizontalDistance = 450;
        const textToTextNodeY = textToTextNode.position?.y ?? 0;

        const filePromptNodeId = generateId();
        const fileNodeDefinition = getBlockById('primary-prompt-file');

        const newFilePromptNode: NodeWithDimensions = {
            id: filePromptNodeId,
            type: NodeTypeEnum.FILE_PROMPT,
            position: {
                x: -horizontalDistance,
                y: textToTextNodeY,
            },
            data: { files: files } as DataFilePrompt,
        };

        if (fileNodeDefinition?.forcedInitialDimensions) {
            newFilePromptNode.width = fileNodeDefinition.minSize.width;
            newFilePromptNode.height = fileNodeDefinition.minSize.height;
        }

        const edge1: Edge = {
            id: `e-${filePromptNodeId}-${textToTextNodeId}`,
            source: filePromptNodeId,
            target: textToTextNodeId,
            targetHandle: 'attachment_' + textToTextNodeId,
            type: 'custom',
        };

        addNodes([newFilePromptNode]);
        addEdges([edge1]);

        return filePromptNodeId;
    };

    const addParallelizationInputNode = (input: string, fromNodeId: string | null) => {
        const { findNode, addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

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

        const verticalDistance = 350;
        const horizontalDistance = 200;
        const verticalOffsetForPrompt = 25;

        const inputNodeHeight = getNodeHeight(inputNode.id);
        const inputNodeBaseX = inputNode.position?.x ?? 0;
        const inputNodeBaseY = inputNode.position?.y ?? 0;

        const parallelizationNodeId = generateId();
        const promptNodeId = generateId();

        const newParallelizationNode: Node = {
            id: parallelizationNodeId,
            type: NodeTypeEnum.PARALLELIZATION,
            position: {
                x: inputNodeBaseX,
                y: inputNodeBaseY + inputNodeHeight + verticalDistance,
            },
            data: {
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
        };

        const parallelizationNodeDefinition = getBlockById('primary-model-parallelization');
        if (parallelizationNodeDefinition?.forcedInitialDimensions) {
            newParallelizationNode.width = parallelizationNodeDefinition.minSize.width;
            newParallelizationNode.height = parallelizationNodeDefinition.minSize.height;
        }

        const newPromptNode: Node = {
            id: promptNodeId,
            type: NodeTypeEnum.PROMPT,
            position: {
                x: inputNodeBaseX - horizontalDistance,
                y: inputNodeBaseY + inputNodeHeight + verticalOffsetForPrompt,
            },
            data: {
                prompt: input,
            },
        };

        const edge1: Edge = {
            id: `e-${inputNode.id}-${parallelizationNodeId}`,
            source: inputNode.id,
            target: parallelizationNodeId,
            targetHandle: 'context_' + parallelizationNodeId,
            type: 'custom',
        };
        const edge2: Edge = {
            id: `e-${promptNodeId}-${parallelizationNodeId}`,
            source: promptNodeId,
            target: parallelizationNodeId,
            targetHandle: 'prompt_' + parallelizationNodeId,
            type: 'custom',
        };

        addNodes([newParallelizationNode, newPromptNode]);
        addEdges([edge1, edge2]);

        setTimeout(() => {
            resolveOverlaps(parallelizationNodeId, [promptNodeId]);
        }, 1);

        return parallelizationNodeId;
    };

    const updateNodeModel = (nodeId: string, model: string) => {
        const { updateNode } = useVueFlow('main-graph-' + graphId.value);
        const node = useVueFlow('main-graph-' + graphId.value).findNode(nodeId);
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
        const { updateNode } = useVueFlow('main-graph-' + graphId.value);
        const node = useVueFlow('main-graph-' + graphId.value).findNode(nodeId);
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
