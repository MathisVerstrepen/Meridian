import { MarkerType, useVueFlow } from '@vue-flow/core';
import type { Node, Edge } from '@vue-flow/core';

export const useGraphAppend = () => {
    const route = useRoute();
    const graphId = computed(() => route.params.id as string);

    const chatStore = useChatStore();
    const { fromNodeId } = storeToRefs(chatStore);
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

    const addTextToTextInputNodes = (input: string) => {
        const { findNode, addEdges, addNodes } = useVueFlow(
            'main-graph-' + graphId.value,
        );

        if (!fromNodeId.value) {
            console.error('Cannot add nodes: fromNodeId is not set.');
            return;
        }

        const inputNode = findNode(fromNodeId.value);

        if (!inputNode) {
            console.error(
                `Cannot add nodes: Input node with ID ${fromNodeId.value} not found.`,
            );
            return;
        }

        const verticalDistance = 250;
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
                model: inputNode.data?.model,
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
    };

    return {
        addTextToTextInputNodes,
    };
};
