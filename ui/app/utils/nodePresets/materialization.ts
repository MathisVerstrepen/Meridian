import { nodeGroupColorFromIndex } from '@/constants/nodeGroup';
import {
    NODE_PRESET_SCHEMA_VERSION,
    type NodePreset,
    type NodePresetData,
    type NodePresetNodeType,
} from '@/types/nodePresets';
import type {
    MaterializedNodePreset,
    MaterializedPresetEdge,
    MaterializedPresetNode,
    MaterializeNodePresetOptions,
    NodePresetRuntimeDefaults,
    NodePresetResult,
    NodePresetUnknownRecord,
} from '@/utils/nodePresets/contracts';
import { isRecord } from '@/utils/nodePresets/validationHelpers';
import { validateNodePresetSettings } from '@/utils/nodePresets/validation';
import { jsonObjectOrEmpty } from '@/utils/runtimeTypes';

function runtimeData(
    type: NodePresetNodeType,
    configured: NodePresetData,
    defaults: NodePresetRuntimeDefaults | Record<string, never>,
    generateId: () => string,
): NodePresetUnknownRecord {
    const merged = {
        ...jsonObjectOrEmpty(defaults),
        ...jsonObjectOrEmpty(configured),
    };
    if (type === 'textToText') {
        return { ...merged, reply: '', usageData: null, activeGenerationHistoryId: undefined };
    }
    if (type === 'parallelization' && 'models' in configured && 'aggregator' in configured) {
        const data = configured;
        const aggregator = isRecord(merged.aggregator) ? merged.aggregator : {};
        return {
            ...merged,
            models: data.models.map((model) => ({
                model: model.model,
                id: generateId(),
                reply: '',
                usageData: null,
            })),
            aggregator: {
                ...data.aggregator,
                ...aggregator,
                prompt: data.aggregator.prompt,
                model: data.aggregator.model,
                reply: '',
                usageData: null,
            },
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
        return {
            ...merged,
            files: configured.files.map((file) => ({
                ...file,
                children: [],
            })),
        };
    }
    if (type === 'contextMerger') return { ...merged, branch_summaries: {} };
    if (
        type === 'group' &&
        'title' in configured &&
        'comment' in configured &&
        'colorIndex' in configured
    ) {
        const group = configured;
        return {
            title: group.title,
            comment: group.comment,
            color: nodeGroupColorFromIndex(group.colorIndex),
            contentMode: 'plain',
        };
    }
    return merged;
}

export function materializeNodePreset(
    preset: NodePreset,
    options: MaterializeNodePresetOptions,
): NodePresetResult<MaterializedNodePreset> {
    const validated = validateNodePresetSettings({
        schemaVersion: NODE_PRESET_SCHEMA_VERSION,
        presets: [preset],
    });
    if (!validated.valid || !validated.value) {
        return { valid: false, issues: validated.issues };
    }
    const source = validated.value.presets[0];
    if (source.nodes.length === 0) {
        return {
            valid: false,
            issues: [
                {
                    path: ['nodes'],
                    code: 'empty_draft',
                    message: 'Empty drafts cannot be materialized.',
                },
            ],
        };
    }

    const idMap = new Map<string, string>();
    source.nodes.forEach((node) =>
        idMap.set(
            node.id,
            node.type === 'group' ? `group-${options.generateId()}` : options.generateId(),
        ),
    );
    const roots = source.nodes.filter((node) => !node.parentId);
    const bounds = {
        minX: Math.min(...roots.map((node) => node.position.x)),
        minY: Math.min(...roots.map((node) => node.position.y)),
        maxX: Math.max(...roots.map((node) => node.position.x + node.width)),
        maxY: Math.max(...roots.map((node) => node.position.y + node.height)),
    };
    const invocation = options.invocationPosition;
    const offset = invocation
        ? {
              x: invocation.x - (bounds.minX + bounds.maxX) / 2,
              y: invocation.y - (bounds.minY + bounds.maxY) / 2,
          }
        : { x: 0, y: 0 };
    const nodes = source.nodes
        .map((node): MaterializedPresetNode => {
            const id = idMap.get(node.id)!;
            const parentNode = node.parentId ? idMap.get(node.parentId) : undefined;
            const position = parentNode
                ? { ...node.position }
                : { x: node.position.x + offset.x, y: node.position.y + offset.y };
            const materializedNode = {
                id,
                type: node.type,
                position,
                width: node.width,
                height: node.height,
                selected: true as const,
                data: runtimeData(
                    node.type,
                    node.data,
                    options.dataDefaults?.[node.type] ?? {},
                    options.generateId,
                ),
                style: { width: `${node.width}px`, height: `${node.height}px` },
            };
            if (parentNode) Object.assign(materializedNode, { parentNode, expandParent: true });
            if (node.type === 'group') Object.assign(materializedNode, { zIndex: -1 });
            return materializedNode;
        })
        .sort((left, right) => Number(right.type === 'group') - Number(left.type === 'group'));
    const edges = source.edges.map((edge): MaterializedPresetEdge => {
        const sourceId = idMap.get(edge.source)!;
        const targetId = idMap.get(edge.target)!;
        return {
            id: options.generateId(),
            source: sourceId,
            target: targetId,
            sourceHandle: `${edge.category}_${sourceId}`,
            targetHandle: `${edge.category}_${targetId}`,
            type: 'custom',
            selected: false,
        };
    });
    const sortedRoots = source.nodes
        .filter((node) => !node.parentId)
        .sort(
            (left, right) =>
                left.position.y - right.position.y ||
                left.position.x - right.position.x ||
                left.id.localeCompare(right.id),
        );
    const rootIds = sortedRoots.map((node) => idMap.get(node.id)!);
    return {
        valid: true,
        issues: [],
        value: { nodes, edges, idMap, rootIds, primaryRootId: rootIds[0] },
    };
}
