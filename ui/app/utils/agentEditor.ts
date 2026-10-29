import type { AgentProfile } from '@/types/agent';
import { ToolEnum } from '@/types/enums';

export const AGENT_ICONS = [
    { icon: 'RiBrain2Line', label: 'Assistant' },
    { icon: 'FluentCodeText16Filled', label: 'Code' },
    { icon: 'MdiLinkVariant', label: 'Research' },
    { icon: 'MaterialSymbolsPaletteOutline', label: 'Design' },
    { icon: 'MaterialSymbolsImageRounded', label: 'Images' },
    { icon: 'MynauiSparklesSolid', label: 'Creative' },
];
export const AGENT_COLORS = ['#eb5e28', '#4f8c73', '#6788be', '#a17dc4', '#c1788d', '#bd984f'];

export const AGENT_TOOLS = [
    {
        value: ToolEnum.WEB_SEARCH,
        name: 'Web search',
        icon: 'MdiLinkVariant',
        description: 'Find current information and read the sources.',
    },
    {
        value: ToolEnum.LINK_EXTRACTION,
        name: 'Read links',
        icon: 'MdiLinkVariant',
        description: 'Open and read web pages you share.',
    },
    {
        value: ToolEnum.IMAGE_GENERATION,
        name: 'Images & video',
        icon: 'MaterialSymbolsImageRounded',
        description: 'Generate media and edit images.',
    },
    {
        value: ToolEnum.EXECUTE_CODE,
        name: 'Run code',
        icon: 'FluentCodeText16Filled',
        description: 'Calculate, analyze data, and run Python.',
    },
    {
        value: ToolEnum.VISUALISE,
        name: 'Create visuals',
        icon: 'MaterialSymbolsPaletteOutline',
        description: 'Explain ideas with diagrams and interactive visuals.',
    },
    {
        value: ToolEnum.ASK_USER,
        name: 'Ask questions',
        icon: 'LucideMessageCircleDashed',
        description: 'Pause and ask you for details when needed.',
    },
];

/** A valid, unique suggestion; a manually edited handle is managed by the editor. */
export function suggestAgentHandle(name: string, taken: readonly string[]): string {
    let base =
        name
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .replace(/[^a-z0-9_-]+/g, '-')
            .replace(/^-+|-+$/g, '') || 'agent';
    if (!/^[a-z]/.test(base)) base = `agent-${base}`;
    if (base.length < 2) base += '-agent';
    base = base.slice(0, 50);
    let handle = base;
    let suffix = 2;
    while (taken.includes(handle)) {
        const ending = `-${suffix++}`;
        handle = `${base.slice(0, 50 - ending.length)}${ending}`;
    }
    return handle;
}

export function createAgentDraft(defaultModel: string, source?: AgentProfile): AgentProfile {
    if (source) return structuredClone(source);
    return {
        name: '',
        handle: '',
        description: '',
        icon: 'RiBrain2Line',
        accentColor: '#eb5e28',
        lifecycle: 'active',
        visibility: 'private',
        category: 'General',
        tags: [],
        tools: [],
        prompt_stack: [{ name: 'Instructions', text: '', enabled: true }],
        model_settings: {
            model: defaultModel,
            reasoning_effort: null,
            exclude_reasoning: null,
            max_tokens: null,
            temperature: null,
            top_p: null,
            top_k: null,
            frequency_penalty: null,
            presence_penalty: null,
            repetition_penalty: null,
            structured_output: false,
            retry_count: 0,
            fallback_model: null,
        },
    };
}

export function changeAgentTool(
    tools: readonly ToolEnum[],
    tool: ToolEnum,
    enabled: boolean,
): ToolEnum[] {
    const next = new Set(tools);
    if (enabled) {
        next.add(tool);
        if (tool === ToolEnum.WEB_SEARCH) next.add(ToolEnum.LINK_EXTRACTION);
    } else {
        next.delete(tool);
        if (tool === ToolEnum.LINK_EXTRACTION) next.delete(ToolEnum.WEB_SEARCH);
    }
    return [...next];
}
