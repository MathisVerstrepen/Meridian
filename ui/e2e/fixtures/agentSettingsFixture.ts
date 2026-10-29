import type { ModelInfo } from '../../app/types/model';
import { createAgentDraft } from '../../app/utils/agentEditor';
import { ToolEnum } from '../../app/types/enums';

export const AGENT_SETTINGS_MODELS: ModelInfo[] = ['Meridian Balanced', 'Meridian Fast'].map(
    (name, index) => ({
        id: index ? 'fixture/fast' : 'fixture/default',
        name,
        icon: '',
        architecture: {
            input_modalities: ['text'],
            output_modalities: ['text'],
            modality: 'text->text',
            tokenizer: 'fixture',
        },
        pricing: { completion: '0', prompt: '0' },
        provider: 'openrouter',
        billingType: 'metered',
        requiresConnection: false,
        supportsStructuredOutputs: true,
        supportsMeridianTools: true,
        supportedMeridianToolNames: Object.values(ToolEnum),
        toolsSupport: true,
        reasoningEfforts: -1,
    }),
);
export const AGENT_SETTINGS_PRESETS = [
    {
        ...createAgentDraft('fixture/default'),
        name: 'Research Agent',
        handle: 'research-agent',
        description: 'Find reliable sources and summarize the evidence.',
        category: 'Research',
        tools: [ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION],
        prompt_stack: [
            {
                name: 'Instructions',
                text: 'Research using primary sources and cite the evidence.',
                enabled: true,
            },
        ],
    },
    {
        ...createAgentDraft('fixture/default'),
        name: 'Summarizer',
        handle: 'summarizer',
        category: 'Writing',
        prompt_stack: [
            {
                name: 'Instructions',
                text: 'Summarize clearly and preserve key decisions.',
                enabled: true,
            },
        ],
    },
];
