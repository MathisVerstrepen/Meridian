import type { InferenceProvider } from '@/types/model';

export type SubscriptionInferenceProvider = Exclude<InferenceProvider, 'openrouter'>;

export interface ModelDropdownSectionDefinition {
    id: string;
    label: string;
    description: string;
    icon?: string;
    provider?: SubscriptionInferenceProvider;
    type: 'pinned' | 'subscription' | 'all';
}

export const MODEL_DROPDOWN_PINNED_SECTION_ID = 'pinned';
export const MODEL_DROPDOWN_ALL_SECTION_ID = 'all';

export const SUBSCRIPTION_PROVIDER_META: Record<
    SubscriptionInferenceProvider,
    { label: string; icon: string; description: string }
> = {
    claude_agent: {
        label: 'Claude Agent',
        icon: 'models/anthropic',
        description: 'Anthropic subscription-backed models.',
    },
    github_copilot: {
        label: 'GitHub Copilot',
        icon: 'models/github',
        description: 'GitHub Copilot subscription-backed models.',
    },
    z_ai_coding_plan: {
        label: 'Z.AI Coding Plan',
        icon: 'models/z-ai',
        description: 'Z.AI Coding Plan subscription-backed models.',
    },
    gemini_cli: {
        label: 'Gemini CLI',
        icon: 'models/google',
        description: 'Google AI subscription models via Gemini CLI.',
    },
    openai_codex: {
        label: 'OpenAI Codex',
        icon: 'models/openai',
        description: 'OpenAI Codex subscription-backed models.',
    },
    opencode_go: {
        label: 'OpenCode Go',
        icon: 'models/opencode',
        description: 'OpenCode Go subscription-backed open coding models.',
    },
};

export const SUBSCRIPTION_PROVIDERS = Object.keys(
    SUBSCRIPTION_PROVIDER_META,
) as SubscriptionInferenceProvider[];

export const getSubscriptionSectionId = (provider: SubscriptionInferenceProvider) =>
    `subscription:${provider}`;

export const parseSubscriptionSectionId = (sectionId: string): SubscriptionInferenceProvider | null => {
    if (!sectionId.startsWith('subscription:')) {
        return null;
    }

    const provider = sectionId.slice('subscription:'.length) as SubscriptionInferenceProvider;

    return provider in SUBSCRIPTION_PROVIDER_META ? provider : null;
};

export const DEFAULT_MODEL_DROPDOWN_SECTION_ORDER = [
    MODEL_DROPDOWN_PINNED_SECTION_ID,
    ...SUBSCRIPTION_PROVIDERS.map(getSubscriptionSectionId),
    MODEL_DROPDOWN_ALL_SECTION_ID,
];

export const getModelDropdownSectionDefinitions = (): ModelDropdownSectionDefinition[] => [
    {
        id: MODEL_DROPDOWN_PINNED_SECTION_ID,
        label: 'Pinned Models',
        description: 'Pinned models section.',
        type: 'pinned',
    },
    ...SUBSCRIPTION_PROVIDERS.map((provider) => ({
        id: getSubscriptionSectionId(provider),
        label: SUBSCRIPTION_PROVIDER_META[provider].label,
        description: SUBSCRIPTION_PROVIDER_META[provider].description,
        icon: SUBSCRIPTION_PROVIDER_META[provider].icon,
        provider,
        type: 'subscription' as const,
    })),
    {
        id: MODEL_DROPDOWN_ALL_SECTION_ID,
        label: 'All Models',
        description: 'All remaining metered models.',
        type: 'all',
    },
];

export const normalizeModelDropdownSectionOrder = (sectionOrder?: string[] | null) => {
    const normalized: string[] = [];

    for (const sectionId of sectionOrder ?? []) {
        if (
            DEFAULT_MODEL_DROPDOWN_SECTION_ORDER.includes(sectionId) &&
            !normalized.includes(sectionId)
        ) {
            normalized.push(sectionId);
        }
    }

    for (const defaultSectionId of DEFAULT_MODEL_DROPDOWN_SECTION_ORDER) {
        if (!normalized.includes(defaultSectionId)) {
            normalized.push(defaultSectionId);
        }
    }

    return normalized;
};
