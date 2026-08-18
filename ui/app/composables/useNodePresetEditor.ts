import { type Connection, type Edge, type GraphNode, type Node } from '@vue-flow/core';

import { isDuplicateConnection } from '@/composables/useEdgeCompatibility';
import {
    MAX_PRESET_EDGES,
    MAX_PRESET_NODES,
    NODE_PRESET_EDGE_TYPE_RULES,
    type NodePreset,
    type NodePresetEdgeCategory,
    type NodePresetNodeType,
} from '@/types/nodePresets';
import type { NodePresetValidationIssue } from '@/utils/nodePresets';
import { serializeNodePreset } from '@/utils/nodePresets';

interface UseNodePresetEditorOptions {
    preset: Ref<NodePreset>;
    flowId: string;
}

const cloneRecord = <Value extends object>(value: Value): Value => structuredClone(toRaw(value));

const renderedDimension = (
    node: GraphNode,
    dimension: 'width' | 'height',
): number => {
    const rendered = node.dimensions[dimension];
    if (isRuntimeNumber(rendered) && Number.isFinite(rendered)) return rendered;
    const configured = node[dimension];
    return isRuntimeNumber(configured) && Number.isFinite(configured) ? configured : 0;
};

const edgeCategory = (connection: Connection): NodePresetEdgeCategory | null => {
    const category = connection.targetHandle?.split('_')[0];
    return category === 'prompt' || category === 'context' || category === 'attachment'
        ? category
        : null;
};

export function useNodePresetEditor(options: UseNodePresetEditorOptions) {
    const settingsStore = useSettingsStore();
    const { generateId } = useUniqueId();
    const { getBlockById, getBlockByNodeType } = useBlocks();
    const { checkEdgeCompatibility } = useEdgeCompatibility();
    const { handleContextMergerPlacement } = useGraphActions();
    const {
        getNodes,
        getEdges,
        setNodes,
        setEdges,
        addNodes,
        addEdges,
        removeNodes,
        removeEdges,
        fitView,
    } = useGraphFlow(options.flowId);

    const isHydrating = ref(true);
    const validationIssues = ref<NodePresetValidationIssue[]>([]);
    const actionMessage = ref('');

    const runtimeData = (
        type: NodePresetNodeType,
        configured: NodePreset['nodes'][number]['data'],
    ) => {
        const runtimeType = nodeTypeOrUndefined(type);
        const definition = runtimeType ? getBlockByNodeType(runtimeType) : undefined;
        const merged = { ...definition?.defaultData, ...cloneRecord(configured) };
        if (type === 'textToText') {
            return { ...merged, reply: '', usageData: null, activeGenerationHistoryId: undefined };
        }
        if (type === 'parallelization' && 'models' in configured && 'aggregator' in configured) {
            const data = configured;
            const models = data.models;
            const aggregator = data.aggregator;
            return {
                ...merged,
                models: models.map((model) => ({
                    ...model,
                    id: generateId(),
                    reply: '',
                    usageData: null,
                })),
                aggregator: { ...aggregator, reply: '', usageData: null },
                activeGenerationHistoryId: undefined,
            };
        }
        if (type === 'routing') {
            return {
                ...merged,
                model: '',
                selectedRouteId: '',
                reply: '',
                usageData: null,
                activeGenerationHistoryId: undefined,
            };
        }
        if (type === 'github' && 'files' in configured) {
            const data = configured;
            return {
                ...merged,
                files: Array.isArray(data.files)
                    ? data.files.map((file) =>
                          isJsonObject(file) ? { ...file, children: [] } : { children: [] },
                      )
                    : [],
            };
        }
        if (type === 'contextMerger') return { ...merged, branch_summaries: {} };
        return merged;
    };

    const hydrate = async () => {
        isHydrating.value = true;
        const preset = options.preset.value;
        const nodes = preset.nodes
            .map((node): Node => {
                const hydratedNode = {
                    id: node.id,
                    type: node.type,
                    position: { ...node.position },
                    width: node.width,
                    height: node.height,
                    style: { width: `${node.width}px`, height: `${node.height}px` },
                    data: runtimeData(node.type, node.data),
                };
                if (node.parentId) {
                    Object.assign(hydratedNode, { parentNode: node.parentId, expandParent: true });
                }
                if (node.type === 'group') Object.assign(hydratedNode, { zIndex: -1 });
                return hydratedNode;
            })
            .sort((left, right) => Number(right.type === 'group') - Number(left.type === 'group'));
        const edges: Edge[] = preset.edges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            sourceHandle: `${edge.category}_${edge.source}`,
            targetHandle: `${edge.category}_${edge.target}`,
            type: 'custom',
        }));
        setNodes(nodes);
        setEdges(edges);
        await nextTick();
        isHydrating.value = false;
        if (nodes.length > 0) await fitView({ maxZoom: 0.85, minZoom: 0.15, padding: 0.2 });
    };

    const flush = (): boolean => {
        if (isHydrating.value) return true;
        const result = serializeNodePreset({
            id: options.preset.value.id,
            name: options.preset.value.name,
            accentColor: options.preset.value.accentColor,
            nodes: getNodes.value,
            edges: getEdges.value,
        });
        validationIssues.value = result.issues;
        settingsStore.setNodePresetEditorIssues(result.issues);
        if (!result.valid || !result.value) {
            settingsStore.markSettingsChanged();
            return false;
        }

        const presets = settingsStore.nodePresetSettings.presets;
        const index = presets.findIndex((preset) => preset.id === result.value?.id);
        if (index >= 0 && JSON.stringify(presets[index]) !== JSON.stringify(result.value)) {
            presets[index] = result.value;
        }
        return true;
    };

    const rejectAction = (message: string): false => {
        actionMessage.value = message;
        return false;
    };

    const addBlock = (blockId: string, isFreePlan: boolean): boolean => {
        const definition = getBlockById(blockId);
        if (!definition) return rejectAction('This block is not available.');
        if (definition.nodeType === 'github' && isFreePlan) {
            return rejectAction('GitHub blocks require Premium. Existing GitHub blocks remain editable.');
        }
        if (getNodes.value.length >= MAX_PRESET_NODES) {
            return rejectAction(`Presets support at most ${MAX_PRESET_NODES} nodes.`);
        }
        const id = generateId();
        const offset = getNodes.value.length * 28;
        addNodes({
            id,
            type: definition.nodeType,
            position: { x: 80 + offset, y: 80 + offset },
            width: definition.minSize.width,
            height: definition.minSize.height,
            style: {
                width: `${definition.minSize.width}px`,
                height: `${definition.minSize.height}px`,
            },
            data: cloneRecord(definition.defaultData),
        });
        actionMessage.value = '';
        return true;
    };

    const canConnect = (connection: Connection): boolean => {
        const category = edgeCategory(connection);
        const source = getNodes.value.find((node) => node.id === connection.source);
        const target = getNodes.value.find((node) => node.id === connection.target);
        if (!category || !source || !target || source.id === target.id) return false;
        const rules = NODE_PRESET_EDGE_TYPE_RULES[category];
        return (
            rules.sources.some((type) => type === source.type) &&
            rules.targets.some((type) => type === target.type) &&
            checkEdgeCompatibility(connection, getNodes.value, false) &&
            !isDuplicateConnection(getEdges.value, connection)
        );
    };

    const connect = (connection: Connection): boolean => {
        const category = edgeCategory(connection);
        if (!category || !canConnect(connection)) {
            return rejectAction('These handles cannot be connected.');
        }
        if (category === 'prompt' && getEdges.value.some((edge) => edge.target === connection.target && edge.targetHandle?.startsWith('prompt_'))) {
            return rejectAction('A node can have only one incoming prompt edge.');
        }
        const contextIntoGenerator =
            category === 'context' &&
            ['textToText', 'parallelization', 'routing'].includes(
                getNodes.value.find((node) => node.id === connection.target)?.type ?? '',
            );
        const existingContext = getEdges.value.filter(
            (edge) => edge.target === connection.target && edge.targetHandle === connection.targetHandle,
        ).length;
        const needsMerger = contextIntoGenerator && existingContext >= 1;
        const edgeIncrease = needsMerger ? 2 : 1;
        if (getEdges.value.length + edgeIncrease > MAX_PRESET_EDGES) {
            return rejectAction(`Presets support at most ${MAX_PRESET_EDGES} edges.`);
        }
        if (needsMerger && getNodes.value.length >= MAX_PRESET_NODES) {
            return rejectAction('A Context Merger is required, but the node limit has been reached.');
        }
        const id = generateId();
        addEdges({ ...connection, id, type: 'custom' });
        if (needsMerger) {
            handleContextMergerPlacement(connection, options.preset.value.id, id, options.flowId);
        }
        actionMessage.value = '';
        return true;
    };

    const removeEdge = (edgeId: string) => removeEdges([edgeId]);

    const removeNode = (nodeId: string) => {
        const node = getNodes.value.find((entry) => entry.id === nodeId);
        if (!node) return;
        if (node.type === 'group') {
            deleteGroup(nodeId);
            return;
        }
        const parentId = node.parentNode;
        removeEdges(getEdges.value.filter((edge) => edge.source === nodeId || edge.target === nodeId));
        removeNodes([node]);
        if (parentId && getNodes.value.filter((entry) => entry.parentNode === parentId).length === 1) {
            const parent = getNodes.value.find((entry) => entry.id === parentId);
            if (parent) removeNodes([parent]);
        }
    };

    const createGroup = async (): Promise<boolean> => {
        const selected = getNodes.value.filter(
            (node) => node.selected && node.type !== 'group' && !node.parentNode,
        );
        if (selected.length === 0) return rejectAction('Select one or more ungrouped blocks first.');
        if (getNodes.value.length >= MAX_PRESET_NODES) {
            return rejectAction(`Presets support at most ${MAX_PRESET_NODES} nodes.`);
        }
        const padding = 40;
        const minX = Math.min(...selected.map((node) => node.position.x));
        const minY = Math.min(...selected.map((node) => node.position.y));
        const maxX = Math.max(
            ...selected.map((node) => node.position.x + renderedDimension(node, 'width')),
        );
        const maxY = Math.max(
            ...selected.map((node) => node.position.y + renderedDimension(node, 'height')),
        );
        const groupId = generateId();
        const groupPosition = { x: minX - padding, y: minY - padding };
        addNodes({
            id: groupId,
            type: 'group',
            position: groupPosition,
            style: { width: `${maxX - minX + padding * 2}px`, height: `${maxY - minY + padding * 2}px` },
            data: { title: 'New Group', comment: 'Add a description...', colorIndex: 0 },
            zIndex: -1,
        });
        await nextTick();
        setNodes(
            getNodes.value.map((node) =>
                selected.some((entry) => entry.id === node.id)
                    ? {
                          ...node,
                          parentNode: groupId,
                          expandParent: true,
                          position: {
                              x: node.position.x - groupPosition.x,
                              y: node.position.y - groupPosition.y,
                          },
                      }
                    : node,
            ),
        );
        actionMessage.value = '';
        return true;
    };

    const unlinkNode = (nodeId: string) => {
        const node = getNodes.value.find((entry) => entry.id === nodeId);
        if (!node?.parentNode) return;
        const parent = getNodes.value.find((entry) => entry.id === node.parentNode);
        const parentId = node.parentNode;
        const lastChild = getNodes.value.filter((entry) => entry.parentNode === parentId).length === 1;
        setNodes(
            getNodes.value
                .filter((entry) => !lastChild || entry.id !== parentId)
                .map((entry) =>
                    entry.id === nodeId
                        ? {
                              ...entry,
                              parentNode: undefined,
                              expandParent: false,
                              position: {
                                  x: entry.position.x + (parent?.position.x ?? 0),
                                  y: entry.position.y + (parent?.position.y ?? 0),
                              },
                          }
                        : entry,
                ),
        );
    };

    function deleteGroup(groupId: string) {
        const group = getNodes.value.find((node) => node.id === groupId && node.type === 'group');
        if (!group) return;
        setNodes(
            getNodes.value
                .filter((node) => node.id !== groupId)
                .map((node) =>
                    node.parentNode === groupId
                        ? {
                              ...node,
                              parentNode: undefined,
                              expandParent: false,
                              position: {
                                  x: node.position.x + group.position.x,
                                  y: node.position.y + group.position.y,
                              },
                          }
                        : node,
                ),
        );
    }

    watch([getNodes, getEdges], () => flush(), { deep: true, flush: 'post' });
    onMounted(hydrate);
    onBeforeUnmount(() => settingsStore.setNodePresetEditorIssues([]));

    return {
        getNodes,
        getEdges,
        validationIssues,
        actionMessage,
        hydrate,
        flush,
        addBlock,
        canConnect,
        connect,
        removeEdge,
        removeNode,
        createGroup,
        unlinkNode,
        deleteGroup,
        fit: () => fitView({ maxZoom: 0.85, minZoom: 0.15, padding: 0.2 }),
    };
}
