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
            defaultData: { prompt: "" },
        },
    ],
    output: [
        {
            id: "primary-model-text-to-text",
            name: "Text to Text",
            desc: "In this block, you can select a model, link it to the prompt, and generate a response.",
            icon: "fluent:code-text-16-filled",
            nodeType: "textToText",
            defaultData: { model: "google/gemini-2.0-flash-001" },
        },
    ],
});

/**
 * Composable for working with blocks in the Meridian UI.
 * 
 * @returns {Object} An object containing:
 * - blockDefinitions: A reactive reference to block definitions organized by category
 * - getBlockById: A function to retrieve a specific block definition by its ID
 */
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
