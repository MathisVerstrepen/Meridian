import type { Node, Edge } from '@vue-flow/core';
import type { EdgeRequest, NodeRequest } from '@/types/graph';
import { NodeTypeEnum, NodeCategoryEnum } from '@/types/enums';

export const graphMappers = () => {
    const mapNodeRequestToNode = (req: NodeRequest): Node => {
        const node: Node = {
            id: req.id,
            type: req.type,
            position: { x: req.position_x, y: req.position_y },
            style: {
                height: req.height ?? 0,
                width: req.width ?? 0,
            },
            ...(req.data && { data: req.data }),
            ...(req.label && { label: req.label }),
        };
        return node;
    };

    const mapNodeToNodeRequest = (
        node: Node,
        graphId: string,
    ): Omit<
        NodeRequest,
        'graph' | 'outgoing_edges' | 'incoming_edges' | 'created_at' | 'updated_at'
    > => {
        const request = {
            id: node.id,
            graph_id: graphId,
            type: node.type || 'default',
            position_x: node.position.x,
            position_y: node.position.y,
            width:
                typeof node.style === 'object' && node.style !== null && 'width' in node.style
                    ? (node.style).width
                    : '100px',
            height:
                typeof node.style === 'object' && node.style !== null && 'height' in node.style
                    ? (node.style).height
                    : '100px',
            ...(node.data && { data: node.data }),
        };
        return request;
    };

    const mapEdgeRequestToEdge = (req: EdgeRequest): Edge => {
        const edge: Edge = {
            id: req.id,
            source: req.source_node_id,
            target: req.target_node_id,
            animated: req.animated,
            sourceHandle: req.source_handle_id ?? undefined,
            targetHandle: req.target_handle_id ?? undefined,
            label: req.label ?? undefined,
            ...(req.data && { data: req.data }),
            ...(req.style && { style: req.style as Edge['style'] }),
            ...(req.type && { type: req.type }),
        };
        return edge;
    };

    const mapEdgeToEdgeRequest = (
        edge: Edge,
        graphId: string,
    ): Omit<EdgeRequest, 'graph' | 'source_node' | 'target_node' | 'created_at' | 'updated_at'> => {
        const request = {
            id: edge.id,
            graph_id: graphId,
            source_node_id: edge.source,
            target_node_id: edge.target,
            animated: edge.animated ?? false,
            source_handle_id: edge.sourceHandle ?? null,
            target_handle_id: edge.targetHandle ?? null,
            label: typeof edge.label === 'string' ? edge.label : null,
            type: edge.type ?? null,
            ...(edge.data && { data: edge.data }),
            ...(edge.style && { style: edge.style as Edge['style'] }),
        };
        return request;
    };

    const nodeTypeEnumToHandleCategory = (
        type: NodeTypeEnum | string | undefined,
    ): 'prompt' | 'attachment' | 'context' => {
        switch (type) {
            case NodeTypeEnum.PROMPT:
                return 'prompt';
            case NodeTypeEnum.FILE_PROMPT:
                return 'attachment';
            case NodeTypeEnum.TEXT_TO_TEXT:
                return 'context';
            case NodeTypeEnum.PARALLELIZATION:
                return 'context';
            case NodeTypeEnum.GITHUB:
                return 'attachment';
            default:
                console.warn('Unknown node type for handle category mapping:', type);
                return 'context';
        }
    };

    const mapHandleIdToNodeType = (handleId: string | undefined): NodeCategoryEnum => {
        switch (handleId?.split('_')[0]) {
            case 'prompt':
                return NodeCategoryEnum.PROMPT;
            case 'attachment':
                return NodeCategoryEnum.ATTACHMENT;
            case 'context':
                return NodeCategoryEnum.CONTEXT;
            default:
                return NodeCategoryEnum.CONTEXT;
        }
    };

    const mapNodeTypeToColor = (type: NodeCategoryEnum): string => {
        switch (type) {
            case NodeCategoryEnum.PROMPT:
                return 'var(--color-node-cat-prompt)';
            case NodeCategoryEnum.ATTACHMENT:
                return 'var(--color-node-cat-attachment)';
            case NodeCategoryEnum.CONTEXT:
                return 'var(--color-node-cat-context)';
            default:
                return '#808080';
        }
    };

    return {
        mapNodeRequestToNode,
        mapNodeToNodeRequest,
        mapEdgeRequestToEdge,
        mapEdgeToEdgeRequest,
        nodeTypeEnumToHandleCategory,
        mapHandleIdToNodeType,
        mapNodeTypeToColor,
    };
};
