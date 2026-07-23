import { describe, expect, it } from 'vitest';
import { ToolEnum } from '@/types/enums';
import { decodeModelCatalog } from '@/utils/modelCatalog';

describe('decodeModelCatalog', () => {
    it('decodes all known version-1 capabilities, tools, pricing, and warnings', () => {
        const result = decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'all-capabilities',
                    name: 'All Capabilities',
                    icon: 'github-copilot',
                    provider: 'github_copilot',
                    created: '2026-07-18',
                    contextLength: 128000,
                    pricing: {
                        prompt: '0.000003',
                        completion: '0.000006',
                        image: '0.04',
                    },
                    capabilities: 127,
                    supportedTools: 63,
                    reasoningEfforts: -1,
                },
            ],
            warnings: [
                {
                    provider: 'github_copilot',
                    title: 'Provider warning',
                    message: 'Reconnect the provider.',
                    actionLabel: 'Reconnect',
                    actionUrl: '/settings',
                },
            ],
        });

        expect(result.data).toHaveLength(1);
        expect(result.data[0]).toMatchObject({
            id: 'all-capabilities',
            name: 'All Capabilities',
            icon: 'github-copilot',
            provider: 'github_copilot',
            context_length: 128000,
            pricing: {
                prompt: '0.000003',
                completion: '0.000006',
                image: '0.04',
            },
            architecture: {
                output_modalities: ['text', 'image', 'video'],
            },
            billingType: 'subscription',
            requiresConnection: true,
            supportsStructuredOutputs: true,
            supportsMeridianTools: true,
            toolsSupport: true,
            reasoningEfforts: -1,
            supportedMeridianToolNames: [
                ToolEnum.WEB_SEARCH,
                ToolEnum.LINK_EXTRACTION,
                ToolEnum.IMAGE_GENERATION,
                ToolEnum.EXECUTE_CODE,
                ToolEnum.VISUALISE,
                ToolEnum.ASK_USER,
            ],
        });
        expect(result.warnings).toEqual([
            {
                provider: 'github_copilot',
                title: 'Provider warning',
                message: 'Reconnect the provider.',
                actionLabel: 'Reconnect',
                actionUrl: '/settings',
            },
        ]);
    });

    it('applies defaults and ignores unknown capability and tool bits', () => {
        const result = decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'minimal',
                    name: 'Minimal',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 128,
                    supportedTools: 64,
                },
            ],
        });

        expect(result).toMatchObject({
            data: [
                {
                    id: 'minimal',
                    icon: '',
                    provider: 'openrouter',
                    architecture: { output_modalities: [] },
                    billingType: 'metered',
                    requiresConnection: false,
                    reasoningEfforts: 0,
                    supportedMeridianToolNames: [],
                },
            ],
            warnings: [],
        });
    });

    it('accepts Alibaba Token Plan as a subscription provider', () => {
        const result = decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'alibaba-token-plan/future-text-model-v9',
                    name: 'Future Text Model V9',
                    provider: 'alibaba_token_plan',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 65,
                },
            ],
        });

        expect(result.data[0]).toMatchObject({
            id: 'alibaba-token-plan/future-text-model-v9',
            provider: 'alibaba_token_plan',
            billingType: 'subscription',
            requiresConnection: true,
            architecture: { output_modalities: ['text'] },
        });
    });

    it('decodes dynamically discovered Alibaba image and video output modalities', () => {
        const result = decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'alibaba-token-plan/future-image-family-v9',
                    name: 'Future Image Family V9',
                    provider: 'alibaba_token_plan',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 66,
                },
                {
                    id: 'alibaba-token-plan/happyhorse-future-r2v-v9',
                    name: 'HappyHorse Future R2V V9',
                    provider: 'alibaba_token_plan',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 68,
                },
            ],
        });

        expect(result.data.find((item) => item.id.endsWith('future-image-family-v9')))
            .toMatchObject({
                provider: 'alibaba_token_plan',
                architecture: { output_modalities: ['image'] },
            });
        expect(result.data.find((item) => item.id.endsWith('happyhorse-future-r2v-v9')))
            .toMatchObject({
                provider: 'alibaba_token_plan',
                architecture: { output_modalities: ['video'] },
            });
    });

    it('rejects unsupported versions and malformed required values or masks', () => {
        expect(() => decodeModelCatalog({ version: 2, data: [] })).toThrow(
            'Unsupported model catalog version: 2',
        );
        expect(() => decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'broken',
                    name: 42,
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 0,
                },
            ],
        })).toThrow('Invalid model catalog value at data[0].name: expected a string');
        expect(() => decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'broken',
                    name: 'Broken',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: -1,
                },
            ],
        })).toThrow(
            'Invalid model catalog value at data[0].capabilities: expected a non-negative 32-bit integer',
        );
        expect(() => decodeModelCatalog({
            version: 1,
            data: [
                {
                    id: 'broken',
                    name: 'Broken',
                    pricing: { prompt: '0', completion: '0' },
                    capabilities: 0,
                    supportedTools: 1.5,
                },
            ],
        })).toThrow(
            'Invalid model catalog value at data[0].supportedTools: expected a non-negative 32-bit integer',
        );
    });
});
