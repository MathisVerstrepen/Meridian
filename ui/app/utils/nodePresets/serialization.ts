import { nodeGroupColorToIndex } from '@/constants/nodeGroup';
import { ContextMergerModeEnum, ToolEnum } from '@/types/enums';
import type { GithubIssue, RepositoryInfo } from '@/types/github';
import {
    DEFAULT_NODE_PRESET_ACCENT_COLOR,
    NODE_PRESET_SCHEMA_VERSION,
    type NodePreset,
    type NodePresetData,
    type NodePresetEdge,
    type NodePresetEdgeCategory,
    type NodePresetGithubFile,
    type NodePresetNode,
    type NodePresetNodeType,
} from '@/types/nodePresets';
import type {
    NodePresetDraftInput,
    NodePresetResult,
    NodePresetUnknownRecord,
} from '@/utils/nodePresets/contracts';
import { isRecord } from '@/utils/nodePresets/validationHelpers';
import { validateNodePresetSettings } from '@/utils/nodePresets/validation';

const TOOLS = new Set<string>(Object.values(ToolEnum));

function stringValue(value: RuntimeValue, fallback = ''): string {
    return isRuntimeString(value) ? value : fallback;
}

function optionalValue<T>(
    source: NodePresetUnknownRecord,
    key: string,
    convert: (value: RuntimeValue) => T,
): Partial<Record<string, T>> {
    return key in source ? { [key]: convert(source[key]) } : {};
}

function flattenGithubFiles(value: RuntimeValue): NodePresetGithubFile[] {
    if (!Array.isArray(value)) return [];
    const flattened: NodePresetGithubFile[] = [];
    const visit = (entry: RuntimeValue): void => {
        if (!isRecord(entry)) return;
        if (entry.type === 'file' || entry.type === 'directory') {
            flattened.push({
                name: stringValue(entry.name),
                type: entry.type,
                path: stringValue(entry.path),
            });
        }
        if (Array.isArray(entry.children)) entry.children.forEach(visit);
    };
    value.forEach(visit);
    return flattened;
}

function sanitizeGeneratorData(
    data: NodePresetUnknownRecord,
): { selectedTools: ToolEnum[] } & NodePresetUnknownRecord {
    return {
        selectedTools: Array.isArray(data.selectedTools)
            ? data.selectedTools.filter(
                  (tool): tool is ToolEnum => typeof tool === 'string' && TOOLS.has(tool),
              )
            : [],
        ...optionalValue(data, 'autoSelectTools', (entry) => (entry === null ? null : entry === true)),
        ...optionalValue(data, 'imageModel', (entry) =>
            entry === null ? null : stringValue(entry),
        ),
        ...optionalValue(data, 'videoModel', (entry) =>
            entry === null ? null : stringValue(entry),
        ),
        ...optionalValue(data, 'visualiseModes', (entry) =>
            entry === null
                ? null
                : isRecord(entry)
                  ? {
                        ...optionalValue(entry, 'enableMermaid', (item) => item === true),
                        ...optionalValue(entry, 'enableSvg', (item) => item === true),
                        ...optionalValue(entry, 'enableHtml', (item) => item === true),
                    }
                  : {},
        ),
    };
}

function sanitizeGithubData(data: NodePresetUnknownRecord): NodePresetData {
    return {
        ...optionalValue(data, 'repo', (entry) =>
            entry === null
                ? null
                : isRecord(entry)
                  ? ({
                        provider: stringValue(entry.provider),
                        encoded_provider: stringValue(entry.encoded_provider),
                        full_name: stringValue(entry.full_name),
                        description:
                            entry.description === null ? null : stringValue(entry.description),
                        clone_url_ssh: stringValue(entry.clone_url_ssh),
                        clone_url_https: stringValue(entry.clone_url_https),
                        default_branch: stringValue(entry.default_branch),
                        ...optionalValue(entry, 'stargazers_count', Number),
                    } satisfies RepositoryInfo)
                  : null,
        ),
        files: flattenGithubFiles(data.files),
        selectedIssues: Array.isArray(data.selectedIssues)
            ? data.selectedIssues.filter(isRecord).map(
                  (issue) =>
                      ({
                          id: Number(issue.id),
                          number: Number(issue.number),
                          title: stringValue(issue.title),
                          body: issue.body === null ? null : stringValue(issue.body),
                          state: issue.state === 'closed' ? 'closed' : 'open',
                          html_url: stringValue(issue.html_url),
                          is_pull_request: issue.is_pull_request === true,
                          user_login: stringValue(issue.user_login),
                          user_avatar:
                              issue.user_avatar === null ? null : stringValue(issue.user_avatar),
                          created_at: stringValue(issue.created_at),
                          updated_at: stringValue(issue.updated_at),
                      }) satisfies GithubIssue,
              )
            : [],
        ...optionalValue(data, 'branch', (entry) =>
            entry === null ? null : stringValue(entry),
        ),
    };
}

function sanitizeData(type: NodePresetNodeType, value: RuntimeValue): NodePresetData {
    const data = isRecord(value) ? value : {};
    if (type === 'prompt') {
        return {
            prompt: stringValue(data.prompt),
            ...optionalValue(data, 'templateId', (entry) =>
                entry === null ? null : stringValue(entry),
            ),
            templateVariables: isRecord(data.templateVariables)
                ? Object.fromEntries(
                      Object.entries(data.templateVariables).filter(
                          (entry): entry is [string, string] => typeof entry[1] === 'string',
                      ),
                  )
                : {},
        };
    }
    if (type === 'filePrompt') {
        return {
            files: Array.isArray(data.files)
                ? data.files.filter(isRecord).map((file) => ({
                      id: stringValue(file.id),
                      name: stringValue(file.name),
                      ...optionalValue(file, 'path', (entry) =>
                          entry === null ? null : stringValue(entry),
                      ),
                      type: file.type === 'folder' ? 'folder' : 'file',
                      ...optionalValue(file, 'size', (entry) =>
                          entry === null ? null : Number(entry),
                      ),
                      ...optionalValue(file, 'content_type', (entry) =>
                          entry === null ? null : stringValue(entry),
                      ),
                      created_at: stringValue(file.created_at),
                      updated_at: stringValue(file.updated_at),
                      cached: file.cached === true,
                  }))
                : [],
        };
    }
    if (type === 'textToText' || type === 'routing') {
        const shared = sanitizeGeneratorData(data);
        return type === 'textToText'
            ? { model: stringValue(data.model), ...shared }
            : { routeGroupId: stringValue(data.routeGroupId), ...shared };
    }
    if (type === 'parallelization') {
        return {
            models: Array.isArray(data.models)
                ? data.models.filter(isRecord).map((model) => ({ model: stringValue(model.model) }))
                : [],
            aggregator: {
                prompt: isRecord(data.aggregator) ? stringValue(data.aggregator.prompt) : '',
                model: isRecord(data.aggregator) ? stringValue(data.aggregator.model) : '',
            },
            defaultModel: stringValue(data.defaultModel),
        };
    }
    if (type === 'github') return sanitizeGithubData(data);
    if (type === 'contextMerger') {
        const mode = data.mode;
        return {
            mode:
                mode === ContextMergerModeEnum.SUMMARY || mode === ContextMergerModeEnum.LAST_N
                    ? mode
                    : ContextMergerModeEnum.FULL,
            ...optionalValue(data, 'last_n', (entry) =>
                entry === null ? null : Number(entry),
            ),
            include_user_messages: data.include_user_messages === true,
        };
    }
    return {
        title: stringValue(data.title),
        comment: stringValue(data.comment),
        colorIndex: Number.isInteger(data.colorIndex)
            ? Number(data.colorIndex)
            : nodeGroupColorToIndex(data.color),
    };
}

function readDimension(
    node: NodePresetUnknownRecord,
    dimension: 'width' | 'height',
): number {
    if (isRuntimeNumber(node[dimension])) return node[dimension];
    if (isRecord(node.dimensions) && isRuntimeNumber(node.dimensions[dimension])) {
        return node.dimensions[dimension];
    }
    if (isRecord(node.style)) {
        const parsed = Number.parseFloat(String(node.style[dimension] ?? ''));
        if (Number.isFinite(parsed)) return parsed;
    }
    return Number.NaN;
}

export function normalizeNodePresetGeometry(preset: NodePreset): NodePreset {
    const roots = preset.nodes.filter((node) => !node.parentId);
    if (roots.length === 0) return preset;
    const minX = Math.min(...roots.map((node) => node.position.x));
    const minY = Math.min(...roots.map((node) => node.position.y));
    return {
        ...preset,
        nodes: preset.nodes.map((node) =>
            node.parentId
                ? node
                : { ...node, position: { x: node.position.x - minX, y: node.position.y - minY } },
        ),
    };
}

export function serializeNodePreset(input: NodePresetDraftInput): NodePresetResult<NodePreset> {
    const nodes: NodePresetNode[] = input.nodes.map((node) => {
        const record = isRecord(node) ? node : {};
        const type = /* SAFETY: This untrusted candidate is passed directly to validateNodePresetSettings; assertion does not bypass that node-type check. */ stringValue(record.type) as NodePresetNodeType;
        const position = isRecord(record.position) ? record.position : {};
        const parentId =
            isRuntimeString(record.parentId)
                ? record.parentId
                : isRuntimeString(record.parentNode)
                  ? record.parentNode
                  : undefined;
        const serializedNode = {
            id: stringValue(record.id),
            type,
            position: { x: Number(position.x), y: Number(position.y) },
            width: readDimension(record, 'width'),
            height: readDimension(record, 'height'),
            data: sanitizeData(type, record.data),
        };
        if (parentId) Object.assign(serializedNode, { parentId });
        return serializedNode;
    });
    const edges: NodePresetEdge[] = input.edges.map((edge) => {
        const record = isRecord(edge) ? edge : {};
        const categoryValue =
            isRuntimeString(record.category)
                ? record.category
                : isRuntimeString(record.sourceHandle)
                  ? record.sourceHandle.split('_')[0]
                  : '';
        return {
            id: stringValue(record.id),
            source: stringValue(record.source),
            target: stringValue(record.target),
            category: /* SAFETY: This untrusted candidate is passed directly to validateNodePresetSettings; assertion does not bypass that edge-category check. */ categoryValue as NodePresetEdgeCategory,
        };
    });
    const normalized = normalizeNodePresetGeometry({
        id: input.id,
        name: input.name,
        accentColor: input.accentColor ?? DEFAULT_NODE_PRESET_ACCENT_COLOR,
        nodes,
        edges,
    });
    const result = validateNodePresetSettings({
        schemaVersion: NODE_PRESET_SCHEMA_VERSION,
        presets: [normalized],
    });
    return result.valid && result.value
        ? { valid: true, issues: [], value: result.value.presets[0] }
        : { valid: false, issues: result.issues };
}
import { isRuntimeNumber, isRuntimeString } from '@/utils/runtimeTypes';
