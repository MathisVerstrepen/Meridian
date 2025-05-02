import { MarkerType, useVueFlow } from '@vue-flow/core';
import type { Node, Edge } from '@vue-flow/core';

export const useGraphChat = () => {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const chatStore = useChatStore();
    const { fromNodeId, currentModel } = storeToRefs(chatStore);
    const { generateId } = useUniqueNodeId();

    const getNodeHeight = (nodeId: string) => {
        const element = document.querySelector(`[data-id="${nodeId}"]`);
        if (element) {
            const style = window.getComputedStyle(element);
            const height = parseFloat(style.height);
            return height;
        }

        return 0;
    };

    const addNodeFromNodeId = (input: string) => {
        const { findNode, addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

        const inputNode = findNode(fromNodeId.value);

        if (!inputNode) {
            console.error(`Cannot add nodes: Input node with ID ${fromNodeId.value} not found.`);
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
            type: 'textToText',
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
            type: 'prompt',
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
            markerEnd: {
                type: MarkerType.ArrowClosed,
                height: 20,
                width: 20,
            },
        };
        const edge2: Edge = {
            id: `e-${promptNodeId}-${textToTextNodeId}`,
            source: promptNodeId,
            target: textToTextNodeId,
            targetHandle: 'prompt_' + textToTextNodeId,
            markerEnd: {
                type: MarkerType.ArrowClosed,
                height: 20,
                width: 20,
            },
        };

        addNodes([newTextToTextNode, newPromptNode]);
        addEdges([edge1, edge2]);

        return textToTextNodeId;
    };

    const addNodeFromEmptyGraph = (input: string) => {
        const { addEdges, addNodes } = useVueFlow('main-graph-' + graphId.value);

        const verticalDistance = 350;
        const horizontalDistance = 200;
        const verticalOffsetForPrompt = 25;

        const textToTextNodeId = generateId();
        const promptNodeId = generateId();

        const newTextToTextNode: Node = {
            id: textToTextNodeId,
            type: 'textToText',
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
            type: 'prompt',
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
            markerEnd: {
                type: MarkerType.ArrowClosed,
                height: 20,
                width: 20,
            },
        };

        addNodes([newTextToTextNode, newPromptNode]);
        addEdges([edge1]);

        return textToTextNodeId;
    };

    const addTextToTextInputNodes = (input: string) => {
        if (!fromNodeId.value) {
            return addNodeFromEmptyGraph(input);
        } else {
            return addNodeFromNodeId(input);
        }
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
        }
    };

    return {
        addTextToTextInputNodes,
        updateNodeModel,
    };
};
