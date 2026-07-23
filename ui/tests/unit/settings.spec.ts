import { describe, expect, it } from 'vitest';
import {
    DEFAULT_MODEL_DROPDOWN_SECTION_ORDER,
    SUBSCRIPTION_PROVIDER_META,
    normalizeModelDropdownSectionOrder,
} from '@/constants/modelDropdownSections';
import { SETTINGS_SEARCH_ENTRIES } from '@/constants/settingsEntries';
import type { SettingSearchEntry } from '@/utils/settingsSearch';
import { searchSettings } from '@/utils/settingsSearch';

const entry = (
    id: string,
    title: string,
    overrides: Partial<SettingSearchEntry> = {},
): SettingSearchEntry => ({
    id,
    title,
    tab: 'General',
    group: 'Preferences',
    ...overrides,
});

describe('normalizeModelDropdownSectionOrder', () => {
    it('normalizes missing orders to independent copies of the complete default order', () => {
        const fromUndefined = normalizeModelDropdownSectionOrder(undefined);
        const fromNull = normalizeModelDropdownSectionOrder(null);

        expect(fromUndefined).toEqual(DEFAULT_MODEL_DROPDOWN_SECTION_ORDER);
        expect(fromNull).toEqual(DEFAULT_MODEL_DROPDOWN_SECTION_ORDER);
        expect(fromUndefined).not.toBe(DEFAULT_MODEL_DROPDOWN_SECTION_ORDER);
        expect(fromNull).not.toBe(DEFAULT_MODEL_DROPDOWN_SECTION_ORDER);
    });

    it('preserves first valid entries, drops invalid duplicates, and appends defaults', () => {
        const persisted = [
            'all',
            'unknown',
            'pinned',
            'all',
            'subscription:github_copilot',
        ];
        const original = [...persisted];

        expect(normalizeModelDropdownSectionOrder(persisted)).toEqual([
            'all',
            'pinned',
            'subscription:github_copilot',
            ...DEFAULT_MODEL_DROPDOWN_SECTION_ORDER.filter(
                (sectionId) =>
                    !['all', 'pinned', 'subscription:github_copilot'].includes(sectionId),
            ),
        ]);
        expect(persisted).toEqual(original);
    });

    it('adds the Alibaba section and appends it to a complete legacy order', () => {
        const legacyOrder = [
            'pinned',
            'subscription:claude_agent',
            'subscription:github_copilot',
            'subscription:z_ai_coding_plan',
            'subscription:gemini_cli',
            'subscription:openai_codex',
            'subscription:opencode_go',
            'all',
        ];

        expect(SUBSCRIPTION_PROVIDER_META.alibaba_token_plan).toEqual({
            label: 'Alibaba Cloud Token Plan (Personal)',
            icon: 'models/qwen',
            description: 'Alibaba Cloud Model Studio Personal subscription models.',
        });
        expect(normalizeModelDropdownSectionOrder(legacyOrder)).toEqual([
            ...legacyOrder,
            'subscription:alibaba_token_plan',
        ]);
    });
});

describe('searchSettings', () => {
    it('normalizes diacritics, ampersands, and punctuation', () => {
        const entries = [entry('normalized', 'Café & Security')];

        expect(searchSettings('cafe, and security!', entries).map((result) => result.entry.id))
            .toEqual(['normalized']);
    });

    it('matches plural-to-singular variants and prefixes of at least three characters', () => {
        const entries = [
            entry('matching', 'Alerts', { keywords: ['policy', 'notifications'] }),
            entry('missing-prefix', 'Policies', { keywords: ['notebook'] }),
        ];

        expect(searchSettings('policies notif', entries).map((result) => result.entry.id)).toEqual([
            'matching',
        ]);
    });

    it('requires every query token to match', () => {
        const entries = [
            entry('complete', 'Account Privacy'),
            entry('partial', 'Account Billing'),
        ];

        expect(searchSettings('account privacy', entries).map((result) => result.entry.id)).toEqual([
            'complete',
        ]);
    });

    it('ranks exact titles above keyword- and description-only matches', () => {
        const entries = [
            entry('description', 'Account', { description: 'Privacy controls' }),
            entry('keyword', 'Security', { keywords: ['privacy'] }),
            entry('title', 'Privacy'),
        ];

        expect(searchSettings('privacy', entries).map((result) => result.entry.id)).toEqual([
            'title',
            'keyword',
            'description',
        ]);
    });

    it('returns no results for punctuation-only input and orders equal scores by title', () => {
        const entries = [
            entry('zulu', 'Zulu', { keywords: ['shared-match'] }),
            entry('alpha', 'Alpha', { keywords: ['shared-match'] }),
        ];

        expect(searchSettings('---', entries)).toEqual([]);
        expect(searchSettings('shared match', entries).map((result) => result.entry.id)).toEqual([
            'alpha',
            'zulu',
        ]);
    });

    it('finds the Alibaba Personal provider by product and credential keywords', () => {
        expect(
            searchSettings('Alibaba Model Studio Personal API key', SETTINGS_SEARCH_ENTRIES).map(
                (result) => result.entry.id,
            ),
        ).toContain('providers.alibaba_token_plan');
    });
});
