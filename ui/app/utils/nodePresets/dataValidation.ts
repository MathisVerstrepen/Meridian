import { NODE_GROUP_COLORS } from '@/constants/nodeGroup';
import { ContextMergerModeEnum, ToolEnum } from '@/types/enums';
import type { NodePresetNodeType } from '@/types/nodePresets';
import type {
    NodePresetPathPart,
    NodePresetUnknownRecord,
    NodePresetValidationIssue,
} from '@/utils/nodePresets/contracts';
import {
    addIssue,
    containsDisallowedControl,
    forbidExtraKeys,
    requireRecord,
    validateBoolean,
    validateInteger,
    validateString,
    validateUuid,
} from '@/utils/nodePresets/validationHelpers';

const TOOLS = new Set<string>(Object.values(ToolEnum));
const CONTEXT_MODES = new Set<string>(Object.values(ContextMergerModeEnum));

const DATA_KEYS = {
    prompt: ['prompt', 'templateId', 'templateVariables'],
    filePrompt: ['files'],
    textToText: [
        'model',
        'selectedTools',
        'autoSelectTools',
        'imageModel',
        'videoModel',
        'visualiseModes',
    ],
    parallelization: ['models', 'aggregator', 'defaultModel'],
    routing: [
        'routeGroupId',
        'selectedTools',
        'autoSelectTools',
        'imageModel',
        'videoModel',
        'visualiseModes',
    ],
    github: ['repo', 'files', 'selectedIssues', 'branch'],
    contextMerger: ['mode', 'last_n', 'include_user_messages'],
    group: ['title', 'comment', 'colorIndex'],
} satisfies Record<NodePresetNodeType, readonly string[]>;

function validateOptionalStringFields(
    data: NodePresetUnknownRecord,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    validateString(data.imageModel, [...path, 'imageModel'], issues, 256, { nullable: true });
    validateString(data.videoModel, [...path, 'videoModel'], issues, 256, { nullable: true });
    validateBoolean(data.autoSelectTools, [...path, 'autoSelectTools'], issues, { nullable: true });
    if (data.visualiseModes === undefined || data.visualiseModes === null) return;
    const visualisePath = [...path, 'visualiseModes'];
    if (!requireRecord(data.visualiseModes, visualisePath, issues)) return;
    forbidExtraKeys(
        data.visualiseModes,
        ['enableMermaid', 'enableSvg', 'enableHtml'],
        visualisePath,
        issues,
    );
    for (const field of ['enableMermaid', 'enableSvg', 'enableHtml']) {
        validateBoolean(data.visualiseModes[field], [...visualisePath, field], issues, {
            nullable: true,
        });
    }
}

function validateTools(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!Array.isArray(value)) {
        addIssue(issues, path, 'invalid_type', 'Must be an array.');
        return;
    }
    const seen = new Set<string>();
    value.forEach((tool, index) => {
        if (!isRuntimeString(tool) || !TOOLS.has(tool)) {
            addIssue(issues, [...path, index], 'invalid_tool', 'Tool is not supported.');
        } else if (seen.has(tool)) {
            addIssue(issues, [...path, index], 'duplicate_tool', 'Selected tools must be unique.');
        }
        if (isRuntimeString(tool)) seen.add(tool);
    });
}

function validatePromptData(
    data: NodePresetUnknownRecord,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    validateString(data.prompt, [...path, 'prompt'], issues, 100_000, { required: true });
    validateString(data.templateId, [...path, 'templateId'], issues, 256, { nullable: true });
    const variablesPath = [...path, 'templateVariables'];
    if (!requireRecord(data.templateVariables, variablesPath, issues)) return;
    const entries = Object.entries(data.templateVariables);
    if (entries.length > 100) {
        addIssue(issues, variablesPath, 'too_many_items', 'At most 100 template variables are allowed.');
    }
    entries.forEach(([key, value]) => {
        validateString(key, [...variablesPath, key], issues, 128, {
            required: true,
            nonEmpty: true,
        });
        validateString(value, [...variablesPath, key], issues, 20_000, { required: true });
    });
}

function validateFilePromptData(
    data: NodePresetUnknownRecord,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!Array.isArray(data.files)) {
        addIssue(issues, [...path, 'files'], 'invalid_type', 'Must be an array.');
        return;
    }
    if (data.files.length > 50) {
        addIssue(issues, [...path, 'files'], 'too_many_items', 'At most 50 files are allowed.');
    }
    data.files.forEach((file, index) => {
        const filePath = [...path, 'files', index];
        if (!requireRecord(file, filePath, issues)) return;
        forbidExtraKeys(
            file,
            ['id', 'name', 'path', 'type', 'size', 'content_type', 'created_at', 'updated_at', 'cached'],
            filePath,
            issues,
        );
        validateUuid(file.id, [...filePath, 'id'], issues);
        validateString(file.name, [...filePath, 'name'], issues, 255, { required: true });
        validateString(file.path, [...filePath, 'path'], issues, 2_048, { nullable: true });
        if (file.type !== 'file' && file.type !== 'folder') {
            addIssue(issues, [...filePath, 'type'], 'invalid_value', 'Must be file or folder.');
        }
        validateInteger(file.size, [...filePath, 'size'], issues, 0, 10 ** 15, { nullable: true });
        validateString(file.content_type, [...filePath, 'content_type'], issues, 255, {
            nullable: true,
        });
        validateString(file.created_at, [...filePath, 'created_at'], issues, 64, { required: true });
        validateString(file.updated_at, [...filePath, 'updated_at'], issues, 64, { required: true });
        validateBoolean(file.cached, [...filePath, 'cached'], issues, { required: true });
    });
}

function validateParallelData(
    data: NodePresetUnknownRecord,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!Array.isArray(data.models)) {
        addIssue(issues, [...path, 'models'], 'invalid_type', 'Must be an array.');
    } else {
        if (data.models.length > 16) {
            addIssue(issues, [...path, 'models'], 'too_many_items', 'At most 16 models are allowed.');
        }
        data.models.forEach((model, index) => {
            const modelPath = [...path, 'models', index];
            if (!requireRecord(model, modelPath, issues)) return;
            forbidExtraKeys(model, ['model'], modelPath, issues);
            validateString(model.model, [...modelPath, 'model'], issues, 256, { required: true });
        });
    }
    const aggregatorPath = [...path, 'aggregator'];
    if (requireRecord(data.aggregator, aggregatorPath, issues)) {
        forbidExtraKeys(data.aggregator, ['prompt', 'model'], aggregatorPath, issues);
        validateString(data.aggregator.prompt, [...aggregatorPath, 'prompt'], issues, 100_000, {
            required: true,
        });
        validateString(data.aggregator.model, [...aggregatorPath, 'model'], issues, 256, {
            required: true,
        });
    }
    validateString(data.defaultModel, [...path, 'defaultModel'], issues, 256, { required: true });
}

function validateRepository(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (value === undefined || value === null || !requireRecord(value, path, issues)) return;
    forbidExtraKeys(
        value,
        [
            'provider',
            'encoded_provider',
            'full_name',
            'description',
            'clone_url_ssh',
            'clone_url_https',
            'default_branch',
            'stargazers_count',
        ],
        path,
        issues,
    );
    for (const field of ['provider', 'encoded_provider', 'full_name', 'default_branch']) {
        validateString(value[field], [...path, field], issues, 255, { required: true });
    }
    validateString(value.description, [...path, 'description'], issues, 4_096, {
        required: true,
        nullable: true,
    });
    validateString(value.clone_url_ssh, [...path, 'clone_url_ssh'], issues, 4_096, { required: true });
    validateString(value.clone_url_https, [...path, 'clone_url_https'], issues, 4_096, {
        required: true,
    });
    validateInteger(value.stargazers_count, [...path, 'stargazers_count'], issues, 0, Number.MAX_VALUE, {
        nullable: true,
    });
}

function validateGithubIssue(
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!requireRecord(value, path, issues)) return;
    forbidExtraKeys(
        value,
        [
            'id',
            'number',
            'title',
            'body',
            'state',
            'html_url',
            'is_pull_request',
            'user_login',
            'user_avatar',
            'created_at',
            'updated_at',
        ],
        path,
        issues,
    );
    validateInteger(value.id, [...path, 'id'], issues, 0, Number.MAX_VALUE, { required: true });
    validateInteger(value.number, [...path, 'number'], issues, 0, Number.MAX_VALUE, { required: true });
    validateString(value.title, [...path, 'title'], issues, 512, { required: true });
    validateString(value.body, [...path, 'body'], issues, 100_000, { required: true, nullable: true });
    if (value.state !== 'open' && value.state !== 'closed') {
        addIssue(issues, [...path, 'state'], 'invalid_value', 'Must be open or closed.');
    }
    validateString(value.html_url, [...path, 'html_url'], issues, 4_096, { required: true });
    validateBoolean(value.is_pull_request, [...path, 'is_pull_request'], issues, { required: true });
    validateString(value.user_login, [...path, 'user_login'], issues, 255, { required: true });
    validateString(value.user_avatar, [...path, 'user_avatar'], issues, 4_096, {
        required: true,
        nullable: true,
    });
    validateString(value.created_at, [...path, 'created_at'], issues, 255, { required: true });
    validateString(value.updated_at, [...path, 'updated_at'], issues, 255, { required: true });
}

function validateGithubData(
    data: NodePresetUnknownRecord,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    validateRepository(data.repo, [...path, 'repo'], issues);
    if (!Array.isArray(data.files)) {
        addIssue(issues, [...path, 'files'], 'invalid_type', 'Must be an array.');
    } else {
        if (data.files.length > 200) {
            addIssue(issues, [...path, 'files'], 'too_many_items', 'At most 200 files are allowed.');
        }
        data.files.forEach((file, index) => {
            const filePath = [...path, 'files', index];
            if (!requireRecord(file, filePath, issues)) return;
            forbidExtraKeys(file, ['name', 'type', 'path'], filePath, issues);
            validateString(file.name, [...filePath, 'name'], issues, 255, { required: true });
            if (file.type !== 'file' && file.type !== 'directory') {
                addIssue(issues, [...filePath, 'type'], 'invalid_value', 'Must be file or directory.');
            }
            validateString(file.path, [...filePath, 'path'], issues, 4_096, { required: true });
        });
    }
    if (!Array.isArray(data.selectedIssues)) {
        addIssue(issues, [...path, 'selectedIssues'], 'invalid_type', 'Must be an array.');
    } else {
        if (data.selectedIssues.length > 50) {
            addIssue(
                issues,
                [...path, 'selectedIssues'],
                'too_many_items',
                'At most 50 issues are allowed.',
            );
        }
        data.selectedIssues.forEach((issue, index) =>
            validateGithubIssue(issue, [...path, 'selectedIssues', index], issues),
        );
    }
    validateString(data.branch, [...path, 'branch'], issues, 255, { nullable: true });
}

export function validateNodeData(
    type: NodePresetNodeType,
    value: RuntimeValue,
    path: NodePresetPathPart[],
    issues: NodePresetValidationIssue[],
): void {
    if (!requireRecord(value, path, issues)) return;
    forbidExtraKeys(value, DATA_KEYS[type], path, issues);
    if (type === 'prompt') validatePromptData(value, path, issues);
    else if (type === 'filePrompt') validateFilePromptData(value, path, issues);
    else if (type === 'textToText' || type === 'routing') {
        const primary = type === 'textToText' ? 'model' : 'routeGroupId';
        validateString(value[primary], [...path, primary], issues, 256, { required: true });
        validateTools(value.selectedTools, [...path, 'selectedTools'], issues);
        validateOptionalStringFields(value, path, issues);
    } else if (type === 'parallelization') validateParallelData(value, path, issues);
    else if (type === 'github') validateGithubData(value, path, issues);
    else if (type === 'contextMerger') {
        if (!isRuntimeString(value.mode) || !CONTEXT_MODES.has(value.mode)) {
            addIssue(
                issues,
                [...path, 'mode'],
                'invalid_value',
                'Context merger mode is not supported.',
            );
        }
        validateInteger(value.last_n, [...path, 'last_n'], issues, 1, 1_000, { nullable: true });
        validateBoolean(value.include_user_messages, [...path, 'include_user_messages'], issues, {
            required: true,
        });
    } else {
        const titleValid = validateString(value.title, [...path, 'title'], issues, 128, {
            required: true,
        });
        if (titleValid && isRuntimeString(value.title) && containsDisallowedControl(value.title)) {
            addIssue(
                issues,
                [...path, 'title'],
                'control_character',
                'Must not contain control characters.',
            );
        }
        validateString(value.comment, [...path, 'comment'], issues, 4_000, { required: true });
        validateInteger(value.colorIndex, [...path, 'colorIndex'], issues, 0, NODE_GROUP_COLORS.length - 1, {
            required: true,
        });
    }
}
import { isRuntimeString } from '@/utils/runtimeTypes';
