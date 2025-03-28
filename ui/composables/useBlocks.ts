export interface BlockDefinition {
    id: string;
    name: string;
    desc: string;
    icon: string;
    nodeType: string;
    defaultData?: Record<string, any>;
}

export interface BlockCategories {
    [category: string]: BlockDefinition[];
}

const blockDefinitions = ref<BlockCategories>({
    input: [
        {
            id: "primary-prompt-text",
            name: "Prompt",
            desc: "In this block, you can enter a prompt to be sent to the LLM.",
            icon: "material-symbols:text-fields-rounded",
            nodeType: "prompt",
            defaultData: { prompt: "New Prompt" },
        },
    ],
    output: [
        {
            id: "primary-model-text-to-text",
            name: "Text to Text",
            desc: "In this block, you can select a model, link it to the prompt, and generate a response.",
            icon: "fluent:code-text-16-filled",
            nodeType: "textToText",
            defaultData: { model: "default-model" },
        },
    ],
});

export function useBlocks() {
    const getBlockById = (id: string): BlockDefinition | undefined => {
        for (const category in blockDefinitions.value) {
            const found = blockDefinitions.value[category].find(
                (b) => b.id === id
            );
            if (found) {
                return found;
            }
        }
        return undefined;
    };

    return {
        blockDefinitions,
        getBlockById,
    };
}
