import { describe, expect, it } from 'vitest';
import { NODE_GROUP_COLORS } from '@/constants/nodeGroup';
import { ContextMergerModeEnum, ToolEnum } from '@/types/enums';
import {
    DEFAULT_NODE_PRESET_ACCENT_COLOR,
    MAX_NODE_PRESETS_UTF8_BYTES,
    NODE_PRESET_EDGE_TYPE_RULES,
    NODE_PRESET_MINIMUM_DIMENSIONS,
    NODE_PRESET_SCHEMA_VERSION,
    type NodePreset,
} from '@/types/nodePresets';
import {
    materializeNodePreset,
    serializeNodePreset,
    validateNodePresetSettings,
} from '@/utils/nodePresets';

const ids = {
    preset: '00000000-0000-0000-0000-000000000001',
    group: '00000000-0000-0000-0000-000000000002',
    prompt: '00000000-0000-0000-0000-000000000003',
    generator: '00000000-0000-0000-0000-000000000004',
    edge: '00000000-0000-0000-0000-000000000005',
};

function canonicalPreset(): NodePreset {
    return {
        id: ids.preset,
        name: 'Starter',
        accentColor: '#3366aa',
        nodes: [
            {
                id: ids.group,
                type: 'group',
                position: { x: 100, y: 200 },
                width: 700,
                height: 500,
                data: { title: '<b>Plain</b>', comment: 'No HTML rendering', colorIndex: 3 },
            },
            {
                id: ids.prompt,
                type: 'prompt',
                position: { x: 40, y: 50 },
                width: 500,
                height: 200,
                parentId: ids.group,
                data: { prompt: 'Hello', templateId: null, templateVariables: { name: 'Ada' } },
            },
            {
                id: ids.generator,
                type: 'textToText',
                position: { x: 900, y: 300 },
                width: 600,
                height: 300,
                data: {
                    model: 'provider/model',
                    selectedTools: [ToolEnum.WEB_SEARCH],
                    autoSelectTools: false,
                },
            },
        ],
        edges: [
            {
                id: ids.edge,
                source: ids.prompt,
                target: ids.generator,
                category: 'prompt',
            },
        ],
    };
}

describe('node preset contract constants', () => {
    it('mirrors backend version, geometry, edge mapping, and byte limits', () => {
        expect(NODE_PRESET_SCHEMA_VERSION).toBe(1);
        expect(MAX_NODE_PRESETS_UTF8_BYTES).toBe(524_288);
        expect(NODE_PRESET_MINIMUM_DIMENSIONS).toEqual({
            prompt: { width: 500, height: 200 },
            filePrompt: { width: 500, height: 275 },
            textToText: { width: 600, height: 300 },
            parallelization: { width: 660, height: 450 },
            routing: { width: 600, height: 300 },
            github: { width: 500, height: 250 },
            contextMerger: { width: 285, height: 135 },
            group: { width: 40, height: 40 },
        });
        expect(NODE_PRESET_EDGE_TYPE_RULES.attachment).toEqual({
            sources: ['filePrompt', 'github'],
            targets: ['textToText', 'parallelization', 'routing'],
        });
        expect(NODE_GROUP_COLORS).toHaveLength(11);
    });
});

describe('validateNodePresetSettings', () => {
    it('normalizes names and accepts canonical topology plus empty drafts', () => {
        const result = validateNodePresetSettings({
            schemaVersion: 1,
            presets: [
                { ...canonicalPreset(), name: '  Starter  ' },
                {
                    id: '00000000-0000-0000-0000-000000000010',
                    name: 'Draft',
                    accentColor: '#AABBCC',
                    nodes: [],
                    edges: [],
                },
            ],
        });

        expect(result.valid).toBe(true);
        expect(result.value?.presets.map((preset) => preset.name)).toEqual(['Starter', 'Draft']);
        expect(result.value?.presets[1]?.accentColor).toBe('#aabbcc');
    });

    it('defaults legacy accent colors and rejects invalid CSS colors', () => {
        const { accentColor: _accentColor, ...legacy } = structuredClone(canonicalPreset());
        const normalized = validateNodePresetSettings({ schemaVersion: 1, presets: [legacy] });
        expect(normalized.value?.presets[0]?.accentColor).toBe(DEFAULT_NODE_PRESET_ACCENT_COLOR);

        for (const accentColor of [
            'red',
            '#abcd',
            '#11223344',
            'var(--accent)',
            '#112233\n',
            '#112233\t',
            42,
        ]) {
            const invalid = validateNodePresetSettings({
                schemaVersion: 1,
                presets: [{ ...canonicalPreset(), accentColor }],
            });
            expect(invalid.issues).toContainEqual(
                expect.objectContaining({
                    path: ['presets', 0, 'accentColor'],
                    code: 'invalid_accent_color',
                }),
            );
        }
    });

    it.each([2, '1', 1.0 + Number.EPSILON])('rejects unsupported schema version %s', (schemaVersion) => {
        const result = validateNodePresetSettings({ schemaVersion, presets: [] });
        expect(result.valid).toBe(false);
        expect(result.issues).toContainEqual(
            expect.objectContaining({ path: ['schemaVersion'], code: 'unsupported_schema_version' }),
        );
    });

    it('rejects extras, duplicate normalized names, invalid topology, and runtime fields', () => {
        const first = canonicalPreset();
        const second = {
            ...canonicalPreset(),
            id: '00000000-0000-0000-0000-000000000020',
            name: 'ＳＴＡＲＴＥＲ',
            nodes: canonicalPreset().nodes.map((node) => ({ ...node })),
            edges: canonicalPreset().edges.map((edge) => ({ ...edge })),
        };
        const generator = first.nodes.find((node) => node.type === 'textToText');
        Object.assign(generator!.data, { reply: 'must not persist' });
        first.edges.push({
            id: '00000000-0000-0000-0000-000000000099',
            source: ids.generator,
            target: ids.prompt,
            category: 'prompt',
        });

        const result = validateNodePresetSettings({ schemaVersion: 1, presets: [first, second] });

        expect(result.valid).toBe(false);
        expect(result.issues.map((issue) => issue.code)).toEqual(
            expect.arrayContaining(['extra_field', 'incompatible_edge', 'duplicate_preset_name']),
        );
    });

    it('uses compact UTF-8 bytes after normalization', () => {
        const oversized = Array.from({ length: 8 }, (_, presetIndex) => ({
            id: `00000000-0000-0000-0000-${String(presetIndex + 1).padStart(12, '0')}`,
            name: `Preset ${presetIndex}`,
            nodes: Array.from({ length: 20 }, (_, nodeIndex) => ({
                id: `10000000-0000-0000-${String(presetIndex).padStart(4, '0')}-${String(nodeIndex + 1).padStart(12, '0')}`,
                type: 'prompt',
                position: { x: nodeIndex, y: presetIndex },
                width: 500,
                height: 200,
                data: { prompt: 'é'.repeat(2_000), templateVariables: {} },
            })),
            edges: [],
        }));

        const result = validateNodePresetSettings({ schemaVersion: 1, presets: oversized });

        expect(result.issues).toContainEqual(expect.objectContaining({ code: 'payload_too_large' }));
    });
});

describe('serializeNodePreset', () => {
    it('allowlists configured data, flattens GitHub files, clears runtime data, and normalizes roots', () => {
        const result = serializeNodePreset({
            id: ids.preset,
            name: '  Serialized  ',
            accentColor: '#ABCDEF',
            nodes: [
                {
                    id: ids.generator,
                    type: 'textToText',
                    position: { x: 400, y: 300 },
                    dimensions: { width: 600, height: 300 },
                    data: {
                        model: 'provider/model',
                        selectedTools: [ToolEnum.ASK_USER],
                        reply: 'generated',
                        usageData: { total_tokens: 4 },
                        activeGenerationHistoryId: 'history',
                    },
                    selected: true,
                    graphId: 'forbidden-runtime',
                },
                {
                    id: '00000000-0000-0000-0000-000000000030',
                    type: 'github',
                    position: { x: 1_200, y: 600 },
                    width: 500,
                    height: 250,
                    data: {
                        files: [
                            {
                                name: 'src',
                                type: 'directory',
                                path: 'src',
                                children: [
                                    { name: 'index.ts', type: 'file', path: 'src/index.ts', children: [] },
                                ],
                            },
                        ],
                        selectedIssues: [],
                        oldId: 'runtime',
                    },
                },
            ],
            edges: [],
        });

        expect(result.valid).toBe(true);
        expect(result.value?.name).toBe('Serialized');
        expect(result.value?.accentColor).toBe('#abcdef');
        expect(result.value?.nodes.map((node) => node.position)).toEqual([
            { x: 0, y: 0 },
            { x: 800, y: 300 },
        ]);
        expect(result.value?.nodes[0].data).toEqual({
            model: 'provider/model',
            selectedTools: [ToolEnum.ASK_USER],
        });
        expect(result.value?.nodes[1].data).toEqual({
            files: [
                { name: 'src', type: 'directory', path: 'src' },
                { name: 'index.ts', type: 'file', path: 'src/index.ts' },
            ],
            selectedIssues: [],
        });
    });
});

describe('materializeNodePreset', () => {
    it('maps fresh IDs and handles, centers roots, restores runtime shapes, and marks groups plain', () => {
        let sequence = 100;
        const generateId = () => `fresh-${sequence++}`;
        const preset = canonicalPreset();
        const result = materializeNodePreset(preset, {
            generateId,
            invocationPosition: { x: 1_000, y: 800 },
            dataDefaults: {
                textToText: {
                    reply: 'stale default',
                    usageData: { total_tokens: 99 },
                    activeGenerationHistoryId: 'stale-history',
                },
            },
        });

        expect(result.valid).toBe(true);
        const value = result.value!;
        expect(value.nodes[0]).toEqual(
            expect.objectContaining({
                id: 'group-fresh-100',
                type: 'group',
                data: expect.objectContaining({
                    title: '<b>Plain</b>',
                    contentMode: 'plain',
                    color: NODE_GROUP_COLORS[3],
                }),
            }),
        );
        const child = value.nodes.find((node) => node.type === 'prompt')!;
        expect(child.parentNode).toBe('group-fresh-100');
        expect(child.position).toEqual({ x: 40, y: 50 });
        const generator = value.nodes.find((node) => node.type === 'textToText')!;
        expect(generator.data).toEqual(
            expect.objectContaining({ reply: '', usageData: null, activeGenerationHistoryId: undefined }),
        );
        expect(value.edges[0]).toEqual(
            expect.objectContaining({
                source: child.id,
                target: generator.id,
                sourceHandle: `prompt_${child.id}`,
                targetHandle: `prompt_${generator.id}`,
                type: 'custom',
            }),
        );
        expect(value.rootIds).toHaveLength(2);
        const rootBounds = value.nodes.filter((node) => !node.parentNode);
        const minX = Math.min(...rootBounds.map((node) => node.position.x));
        const maxX = Math.max(...rootBounds.map((node) => node.position.x + node.width));
        const minY = Math.min(...rootBounds.map((node) => node.position.y));
        const maxY = Math.max(...rootBounds.map((node) => node.position.y + node.height));
        expect((minX + maxX) / 2).toBe(1_000);
        expect((minY + maxY) / 2).toBe(800);
    });

    it('rejects empty drafts without producing materialized arrays', () => {
        const result = materializeNodePreset(
            {
                id: ids.preset,
                name: 'Draft',
                accentColor: DEFAULT_NODE_PRESET_ACCENT_COLOR,
                nodes: [],
                edges: [],
            },
            { generateId: () => 'unused' },
        );
        expect(result).toEqual({
            valid: false,
            issues: [{ path: ['nodes'], code: 'empty_draft', message: 'Empty drafts cannot be materialized.' }],
        });
    });

    it('restores context merger runtime state without persisted branch summaries', () => {
        const preset: NodePreset = {
            id: ids.preset,
            name: 'Context',
            accentColor: DEFAULT_NODE_PRESET_ACCENT_COLOR,
            nodes: [
                {
                    id: ids.generator,
                    type: 'contextMerger',
                    position: { x: 0, y: 0 },
                    width: 285,
                    height: 135,
                    data: {
                        mode: ContextMergerModeEnum.LAST_N,
                        last_n: 5,
                        include_user_messages: true,
                    },
                },
            ],
            edges: [],
        };
        const result = materializeNodePreset(preset, { generateId: () => 'fresh' });
        expect(result.value?.nodes[0].data.branch_summaries).toEqual({});
    });
});
