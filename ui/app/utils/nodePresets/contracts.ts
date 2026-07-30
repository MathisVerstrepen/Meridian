import type { NodePresetNodeType } from '@/types/nodePresets';

export type NodePresetPathPart = string | number;
export type NodePresetUnknownRecord = Record<string, unknown>;

export interface NodePresetValidationIssue {
    path: NodePresetPathPart[];
    code: string;
    message: string;
}

export interface NodePresetResult<T> {
    value?: T;
    issues: NodePresetValidationIssue[];
    valid: boolean;
}

export interface NodePresetDraftInput {
    id: string;
    name: string;
    accentColor?: string;
    nodes: readonly NodePresetUnknownRecord[];
    edges: readonly NodePresetUnknownRecord[];
}

export interface MaterializedPresetNode {
    id: string;
    type: NodePresetNodeType;
    position: { x: number; y: number };
    width: number;
    height: number;
    parentNode?: string;
    expandParent?: boolean;
    selected: true;
    data: NodePresetUnknownRecord;
    style?: { width: string; height: string };
    zIndex?: number;
}

export interface MaterializedPresetEdge {
    id: string;
    source: string;
    target: string;
    sourceHandle: string;
    targetHandle: string;
    type: 'custom';
    selected: false;
}

export interface MaterializeNodePresetOptions {
    generateId: () => string;
    invocationPosition?: { x: number; y: number };
    dataDefaults?: Partial<Record<NodePresetNodeType, NodePresetUnknownRecord>>;
}

export interface MaterializedNodePreset {
    nodes: MaterializedPresetNode[];
    edges: MaterializedPresetEdge[];
    idMap: ReadonlyMap<string, string>;
    rootIds: string[];
    primaryRootId?: string;
}
