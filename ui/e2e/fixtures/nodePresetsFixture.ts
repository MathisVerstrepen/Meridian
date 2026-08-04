import {
    ContextMergerModeEnum,
    ModelsDropdownSortBy,
    NodeTypeEnum,
    PDFEngine,
} from '../../app/types/enums';
import type { NodePreset } from '../../app/types/nodePresets';
import type { Settings } from '../../app/types/settings';

export const NODE_PRESETS_FIXTURE_ROUTE = '/auth/node-presets-fixture';

export const PLACEMENT_PRESET: NodePreset = {
    id: '10000000-0000-4000-8000-000000000001',
    name: 'Grouped responder',
    accentColor: '#3366aa',
    nodes: [
        {
            id: '20000000-0000-4000-8000-000000000001',
            type: 'group',
            position: { x: 0, y: 0 },
            width: 620,
            height: 320,
            data: { title: 'Inputs', comment: '<strong>plain group</strong>', colorIndex: 2 },
        },
        {
            id: '20000000-0000-4000-8000-000000000002',
            type: 'prompt',
            position: { x: 60, y: 60 },
            width: 500,
            height: 200,
            parentId: '20000000-0000-4000-8000-000000000001',
            data: { prompt: 'Explain this code', templateId: null, templateVariables: {} },
        },
        {
            id: '20000000-0000-4000-8000-000000000003',
            type: 'textToText',
            position: { x: 760, y: 0 },
            width: 600,
            height: 300,
            data: { model: 'fixture/model', selectedTools: [], autoSelectTools: false },
        },
    ],
    edges: [
        {
            id: '30000000-0000-4000-8000-000000000001',
            source: '20000000-0000-4000-8000-000000000002',
            target: '20000000-0000-4000-8000-000000000003',
            category: 'prompt',
        },
    ],
};

export const GITHUB_PLACEMENT_PRESET: NodePreset = {
    id: '10000000-0000-4000-8000-000000000002',
    name: 'Repository review',
    accentColor: '#b85c8a',
    nodes: [
        {
            id: '40000000-0000-4000-8000-000000000001',
            type: 'github',
            position: { x: 0, y: 0 },
            width: 500,
            height: 250,
            data: { files: [], selectedIssues: [], branch: null },
        },
    ],
    edges: [],
};

export const INVALID_PLACEMENT_PRESET: NodePreset = {
    ...structuredClone(PLACEMENT_PRESET),
    id: '10000000-0000-4000-8000-000000000003',
    name: 'Invalid geometry',
    nodes: [{ ...structuredClone(PLACEMENT_PRESET.nodes[2]!), width: 1 }],
    edges: [],
};

export const createNodePresetFixtureSettings = (): Settings => ({
    general: {
        openChatViewOnNewCanvas: true,
        alwaysThinkingDisclosures: false,
        includeThinkingInContext: false,
        enableMessageCollapsing: true,
        defaultNodeType: NodeTypeEnum.TEXT_TO_TEXT,
    },
    account: { openRouterApiKey: null },
    appearance: {
        theme: 'standard',
        accentColor: '#eb5e28',
        customThemeColors: {
            softSilk: '#f5f1e8',
            stoneGray: '#85817a',
            anthracite: '#282624',
            obsidian: '#141312',
        },
    },
    models: {
        defaultModel: '',
        routingModel: '',
        titleGenerationModel: '',
        autoToolSelectionModel: '',
        excludeReasoning: false,
        systemPrompt: [],
        reasoningEffort: null,
        preferHigherReasoningEffort: true,
        maxTokens: null,
        temperature: null,
        topP: null,
        topK: null,
        frequencyPenalty: null,
        presencePenalty: null,
        repetitionPenalty: null,
    },
    modelsDropdown: {
        sortBy: ModelsDropdownSortBy.DATE_DESC,
        hideFreeModels: false,
        hidePaidModels: false,
        pinnedModels: [],
        sectionOrder: [],
    },
    block: {
        contextInputWheel: [],
        contextWheel: [],
        promptInputWheel: [],
        promptOutputWheel: [],
        attachmentInputWheel: [],
        attachmentOutputWheel: [],
    },
    blockPrompt: { overridePromptImproverModel: false, promptImproverModel: '' },
    blockAttachment: {
        pdf_engine: PDFEngine.DEFAULT,
        default_upload_folder: 'uploads',
        file_manager_default_sort: 'name_asc',
        file_manager_default_view: 'grid',
        file_manager_remember_last_sort: false,
        file_manager_remember_last_view: true,
    },
    blockParallelization: { models: [], aggregator: { prompt: '', model: '' } },
    blockRouting: { routeGroups: [] },
    blockGithub: { autoPull: false },
    blockContextMerger: {
        merger_mode: ContextMergerModeEnum.FULL,
        last_n: 5,
        summarizer_model: '',
        include_user_messages: true,
    },
    generationHistory: { max_saved_entries: 20, close_modal_on_restore: true },
    tools: { defaultSelectedTools: [], defaultAutoSelectTools: false },
    toolsWebSearch: {
        numResults: 5,
        ignoredSites: [],
        preferredSites: [],
        customApiKey: null,
        forceCustomApiKey: true,
    },
    toolsLinkExtraction: { maxLength: 100_000 },
    toolsImageGeneration: { defaultModel: '', defaultVideoModel: '', resolution: '1024x1024' },
    toolsVisualise: {
        enableMermaid: true,
        enableSvg: true,
        enableHtml: true,
        enableMermaidRetry: true,
        maxMermaidRetry: 3,
        defaultModel: '',
        standardModel: '',
        expertModel: '',
    },
    nodePresets: { schemaVersion: 1, presets: [] },
});
