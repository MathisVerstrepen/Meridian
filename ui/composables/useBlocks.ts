import { NodeTypeEnum } from '@/types/enums';
import type {
    BlockDefinition,
    BlockCategories,
    DataPrompt,
    DataTextToText,
    DataParallelization,
} from '@/types/graph';

const { generateId } = useUniqueId();

/**
 * Composable for working with blocks in the Meridian UI.
 *
 * @returns {Object} An object containing:
 * - blockDefinitions: A reactive reference to block definitions organized by category
 * - getBlockById: A function to retrieve a specific block definition by its ID
 */
export function useBlocks() {
    const globalSettingsStore = useSettingsStore();
    const { modelsSettings, blockParallelizationSettings } = storeToRefs(globalSettingsStore);

    const blockDefinitions = ref<BlockCategories>({
        input: [
            {
                id: 'primary-prompt-text',
                name: 'Prompt',
                desc: 'In this block, you can enter a prompt to be sent to the LLM.',
                icon: 'MaterialSymbolsEditNoteOutlineRounded',
                nodeType: NodeTypeEnum.PROMPT,
                defaultData: { prompt: '' } as DataPrompt,
                minSize: { width: 500, height: 200 },
            },
        ],
        generator: [
            {
                id: 'primary-model-text-to-text',
                name: 'Text to Text',
                desc: 'In this block, you can select a model, link it to the prompt, and generate a response.',
                icon: 'FluentCodeText16Filled',
                nodeType: NodeTypeEnum.TEXT_TO_TEXT,
                defaultData: {
                    model: modelsSettings.value.defaultModel,
                    reply: '',
                } as DataTextToText,
                minSize: { width: 600, height: 300 },
            },
            {
                id: 'primary-model-parallelization',
                name: 'Parallelization',
                desc: 'In this block, the user prompt is passed into multiple models in parallel, their answers are then all sent to a final LLM call to be aggregated for the final answer.',
                icon: 'HugeiconsDistributeHorizontalCenter',
                nodeType: NodeTypeEnum.PARALLELIZATION,
                defaultData: {
                    models: [
                        ...blockParallelizationSettings.value.models.map(({ model }) => ({
                            model,
                            reply: '',
                            id: generateId(),
                        })),
                    ],
                    aggregator: {
                        prompt: blockParallelizationSettings.value.aggregator.prompt,
                        model: blockParallelizationSettings.value.aggregator.model,
                        reply: '',
                    },
                    defaultModel: modelsSettings.value.defaultModel,
                } as DataParallelization,
                minSize: { width: 660, height: 450 },
            },
        ],
    });

    const getBlockById = (id: string): BlockDefinition | undefined => {
        for (const category in blockDefinitions.value) {
            const found = blockDefinitions.value[category].find((b) => b.id === id);
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
