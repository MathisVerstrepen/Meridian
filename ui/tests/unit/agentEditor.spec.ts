import { describe, expect, it } from 'vitest';
import { changeAgentTool, createAgentDraft, suggestAgentHandle } from '@/utils/agentEditor';
import { ToolEnum } from '@/types/enums';

describe('Agent creation defaults and identity', () => {
    it('creates a ready private profile using the account default without adding tools', () => {
        const profile = createAgentDraft('provider/default');
        expect(profile.lifecycle).toBe('active');
        expect(profile.visibility).toBe('private');
        expect(profile.model_settings.model).toBe('provider/default');
        expect(profile.tools).toEqual([]);
        expect(profile.model_settings.temperature).toBeNull();
    });
    it('suggests valid handles from names, including accents and numeric starts', () => {
        expect(suggestAgentHandle('Web Researcher', [])).toBe('web-researcher');
        expect(suggestAgentHandle('Résumé Helper', [])).toBe('resume-helper');
        expect(suggestAgentHandle('24/7 Assistant', [])).toBe('agent-24-7-assistant');
        for (const name of ['A', '🚀', '  ', 'X'.repeat(100)]) {
            expect(suggestAgentHandle(name, [])).toMatch(/^[a-z][a-z0-9_-]{1,49}$/);
        }
    });
    it('avoids collisions while keeping the server handle length limit', () => {
        expect(suggestAgentHandle('Research', ['research', 'research-2'])).toBe('research-3');
        const base = 'a'.repeat(50);
        const suggestion = suggestAgentHandle(base, [base]);
        expect(suggestion).toHaveLength(50);
        expect(suggestion.endsWith('-2')).toBe(true);
    });
    it('keeps an edited profile and its nested configuration independent from its source', () => {
        const source = createAgentDraft('original');
        source.lifecycle = 'draft';
        source.model_settings.temperature = 0.3;
        const edited = createAgentDraft('account-default', source);
        edited.model_settings.model = 'changed';
        edited.prompt_stack[0]!.text = 'New instructions';
        expect(source.model_settings.model).toBe('original');
        expect(source.prompt_stack[0]!.text).toBe('');
        expect(edited.model_settings.temperature).toBe(0.3);
        expect(edited.lifecycle).toBe('draft');
    });
});

describe('Agent tool choices', () => {
    it('makes the web search dependency visible in the saved tool selection', () => {
        const tools = changeAgentTool([], ToolEnum.WEB_SEARCH, true);
        expect(tools).toEqual([ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION]);
        expect(changeAgentTool(tools, ToolEnum.WEB_SEARCH, true)).toHaveLength(2);
    });
    it('disables web search when permission to read links is removed', () => {
        expect(
            changeAgentTool(
                [ToolEnum.WEB_SEARCH, ToolEnum.LINK_EXTRACTION, ToolEnum.EXECUTE_CODE],
                ToolEnum.LINK_EXTRACTION,
                false,
            ),
        ).toEqual([ToolEnum.EXECUTE_CODE]);
    });
    it('preserves other permissions and never changes the source array', () => {
        const original = [ToolEnum.ASK_USER];
        expect(changeAgentTool(original, ToolEnum.IMAGE_GENERATION, true)).toEqual([
            ToolEnum.ASK_USER,
            ToolEnum.IMAGE_GENERATION,
        ]);
        expect(original).toEqual([ToolEnum.ASK_USER]);
    });
});
