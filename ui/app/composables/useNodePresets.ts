import {
    type Connection,
    type Edge,
    type Node,
} from '@vue-flow/core';

import { isDuplicateConnection } from '@/composables/useEdgeCompatibility';
import { NodeTypeEnum } from '@/types/enums';
import {
    isNodePresetNodeType,
    type NodePreset,
    type NodePresetNodeType,
} from '@/types/nodePresets';
import { materializeNodePreset, validateNodePresetSettings } from '@/utils/nodePresets';
import type { NodePresetRuntimeDefaults } from '@/utils/nodePresets/contracts';

export interface PlaceableNodePreset {
    preset: NodePreset;
    locked: boolean;
}

export function useNodePresets(graphId: Ref<string>) {
    const settingsStore = useSettingsStore();
    const { user } = useUserSession();
    const { generateId } = useUniqueId();
    const { getBlockByNodeType } = useBlocks();
    const { checkEdgeCompatibility } = useEdgeCompatibility();
    const { resolveOverlaps } = useGraphOverlaps(graphId);
    const { error } = useToast();
    const flowId = 'main-graph-' + graphId.value;
    const { getNodes, addNodes, addEdges, removeNodes, removeEdges } = useGraphFlow(flowId);

    const isFreePlan = computed(() => (user.value)?.plan_type === 'free');
    const placeablePresets = computed<PlaceableNodePreset[]>(() => {
        const settings = settingsStore.nodePresetSettings;
        const collectionValidation = validateNodePresetSettings(settings);
        const invalidIndexes = new Set<number>();
        let collectionInvalid = false;
        for (const issue of collectionValidation.issues) {
            if (issue.path[0] === 'presets' && isRuntimeNumber(issue.path[1])) {
                invalidIndexes.add(issue.path[1]);
            } else {
                collectionInvalid = true;
            }
        }
        if (collectionInvalid) return [];
        return settings.presets.flatMap((preset, index) => {
            if (invalidIndexes.has(index)) return [];
            const validation = validateNodePresetSettings({ schemaVersion: 1, presets: [preset] });
            if (!validation.valid || !validation.value?.presets[0]?.nodes.length) return [];
            const normalized = validation.value.presets[0];
            return [{
                preset: normalized,
                locked:
                    isFreePlan.value &&
                    normalized.nodes.some((node) => node.type === NodeTypeEnum.GITHUB),
            }];
        });
    });

    const dataDefaults = () => {
        const defaults: Partial<Record<NodePresetNodeType, NodePresetRuntimeDefaults>> = {};
        for (const type of Object.values(NodeTypeEnum)) {
            const definition = getBlockByNodeType(type);
            if (!definition) continue;
            if (definition.defaultData && isNodePresetNodeType(type)) {
                Object.assign(defaults, {
                    [type]: structuredClone(toRaw(definition.defaultData)),
                });
            }
        }
        return defaults;
    };

    const edgesAreCompatible = (nodes: Node[], edges: Edge[]): boolean => {
        const accepted: Edge[] = [];
        for (const edge of edges) {
            const connection: Connection = {
                source: edge.source,
                target: edge.target,
                sourceHandle: edge.sourceHandle,
                targetHandle: edge.targetHandle,
            };
            if (
                !checkEdgeCompatibility(connection, nodes, false) ||
                isDuplicateConnection(accepted, connection)
            ) {
                return false;
            }
            accepted.push(edge);
        }
        return true;
    };

    const placePreset = async (
        preset: NodePreset,
        invocationPosition: { x: number; y: number },
    ): Promise<boolean> => {
        const validation = validateNodePresetSettings({ schemaVersion: 1, presets: [preset] });
        const normalized = validation.value?.presets[0];
        if (!validation.valid || !normalized?.nodes.length) {
            error('This preset is empty or invalid.', { title: 'Preset Unavailable' });
            return false;
        }
        if (
            isFreePlan.value &&
            normalized.nodes.some((node) => node.type === NodeTypeEnum.GITHUB)
        ) {
            error('GitHub nodes are available on the Premium plan.', {
                title: 'Premium Feature',
            });
            return false;
        }

        const materialized = materializeNodePreset(normalized, {
            generateId,
            invocationPosition,
            dataDefaults: dataDefaults(),
        });
        if (!materialized.valid || !materialized.value) {
            error('This preset could not be prepared for placement.', {
                title: 'Preset Unavailable',
            });
            return false;
        }

        const placement = materialized.value;
        const nodes = placement.nodes;
        const edges = placement.edges;
        if (!edgesAreCompatible(nodes, edges)) {
            error('This preset contains incompatible connections.', {
                title: 'Preset Unavailable',
            });
            return false;
        }

        const previousSelection = new Map(
            getNodes.value.map((node) => [node.id, !!node.selected] as const),
        );
        const addedNodeIds = new Set(nodes.map((node) => node.id));
        const addedEdgeIds = new Set(edges.map((edge) => edge.id));
        try {
            getNodes.value.forEach((node) => (node.selected = false));
            const groups = nodes.filter((node) => node.type === 'group');
            const childrenAndRoots = nodes.filter((node) => node.type !== 'group');
            if (groups.length) addNodes(groups);
            if (childrenAndRoots.length) addNodes(childrenAndRoots);
            await nextTick();
            if (edges.length) addEdges(edges);
            await nextTick();
            resolveOverlaps(placement.primaryRootId, placement.rootIds.slice(1));
            return true;
        } catch (cause) {
            removeEdges(edges.filter((edge) => addedEdgeIds.has(edge.id)));
            removeNodes(getNodes.value.filter((node) => addedNodeIds.has(node.id)));
            getNodes.value.forEach((node) => {
                node.selected = previousSelection.get(node.id) ?? false;
            });
            console.error('Failed to place node preset:', cause);
            error('Failed to place preset. No nodes were added.', {
                title: 'Preset Placement Error',
            });
            return false;
        }
    };

    return { placeablePresets, placePreset };
}
