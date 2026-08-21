import {
    DEFAULT_NODE_PRESET_ACCENT_COLOR,
    MAX_NODE_PRESETS,
    MAX_NODE_PRESETS_UTF8_BYTES,
    MAX_PRESET_COORDINATE,
    MAX_PRESET_DIMENSION,
    MAX_PRESET_EDGES,
    MAX_PRESET_NODES,
    isNodePresetEdgeCategory,
    isNodePresetAccentColor,
    isNodePresetNodeType,
    NODE_PRESET_EDGE_TYPE_RULES,
    NODE_PRESET_MINIMUM_DIMENSIONS,
    NODE_PRESET_SCHEMA_VERSION,
    type NodePreset,
    type NodePresetSettings,
} from '@/types/nodePresets';
import type {
    NodePresetPathPart,
    NodePresetResult,
    NodePresetUnknownRecord,
    NodePresetValidationIssue,
} from '@/utils/nodePresets/contracts';
import { validateNodeData } from '@/utils/nodePresets/dataValidation';
import {
    addIssue,
    containsDisallowedControl,
    forbidExtraKeys,
    isRecord,
    requireRecord,
    validateUuid,
} from '@/utils/nodePresets/validationHelpers';

function validateNode(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!requireRecord(value, path, issues)) return;
    forbidExtraKeys(
        value,
        ['id', 'type', 'position', 'width', 'height', 'parentId', 'data'],
        path,
        issues,
    );
    validateUuid(value.id, [...path, 'id'], issues);
    if (!isNodePresetNodeType(value.type)) {
        addIssue(issues, [...path, 'type'], 'unsupported_node_type', 'Node type is not supported.');
        return;
    }
    const type = value.type;
    const positionPath = [...path, 'position'];
    if (requireRecord(value.position, positionPath, issues)) {
        forbidExtraKeys(value.position, ['x', 'y'], positionPath, issues);
        for (const axis of ['x', 'y']) {
            const coordinate = value.position[axis];
            if (
                !isRuntimeNumber(coordinate) ||
                !Number.isFinite(coordinate) ||
                Math.abs(coordinate) > MAX_PRESET_COORDINATE
            ) {
                addIssue(
                    issues,
                    [...positionPath, axis],
                    'invalid_coordinate',
                    `Must be finite and between -${MAX_PRESET_COORDINATE} and ${MAX_PRESET_COORDINATE}.`,
                );
            }
        }
    }
    const minimum = NODE_PRESET_MINIMUM_DIMENSIONS[type];
    for (const [field, min] of [
        ['width', minimum.width],
        ['height', minimum.height],
    ] as const) {
        const dimension = value[field];
        if (
            !isRuntimeNumber(dimension) ||
            !Number.isFinite(dimension) ||
            dimension < min ||
            dimension > MAX_PRESET_DIMENSION
        ) {
            addIssue(
                issues,
                [...path, field],
                'invalid_dimension',
                `Must be finite and between ${min} and ${MAX_PRESET_DIMENSION}.`,
            );
        }
    }
    if (value.parentId !== undefined && value.parentId !== null) {
        validateUuid(value.parentId, [...path, 'parentId'], issues);
    }
    if (type === 'group' && value.parentId !== undefined && value.parentId !== null) {
        addIssue(issues, [...path, 'parentId'], 'nested_group', 'Group nodes cannot have a parent.');
    }
    validateNodeData(type, value.data, [...path, 'data'], issues);
}
function validateTopology(
    nodes: unknown[],
    edges: unknown[],
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    const nodeMap = new Map<string, NodePresetUnknownRecord>();
    nodes.forEach((node, index) => {
        if (!isRecord(node) || !isRuntimeString(node.id)) return;
        if (nodeMap.has(node.id)) {
            addIssue(
                issues,
                [...path, 'nodes', index, 'id'],
                'duplicate_node_id',
                'Node IDs must be unique within a preset.',
            );
        } else nodeMap.set(node.id, node);
    });
    const groupIds = new Set(
        [...nodeMap].filter(([, node]) => node.type === 'group').map(([id]) => id),
    );
    const childCount = new Map([...groupIds].map((id) => [id, 0]));
    nodes.forEach((node, index) => {
        if (!isRecord(node) || node.parentId === undefined || node.parentId === null) return;
        if (
            node.type === 'group' ||
            !isRuntimeString(node.parentId) ||
            !groupIds.has(node.parentId)
        ) {
            addIssue(
                issues,
                [...path, 'nodes', index, 'parentId'],
                'invalid_parent',
                'Parent must reference a group in the same preset.',
            );
        } else childCount.set(node.parentId, (childCount.get(node.parentId) ?? 0) + 1);
    });
    childCount.forEach((count, groupId) => {
        if (count !== 0) return;
        addIssue(
            issues,
            [
                ...path,
                'nodes',
                nodes.findIndex((node) => isRecord(node) && node.id === groupId),
            ],
            'empty_group',
            'Every group must have at least one direct child.',
        );
    });

    const edgeIds = new Set<string>();
    const edgeTuples = new Set<string>();
    const promptTargets = new Set<string>();
    edges.forEach((edge, index) => {
        if (!isRecord(edge) || !isRuntimeString(edge.id)) return;
        const edgePath = [...path, 'edges', index];
        if (edgeIds.has(edge.id)) {
            addIssue(
                issues,
                [...edgePath, 'id'],
                'duplicate_edge_id',
                'Edge IDs must be unique within a preset.',
            );
        }
        edgeIds.add(edge.id);
        if (
            !isRuntimeString(edge.source) ||
            !isRuntimeString(edge.target) ||
            !isNodePresetEdgeCategory(edge.category)
        ) {
            return;
        }
        if (edge.source === edge.target) {
            addIssue(issues, edgePath, 'self_edge', 'Edges cannot connect a node to itself.');
        }
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (!source || !target) {
            addIssue(
                issues,
                edgePath,
                'dangling_edge',
                'Edge endpoints must reference nodes in the same preset.',
            );
            return;
        }
        if (source.type === 'group' || target.type === 'group') {
            addIssue(issues, edgePath, 'group_edge', 'Edges cannot connect group nodes.');
        }
        const category = edge.category;
        const rules = NODE_PRESET_EDGE_TYPE_RULES[category];
        if (
            !rules.sources.some((type) => type === source.type) ||
            !rules.targets.some((type) => type === target.type)
        ) {
            addIssue(
                issues,
                edgePath,
                'incompatible_edge',
                `Invalid ${category} edge node types.`,
            );
        }
        const tuple = `${edge.source}\u0000${edge.target}\u0000${category}`;
        if (edgeTuples.has(tuple)) {
            addIssue(
                issues,
                edgePath,
                'duplicate_edge',
                'Duplicate source, target, and category edge.',
            );
        }
        edgeTuples.add(tuple);
        if (category === 'prompt') {
            if (promptTargets.has(edge.target)) {
                addIssue(
                    issues,
                    edgePath,
                    'prompt_multiplicity',
                    'A node may have only one incoming prompt edge.',
                );
            }
            promptTargets.add(edge.target);
        }
    });
}
function validatePreset(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!requireRecord(value, path, issues)) return;
    forbidExtraKeys(value, ['id', 'name', 'accentColor', 'nodes', 'edges'], path, issues);
    validateUuid(value.id, [...path, 'id'], issues);
    if (!isRuntimeString(value.name)) {
        addIssue(issues, [...path, 'name'], 'invalid_type', 'Must be a string.');
    } else {
        const name = value.name.trim();
        if (!name) addIssue(issues, [...path, 'name'], 'blank_name', 'Preset name must not be blank.');
        if ([...name].length > 64) {
            addIssue(
                issues,
                [...path, 'name'],
                'too_long',
                'Preset name must contain at most 64 Unicode code points.',
            );
        }
        if (containsDisallowedControl(name)) {
            addIssue(
                issues,
                [...path, 'name'],
                'control_character',
                'Preset name must not contain control characters.',
            );
        }
    }
    if (
        value.accentColor !== undefined &&
        !isNodePresetAccentColor(value.accentColor)
    ) {
        addIssue(
            issues,
            [...path, 'accentColor'],
            'invalid_accent_color',
            'Accent color must be a six-digit hex color such as #eb5e28.',
        );
    }
    if (!Array.isArray(value.nodes)) {
        addIssue(issues, [...path, 'nodes'], 'invalid_type', 'Must be an array.');
    } else {
        if (value.nodes.length > MAX_PRESET_NODES) {
            addIssue(
                issues,
                [...path, 'nodes'],
                'too_many_items',
                `At most ${MAX_PRESET_NODES} nodes are allowed.`,
            );
        }
        value.nodes.forEach((node, index) => validateNode(node, [...path, 'nodes', index], issues));
    }
    if (!Array.isArray(value.edges)) {
        addIssue(issues, [...path, 'edges'], 'invalid_type', 'Must be an array.');
    } else {
        if (value.edges.length > MAX_PRESET_EDGES) {
            addIssue(
                issues,
                [...path, 'edges'],
                'too_many_items',
                `At most ${MAX_PRESET_EDGES} edges are allowed.`,
            );
        }
        value.edges.forEach((edge, index) => {
            const edgePath = [...path, 'edges', index];
            if (!requireRecord(edge, edgePath, issues)) return;
            forbidExtraKeys(edge, ['id', 'source', 'target', 'category'], edgePath, issues);
            validateUuid(edge.id, [...edgePath, 'id'], issues);
            validateUuid(edge.source, [...edgePath, 'source'], issues);
            validateUuid(edge.target, [...edgePath, 'target'], issues);
            if (!isNodePresetEdgeCategory(edge.category)) {
                addIssue(
                    issues,
                    [...edgePath, 'category'],
                    'invalid_edge_category',
                    'Edge category is not supported.',
                );
            }
        });
    }
    if (Array.isArray(value.nodes) && Array.isArray(value.edges)) {
        validateTopology(value.nodes, value.edges, path, issues);
    }
}
function nameKey(value: string): string {
    return value
        .normalize('NFKC')
        .toLocaleLowerCase('und')
        .replace(/[ßẞ]/g, 'ss')
        .replace(/ς/g, 'σ');
}
function asValidatedPreset<Value>(value: Value): Value & NodePreset {
    return /* SAFETY: Full preset validation completed before canonicalization. */ value as Value & NodePreset;
}
function canonicalizeSettings<Value extends { presets?: RuntimeValue }>(value: Value): NodePresetSettings {
    const presets = (Array.isArray(value.presets) ? value.presets : []).map((value) => {
        const preset = asValidatedPreset(value);
        return {
        ...preset,
        name: preset.name.trim(),
        accentColor:
            isRuntimeString(preset.accentColor)
                ? preset.accentColor.toLowerCase()
                : DEFAULT_NODE_PRESET_ACCENT_COLOR,
        nodes: preset.nodes.map((node) => {
            const canonicalNode = { ...node, data: { ...node.data } };
            if (node.parentId !== undefined) {
                Object.assign(canonicalNode, { parentId: node.parentId });
            }
            return canonicalNode;
        }),
        edges: preset.edges.map((edge) => ({ ...edge })),
        };
    });
    return { schemaVersion: NODE_PRESET_SCHEMA_VERSION, presets };
}

export function normalizeNodePresetSettings(value: NodePresetSettings): NodePresetSettings {
    return canonicalizeSettings(value);
}

export function validateNodePresetSettings(value: RuntimeValue): NodePresetResult<NodePresetSettings> {
    const issues: NodePresetValidationIssue[] = [];
    if (!requireRecord(value, [], issues)) return { valid: false, issues };
    forbidExtraKeys(value, ['schemaVersion', 'presets'], [], issues);
    if (
        !isRuntimeNumber(value.schemaVersion) ||
        !Number.isInteger(value.schemaVersion) ||
        value.schemaVersion !== NODE_PRESET_SCHEMA_VERSION
    ) {
        addIssue(
            issues,
            ['schemaVersion'],
            'unsupported_schema_version',
            `Schema version must be integer ${NODE_PRESET_SCHEMA_VERSION}.`,
        );
    }
    if (!Array.isArray(value.presets)) {
        addIssue(issues, ['presets'], 'invalid_type', 'Must be an array.');
    } else {
        if (value.presets.length > MAX_NODE_PRESETS) {
            addIssue(
                issues,
                ['presets'],
                'too_many_items',
                `At most ${MAX_NODE_PRESETS} presets are allowed.`,
            );
        }
        value.presets.forEach((preset, index) => validatePreset(preset, ['presets', index], issues));
        const ids = new Set<string>();
        const names = new Set<string>();
        value.presets.forEach((preset, index) => {
            if (!isRecord(preset)) return;
            if (isRuntimeString(preset.id)) {
                if (ids.has(preset.id)) {
                    addIssue(
                        issues,
                        ['presets', index, 'id'],
                        'duplicate_preset_id',
                        'Preset IDs must be unique.',
                    );
                }
                ids.add(preset.id);
            }
            if (isRuntimeString(preset.name)) {
                const key = nameKey(preset.name.trim());
                if (names.has(key)) {
                    addIssue(
                        issues,
                        ['presets', index, 'name'],
                        'duplicate_preset_name',
                        'Preset names must be unique.',
                    );
                }
                names.add(key);
            }
        });
    }
    if (issues.length > 0) return { valid: false, issues };
    const normalized = canonicalizeSettings(value);
    if (new TextEncoder().encode(JSON.stringify(normalized)).length > MAX_NODE_PRESETS_UTF8_BYTES) {
        addIssue(
            issues,
            [],
            'payload_too_large',
            `Node presets must be at most ${MAX_NODE_PRESETS_UTF8_BYTES} UTF-8 bytes.`,
        );
    }
    return issues.length > 0
        ? { valid: false, issues }
        : { valid: true, issues, value: normalized };
}
import { isRuntimeNumber, isRuntimeString } from '@/utils/runtimeTypes';
