import type { ContextMergerModeEnum, ToolEnum } from '@/types/enums';
import type { GithubIssue, RepositoryInfo } from '@/types/github';
import { isRuntimeString } from '@/utils/runtimeTypes';

export const NODE_PRESET_SCHEMA_VERSION = 1 as const;
export const MAX_NODE_PRESETS = 8;
export const MAX_PRESET_NODES = 20;
export const MAX_PRESET_EDGES = 40;
export const MAX_NODE_PRESETS_UTF8_BYTES = 524_288;
export const MAX_PRESET_COORDINATE = 1_000_000;
export const MAX_PRESET_DIMENSION = 4_000;
export const DEFAULT_NODE_PRESET_ACCENT_COLOR = '#eb5e28';
export const NODE_PRESET_ACCENT_COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/;
export const isNodePresetAccentColor = (value: RuntimeValue): value is string =>
    typeof value === 'string' && value.length === 7 && NODE_PRESET_ACCENT_COLOR_PATTERN.test(value);

export const NODE_PRESET_NODE_TYPES = [
    'prompt',
    'filePrompt',
    'textToText',
    'parallelization',
    'routing',
    'github',
    'contextMerger',
    'group',
] as const;

export type NodePresetNodeType = (typeof NODE_PRESET_NODE_TYPES)[number];

export const isNodePresetNodeType = <Value>(
    value: Value,
): value is Value & NodePresetNodeType =>
    isRuntimeString(value) && NODE_PRESET_NODE_TYPES.some((nodeType) => nodeType === value);

export const NODE_PRESET_EDGE_CATEGORIES = ['prompt', 'context', 'attachment'] as const;
export type NodePresetEdgeCategory = (typeof NODE_PRESET_EDGE_CATEGORIES)[number];

export const isNodePresetEdgeCategory = <Value>(
    value: Value,
): value is Value & NodePresetEdgeCategory =>
    isRuntimeString(value) && NODE_PRESET_EDGE_CATEGORIES.some((category) => category === value);

export const NODE_PRESET_MINIMUM_DIMENSIONS = {
    prompt: { width: 500, height: 200 },
    filePrompt: { width: 500, height: 275 },
    textToText: { width: 600, height: 300 },
    parallelization: { width: 660, height: 450 },
    routing: { width: 600, height: 300 },
    github: { width: 500, height: 250 },
    contextMerger: { width: 285, height: 135 },
    group: { width: 40, height: 40 },
} satisfies Record<
    NodePresetNodeType,
    Readonly<{ width: number; height: number }>
>;

export const NODE_PRESET_EDGE_TYPE_RULES = {
    prompt: {
        sources: ['prompt'],
        targets: ['prompt', 'textToText', 'parallelization', 'routing'],
    },
    context: {
        sources: ['textToText', 'parallelization', 'routing', 'contextMerger'],
        targets: ['textToText', 'parallelization', 'routing', 'contextMerger'],
    },
    attachment: {
        sources: ['filePrompt', 'github'],
        targets: ['textToText', 'parallelization', 'routing'],
    },
} satisfies Record<
    NodePresetEdgeCategory,
    Readonly<{ sources: readonly NodePresetNodeType[]; targets: readonly NodePresetNodeType[] }>
>;

export interface NodePresetPosition {
    x: number;
    y: number;
}

export interface NodePresetVisualiseModes {
    enableMermaid?: boolean;
    enableSvg?: boolean;
    enableHtml?: boolean;
}

export interface NodePresetPromptData {
    prompt: string;
    templateId?: string | null;
    templateVariables: Record<string, string>;
}

export interface NodePresetFileReference {
    id: string;
    name: string;
    path?: string | null;
    type: 'file' | 'folder';
    size?: number | null;
    content_type?: string | null;
    created_at: string;
    updated_at: string;
    cached: boolean;
}

export interface NodePresetFilePromptData {
    files: NodePresetFileReference[];
}

export interface NodePresetTextToTextData {
    model: string;
    selectedTools: ToolEnum[];
    autoSelectTools?: boolean | null;
    imageModel?: string | null;
    videoModel?: string | null;
    visualiseModes?: NodePresetVisualiseModes | null;
}

export interface NodePresetParallelizationData {
    models: Array<{ model: string }>;
    aggregator: { prompt: string; model: string };
    defaultModel: string;
}

export interface NodePresetRoutingData {
    routeGroupId: string;
    selectedTools: ToolEnum[];
    autoSelectTools?: boolean | null;
    imageModel?: string | null;
    videoModel?: string | null;
    visualiseModes?: NodePresetVisualiseModes | null;
}

export interface NodePresetGithubFile {
    name: string;
    type: 'file' | 'directory';
    path: string;
}

export interface NodePresetGithubData {
    repo?: RepositoryInfo | null;
    files: NodePresetGithubFile[];
    selectedIssues: GithubIssue[];
    branch?: string | null;
}

export interface NodePresetContextMergerData {
    mode: ContextMergerModeEnum;
    last_n?: number | null;
    include_user_messages: boolean;
}

export interface NodePresetGroupData {
    title: string;
    comment: string;
    colorIndex: number;
}

export type NodePresetData =
    | NodePresetPromptData
    | NodePresetFilePromptData
    | NodePresetTextToTextData
    | NodePresetParallelizationData
    | NodePresetRoutingData
    | NodePresetGithubData
    | NodePresetContextMergerData
    | NodePresetGroupData;

export interface NodePresetNode {
    id: string;
    type: NodePresetNodeType;
    position: NodePresetPosition;
    width: number;
    height: number;
    parentId?: string | null;
    data: NodePresetData;
}

export interface NodePresetEdge {
    id: string;
    source: string;
    target: string;
    category: NodePresetEdgeCategory;
}

export interface NodePreset {
    id: string;
    name: string;
    accentColor: string;
    nodes: NodePresetNode[];
    edges: NodePresetEdge[];
}

export interface NodePresetSettings {
    schemaVersion: typeof NODE_PRESET_SCHEMA_VERSION;
    presets: NodePreset[];
}
