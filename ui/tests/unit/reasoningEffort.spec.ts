import { describe, expect, it } from 'vitest';
import { NodeTypeEnum, ReasoningEffortEnum } from '@/types/enums';
import {
    getCanvasModelIds,
    getExactModelReasoningEfforts,
    getKnownReasoningEffortsUnion,
    isKnownReasoningEffortsMask,
    isReasoningEffortSupported,
    reasoningEffortBit,
} from '@/utils/reasoningEffort';

describe('reasoning-effort helpers', () => {
    it('distinguishes known masks and supports only their selected efforts', () => {
        expect(isKnownReasoningEffortsMask(20)).toBe(true);
        expect(isKnownReasoningEffortsMask(undefined)).toBe(false);
        expect(isKnownReasoningEffortsMask(-1)).toBe(false);
        expect(reasoningEffortBit(ReasoningEffortEnum.HIGH)).toBe(4);
        expect(reasoningEffortBit(ReasoningEffortEnum.LOW)).toBe(16);

        expect(isReasoningEffortSupported(ReasoningEffortEnum.HIGH, 20)).toBe(true);
        expect(isReasoningEffortSupported(ReasoningEffortEnum.LOW, 20)).toBe(true);
        expect(isReasoningEffortSupported(ReasoningEffortEnum.MEDIUM, 20)).toBe(false);
        expect(isReasoningEffortSupported(ReasoningEffortEnum.NONE, 0)).toBe(false);
        expect(isReasoningEffortSupported(ReasoningEffortEnum.MAX, undefined)).toBe(true);
        expect(isReasoningEffortSupported(ReasoningEffortEnum.MAX, -1)).toBe(true);
    });

    it('looks up exact masks and unions known masks across deduplicated IDs', () => {
        const models = [
            { id: 'high', reasoningEfforts: 4 },
            { id: 'low', reasoningEfforts: 16 },
            { id: 'unknown', reasoningEfforts: -1 },
        ];

        expect(getExactModelReasoningEfforts('high', models)).toBe(4);
        expect(getExactModelReasoningEfforts('unknown', models)).toBeUndefined();
        expect(getExactModelReasoningEfforts('missing', models)).toBeUndefined();
        expect(getKnownReasoningEffortsUnion(['high', 'low', 'high', 'unknown'], models)).toBe(20);
        expect(getKnownReasoningEffortsUnion(['unknown', 'missing'], models)).toBeUndefined();
    });

    it('extracts and deduplicates model IDs from supported canvas node shapes', () => {
        const modelIds = getCanvasModelIds([
            { type: NodeTypeEnum.TEXT_TO_TEXT, data: { model: 'text-model' } },
            { type: NodeTypeEnum.ROUTING, data: { model: 'routing-model' } },
            {
                type: NodeTypeEnum.PARALLELIZATION,
                data: {
                    models: [
                        { model: 'parallel-a' },
                        { model: 'parallel-b' },
                        { model: 'text-model' },
                        { model: 42 },
                    ],
                    aggregator: { model: 'aggregator-model' },
                },
            },
            { type: NodeTypeEnum.PROMPT, data: { model: 'ignored-model' } },
            { type: NodeTypeEnum.TEXT_TO_TEXT, data: { model: 42 } },
            { type: NodeTypeEnum.PARALLELIZATION, data: { models: 'malformed' } },
            { type: NodeTypeEnum.ROUTING, data: null },
        ]);

        expect(modelIds).toEqual([
            'text-model',
            'routing-model',
            'parallel-a',
            'parallel-b',
            'aggregator-model',
        ]);
    });
});
