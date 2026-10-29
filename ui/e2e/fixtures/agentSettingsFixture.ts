import type { ModelInfo } from '../../app/types/model';
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
