export type AlibabaHappyHorseOperation = 't2v' | 'i2v' | 'r2v';

export type AlibabaHappyHorseCapabilities = {
    operation: AlibabaHappyHorseOperation;
    minimumReferences: number;
    maximumReferences: number;
    usesAspectRatio: boolean;
    aspectRatios: readonly string[];
    resolutions: readonly string[];
    durationOptions: readonly (number | null)[];
    audioManagedByProvider: true;
};

export const ALIBABA_TOKEN_PLAN_MODEL_PREFIX = 'alibaba-token-plan/';
export const ALIBABA_TOKEN_PLAN_IMAGE_MAX_REFERENCES = 3;
export const ALIBABA_HAPPYHORSE_RESOLUTIONS = ['720p', '1080p'] as const;
export const ALIBABA_HAPPYHORSE_ASPECT_RATIOS = [
    '16:9',
    '9:16',
    '1:1',
    '4:3',
    '3:4',
    '21:9',
    '9:21',
] as const;
export const ALIBABA_HAPPYHORSE_DURATION_OPTIONS = [null, 4, 6, 8, 10] as const;

export const isAlibabaTokenPlanModel = (modelId: string) =>
    modelId.startsWith(ALIBABA_TOKEN_PLAN_MODEL_PREFIX)
    && modelId.length > ALIBABA_TOKEN_PLAN_MODEL_PREFIX.length;

export const classifyAlibabaHappyHorseVideoModel = (
    modelId: string,
): AlibabaHappyHorseOperation | null => {
    if (!isAlibabaTokenPlanModel(modelId)) return null;

    const rawModelId = modelId.slice(ALIBABA_TOKEN_PLAN_MODEL_PREFIX.length);
    const tokens = rawModelId.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    if (!tokens.includes('happyhorse')) return null;

    const operations = (['t2v', 'i2v', 'r2v'] as const).filter((operation) =>
        tokens.includes(operation),
    );
    return operations.length === 1 ? operations[0] : null;
};

export const getAlibabaHappyHorseCapabilities = (
    modelId: string,
): AlibabaHappyHorseCapabilities | null => {
    const operation = classifyAlibabaHappyHorseVideoModel(modelId);
    if (!operation) return null;

    if (operation === 't2v') {
        return {
            operation,
            minimumReferences: 0,
            maximumReferences: 0,
            usesAspectRatio: true,
            aspectRatios: ALIBABA_HAPPYHORSE_ASPECT_RATIOS,
            resolutions: ALIBABA_HAPPYHORSE_RESOLUTIONS,
            durationOptions: ALIBABA_HAPPYHORSE_DURATION_OPTIONS,
            audioManagedByProvider: true,
        };
    }
    if (operation === 'i2v') {
        return {
            operation,
            minimumReferences: 1,
            maximumReferences: 1,
            usesAspectRatio: false,
            aspectRatios: [],
            resolutions: ALIBABA_HAPPYHORSE_RESOLUTIONS,
            durationOptions: ALIBABA_HAPPYHORSE_DURATION_OPTIONS,
            audioManagedByProvider: true,
        };
    }
    return {
        operation,
        minimumReferences: 1,
        maximumReferences: 8,
        usesAspectRatio: true,
        aspectRatios: ALIBABA_HAPPYHORSE_ASPECT_RATIOS,
        resolutions: ALIBABA_HAPPYHORSE_RESOLUTIONS,
        durationOptions: ALIBABA_HAPPYHORSE_DURATION_OPTIONS,
        audioManagedByProvider: true,
    };
};
