import { type GraphNode } from '@vue-flow/core';
import type { ComputedRef, Ref } from 'vue';

import type { NodeWithDimensions } from '@/types/graph';
import {
    calculateGraphAutoLayout,
    type GraphAutoLayoutNode,
} from '@/utils/graphAutoLayout';

interface UseGraphAutoLayoutOptions {
    graphId: Ref<string> | ComputedRef<string>;
    fitGraph: () => RuntimeValue | Promise<RuntimeValue>;
    calculateLayout?: typeof calculateGraphAutoLayout;
}

const positiveNumber = (value: RuntimeValue): number | undefined =>
    isRuntimeNumber(value) && Number.isFinite(value) && value > 0 ? value : undefined;

const styleDimension = (style: GraphNode['style'], key: 'width' | 'height'): number | undefined => {
    if (!style || !isRuntimeObject(style) || Array.isArray(style)) return undefined;
    const value = Object.entries(style).find(([entryKey]) => entryKey === key)?.[1];
    if (isRuntimeNumber(value)) return positiveNumber(value);
    if (!isRuntimeString(value)) return undefined;
    return positiveNumber(Number.parseFloat(value));
};

export const useGraphAutoLayout = (options: UseGraphAutoLayoutOptions) => {
    const { getNodes, getEdges, setNodes } = useGraphFlow('main-graph-' + options.graphId.value);
    const { getBlockByNodeType } = useBlocks();
    const { saveGraph } = useCanvasSaveStore();

    const resolveDimension = (
        node: NodeWithDimensions,
        key: 'width' | 'height',
    ): number =>
        positiveNumber(node.dimensions?.[key]) ??
        positiveNumber(node[key]) ??
        styleDimension(node.style, key) ??
        positiveNumber(getBlockByNodeType(nodeTypeOrUndefined(node.type))?.minSize[key]) ??
        100;

    const autoLayoutGraph = async (): Promise<boolean> => {
        const nodes = getNodes.value;
        if (!nodes.length) return false;

        const layoutNodes: GraphAutoLayoutNode[] = nodes.map((node) => ({
            id: node.id,
            position: { ...node.position },
            width: resolveDimension(node, 'width'),
            height: resolveDimension(node, 'height'),
            type: node.type,
            parentNode: node.parentNode,
        }));
        const positions = (options.calculateLayout ?? calculateGraphAutoLayout)(
            layoutNodes,
            getEdges.value.map((edge) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                sourceHandle: edge.sourceHandle,
                targetHandle: edge.targetHandle,
            })),
        );
        setNodes(
            nodes.map((node) => {
                const position = positions.get(node.id);
                return position ? { ...node, position } : node;
            }),
        );
        await nextTick();
        await options.fitGraph();
        await saveGraph();
        return true;
    };

    return { autoLayoutGraph };
};
