import { ToolEnum } from '@/types/enums';

export interface ToolDefinition {
    name: string;
    type: ToolEnum;
    icon: string;
    description: string;
    linkedTools?: ToolEnum[];
    toolCallNames: string[];
}

export const TOOLS: ToolDefinition[] = [
    {
        name: 'Web Search',
        type: ToolEnum.WEB_SEARCH,
        icon: 'MdiWeb',
        description: 'Allows the model to perform web searches to gather up-to-date information.',
        linkedTools: [ToolEnum.LINK_EXTRACTION],
        toolCallNames: ['web_search'],
    },
    {
        name: 'Link Extraction',
        type: ToolEnum.LINK_EXTRACTION,
        icon: 'MdiLinkVariant',
        description:
            'Enables the model to extract and process links from provided text or data sources.',
        toolCallNames: ['link_extraction', 'fetch_page_content'],
    },
    {
        name: 'Image Gen',
        type: ToolEnum.IMAGE_GENERATION,
        icon: 'MdiImageMultipleOutline',
        description: 'Allows the model to generate images from prompts.',
        toolCallNames: ['image_generation', 'generate_image'],
    },
    {
        name: 'Execute Code',
        type: ToolEnum.EXECUTE_CODE,
        icon: 'MaterialSymbolsTerminalRounded',
        description:
            'Runs self-contained Python snippets in a sandbox for exact computation, debugging, and verification.',
        toolCallNames: ['execute_code'],
    },
    {
        name: 'Visualise',
        type: ToolEnum.VISUALISE,
        icon: 'MaterialSymbolsBarChartRounded',
        description:
            'Delegates Mermaid, SVG, and HTML visual generation to dedicated models for diagrams, charts, and interactive explainers.',
        toolCallNames: ['visualise'],
    },
    {
        name: 'Ask User',
        type: ToolEnum.ASK_USER,
        icon: 'LucideMessageCircleDashed',
        description:
            'Lets the model pause and ask the user one structured clarifying question before continuing.',
        toolCallNames: ['ask_user'],
    },
];

export const getToolDefinitionByToolCallName = (toolCallName: string | null | undefined) => {
    if (!toolCallName) return undefined;
    return TOOLS.find((tool) => tool.toolCallNames.includes(toolCallName));
};
