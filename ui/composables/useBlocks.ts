import { NodeTypeEnum } from '@/types/enums';
import type { BlockDefinition, BlockCategories } from '@/types/graph';

const { generateId } = useUniqueId();

let blockDefinitions: ComputedRef<BlockCategories> | null = null;
let blockMap: ComputedRef<Map<string, BlockDefinition>> | null = null;

// The composable function acts as an initializer and an accessor
export function useBlocks() {
    // On the first call, `blockDefinitions` will be null, so we create it
    if (!blockDefinitions) {
        const globalSettingsStore = useSettingsStore();
        const { modelsSettings, blockParallelizationSettings, blockRoutingSettings } =
            storeToRefs(globalSettingsStore);

        blockDefinitions = computed<BlockCategories>(() => {
            const defaultModel = modelsSettings.value?.defaultModel ?? null;
            const parallelModels = blockParallelizationSettings.value?.models ?? [];
            const aggregator = blockParallelizationSettings.value?.aggregator ?? {};
            const routingGroups = blockRoutingSettings.value?.routeGroups ?? [];

            return {
                input: [
                    {
                        id: 'primary-prompt-text',
                        name: 'Prompt',
                        desc: 'In this block, you can enter a prompt to be sent to the LLM.',
                        icon: 'MaterialSymbolsEditNoteOutlineRounded',
                        nodeType: NodeTypeEnum.PROMPT,
                        defaultData: { prompt: '' },
                        minSize: { width: 500, height: 200 },
                        color: 'var(--color-slate-blue)',
                    },
                    {
                        id: 'primary-prompt-file',
                        name: 'Attachment',
                        desc: 'In this block, you can upload a file to be used as a prompt for the LLM.',
                        icon: 'MajesticonsAttachment',
                        nodeType: NodeTypeEnum.FILE_PROMPT,
                        defaultData: { files: [] },
                        minSize: { width: 500, height: 275 },
                        forcedInitialDimensions: true,
                        color: 'var(--color-dried-heather)',
                    },
                    {
                        id: 'primary-github-context',
                        name: 'GitHub',
                        desc: 'In this block, you can provide context from a GitHub repository to be used as a prompt for the LLM.',
                        icon: 'MdiGithub',
                        nodeType: NodeTypeEnum.GITHUB,
                        defaultData: { repo: undefined, files: [] },
                        minSize: { width: 500, height: 250 },
                        forcedInitialDimensions: true,
                        color: 'var(--color-github)',
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
                            model: defaultModel,
                            reply: '',
                        },
                        minSize: { width: 600, height: 300 },
                        color: 'var(--color-olive-grove)',
                    },
                    {
                        id: 'primary-model-parallelization',
                        name: 'Parallelization',
                        desc: 'In this block, the user prompt is passed into multiple models in parallel, their answers are then all sent to a final LLM call to be aggregated for the final answer.',
                        icon: 'HugeiconsDistributeHorizontalCenter',
                        nodeType: NodeTypeEnum.PARALLELIZATION,
                        defaultData: {
                            models: parallelModels.map(({ model }) => ({
                                model: model,
                                reply: '',
                                id: generateId(),
                                usageData: null,
                            })),
                            aggregator: {
                                prompt: aggregator.prompt ?? '',
                                model: aggregator.model ?? null,
                                reply: '',
                                usageData: null,
                            },
                            defaultModel: defaultModel,
                        },
                        minSize: { width: 660, height: 450 },
                        forcedInitialDimensions: true,
                        color: 'var(--color-terracotta-clay)',
                    },
                    {
                        id: 'primary-model-routing',
                        name: 'Routing',
                        desc: 'In this block, you can route the user prompt to different models based on conditions, allowing for dynamic model selection.',
                        icon: 'MaterialSymbolsAltRouteRounded',
                        nodeType: NodeTypeEnum.ROUTING,
                        defaultData: {
                            routeGroupId: routingGroups.find((group) => group.isDefault)?.id ?? '',
                            model: '',
                            reply: '',
                            selectedRouteId: '',
                        },
                        minSize: { width: 600, height: 300 },
                        color: 'var(--color-sunbaked-sand-dark)',
                    },
                ],
            };
        });

        // Also initialize the map singleton
        blockMap = computed(() => {
            const map = new Map<string, BlockDefinition>();
            for (const category of Object.values(blockDefinitions!.value)) {
                for (const block of category) {
                    map.set(block.id, block);
                }
            }
            return map;
        });
    }

    const getBlockById = (id: string): BlockDefinition | undefined => {
        const block = blockMap!.value.get(id);
        return block ? structuredClone(block) : undefined;
    };

    const getBlockByNodeType = (nodeType: NodeTypeEnum): BlockDefinition | undefined => {
        for (const block of blockMap!.value.values()) {
            if (block.nodeType === nodeType) {
                return structuredClone(block);
            }
        }
        return undefined;
    };

    const getBlockDefinitions = (): BlockCategories => {
        return structuredClone(blockDefinitions!.value);
    };

    return {
        blockDefinitions: blockDefinitions!,
        blockMap: blockMap!,

        getBlockById,
        getBlockByNodeType,
        getBlockDefinitions,
    };
}
