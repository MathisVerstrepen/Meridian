import { describe, expect, it } from 'vitest';
import {
    classifyAlibabaHappyHorseVideoModel,
    getAlibabaHappyHorseCapabilities,
    isAlibabaTokenPlanModel,
} from '@/utils/alibabaTokenPlanMedia';

describe('Alibaba Token Plan media helpers', () => {
    it('recognizes only prefixed Alibaba model IDs', () => {
        expect(isAlibabaTokenPlanModel('alibaba-token-plan/future-image-family-v9')).toBe(true);
        expect(isAlibabaTokenPlanModel('alibaba-token-plan/')).toBe(false);
        expect(isAlibabaTokenPlanModel('openrouter/happyhorse-t2v-future')).toBe(false);
    });

    it.each([
        ['alibaba-token-plan/happyhorse-future-t2v-v9', 't2v'],
        ['alibaba-token-plan/FUTURE.HAPPYHORSE.I2V.2030', 'i2v'],
        ['alibaba-token-plan/r2v_happyhorse_next', 'r2v'],
    ] as const)('classifies standalone HappyHorse operation tokens in %s', (modelId, operation) => {
        expect(classifyAlibabaHappyHorseVideoModel(modelId)).toBe(operation);
    });

    it.each([
        'alibaba-token-plan/future-video-t2v-v9',
        'alibaba-token-plan/happyhorset2v-future',
        'alibaba-token-plan/happyhorse-future-video',
        'alibaba-token-plan/happyhorse-t2v-i2v-future',
        'openrouter/happyhorse-t2v-future',
    ])('fails closed for unknown or ambiguous ID %s', (modelId) => {
        expect(classifyAlibabaHappyHorseVideoModel(modelId)).toBeNull();
    });

    it('returns the operation-specific reference, ratio, and provider-audio matrix', () => {
        expect(getAlibabaHappyHorseCapabilities(
            'alibaba-token-plan/happyhorse-future-t2v-v9',
        )).toMatchObject({
            operation: 't2v',
            minimumReferences: 0,
            maximumReferences: 0,
            usesAspectRatio: true,
            resolutions: ['720p', '1080p'],
            durationOptions: [null, 4, 6, 8, 10],
            audioManagedByProvider: true,
        });
        expect(getAlibabaHappyHorseCapabilities(
            'alibaba-token-plan/happyhorse-future-i2v-v9',
        )).toMatchObject({
            operation: 'i2v',
            minimumReferences: 1,
            maximumReferences: 1,
            usesAspectRatio: false,
            aspectRatios: [],
        });
        expect(getAlibabaHappyHorseCapabilities(
            'alibaba-token-plan/happyhorse-future-r2v-v9',
        )).toMatchObject({
            operation: 'r2v',
            minimumReferences: 1,
            maximumReferences: 8,
            usesAspectRatio: true,
        });
    });
});
