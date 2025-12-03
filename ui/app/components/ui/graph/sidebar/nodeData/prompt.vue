<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import { NodeTypeEnum } from '@/types/enums';
import type { PromptTemplate } from '@/types/settings';

const props = defineProps<{
    node: Node;
    graphId: string;
    setNodeDataKey: (key: string, value: unknown) => void;
}>();

// --- Composables ---
const { saveGraph } = useCanvasSaveStore();
const { searchNode, getPromptTemplates } = useAPI();
const nodeRegistry = useNodeRegistry();

// --- State ---
const templates = ref<PromptTemplate[]>([]);

// --- Computed ---
const isTemplateMode = computed(() => !!props.node.data.templateId);

const selectedTemplate = computed(() => {
    return templates.value.find((t) => t.id === props.node.data.templateId);
});

const templatePreviewParts = computed(() => {
    if (!selectedTemplate.value) return [];
    const text = selectedTemplate.value.templateText;
    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
        }
        parts.push({ type: 'variable', content: match[1] });
        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push({ type: 'text', content: text.slice(lastIndex) });
    }
    return parts;
});

const uniqueVariables = computed(() => {
    if (!selectedTemplate.value) return [];
    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const matches = selectedTemplate.value.templateText.matchAll(regex);
    return Array.from(new Set(Array.from(matches, (m) => m[1])));
});

// --- Methods ---
const updateVariable = (key: string, value: string) => {
    const currentVars = props.node.data.templateVariables || {};
    const newVars = { ...currentVars, [key]: value };
    props.setNodeDataKey('templateVariables', newVars);
};

const assemblePromptFromTemplate = () => {
    if (!selectedTemplate.value) return '';
    const vars = props.node.data.templateVariables || {};
    return selectedTemplate.value.templateText.replace(
        /\{\{([a-zA-Z0-9_]+)\}\}/g,
        (_, varName) => vars[varName] || '',
    );
};

const doneAction = async (generateNext: boolean) => {
    if (isTemplateMode.value) {
        props.setNodeDataKey('prompt', assemblePromptFromTemplate());
    }

    await saveGraph();

    if (!generateNext) {
        return;
    }
    const nodes = await searchNode(props.graphId, props.node.id, 'downstream', [
        NodeTypeEnum.PARALLELIZATION,
        NodeTypeEnum.ROUTING,
        NodeTypeEnum.TEXT_TO_TEXT,
    ]);
    const jobs = [];
    for (const node of nodes) {
        jobs.push(nodeRegistry.execute(node));
    }
    await Promise.all(jobs);
};

// --- Lifecycle ---
onMounted(async () => {
    templates.value = await getPromptTemplates();
});
</script>

<template>
    <div class="flex min-h-0 flex-1 flex-col space-y-4">
        <!-- Template Mode -->
        <template v-if="isTemplateMode && selectedTemplate">
            <div class="flex flex-col space-y-2">
                <!-- Template Info Header -->
                <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Template Info
                </h3>
                <div
                    class="bg-obsidian/30 border-stone-gray/10 flex flex-col gap-2 rounded-xl border
                        p-3"
                >
                    <div class="flex items-center gap-2">
                        <div
                            class="bg-ember-glow/10 flex h-6 w-6 items-center justify-center
                                rounded"
                        >
                            <UiIcon
                                name="MaterialSymbolsTextSnippetOutlineRounded"
                                class="text-ember-glow h-4 w-4"
                            />
                        </div>
                        <span class="text-soft-silk truncate text-sm font-bold">
                            {{ selectedTemplate.name }}
                        </span>
                    </div>
                    <p
                        v-if="selectedTemplate.description"
                        class="text-stone-gray px-1 text-xs leading-relaxed"
                    >
                        {{ selectedTemplate.description }}
                    </p>
                </div>
            </div>

            <!-- Template Preview -->
            <div class="flex shrink-0 flex-col gap-2">
                <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Preview
                </h3>
                <div
                    class="bg-stone-gray/5 border-stone-gray/10 custom_scroll max-h-32
                        overflow-y-auto rounded-xl border p-3"
                >
                    <div
                        class="text-soft-silk/90 font-mono text-xs leading-relaxed
                            whitespace-pre-wrap"
                    >
                        <template v-for="(part, index) in templatePreviewParts" :key="index">
                            <span v-if="part.type === 'text'">{{ part.content }}</span>
                            <span
                                v-else-if="part.type === 'variable'"
                                class="bg-ember-glow/10 text-ember-glow mx-0.5 rounded px-1 py-0.5
                                    font-bold"
                            >
                                {{ part.content }}
                            </span>
                        </template>
                    </div>
                </div>
            </div>

            <!-- Variables Editor -->
            <div class="flex min-h-0 flex-1 flex-col gap-2">
                <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Variables
                </h3>
                <div class="custom_scroll -mr-2 flex flex-col gap-3 overflow-y-auto py-2 pr-2">
                    <div
                        v-for="varName in uniqueVariables"
                        :key="varName"
                        class="flex flex-col gap-2 rounded-xl"
                    >
                        <div class="flex items-center justify-between px-1">
                            <span
                                class="text-stone-gray/60 ml-1 text-[10px] font-bold tracking-widest
                                    uppercase"
                                >{{ varName }}</span
                            >
                            <UiIcon name="MdiVariable" class="text-stone-gray/50 h-4 w-4" />
                        </div>
                        <UiGraphNodeUtilsTextarea
                            :reply="props.node.data.templateVariables?.[varName] || ''"
                            :readonly="false"
                            color="grey"
                            :placeholder="`Value for ${varName}...`"
                            :autoscroll="false"
                            :parse-error="false"
                            class="min-h-[100px]"
                            @update:reply="(val) => updateVariable(varName, val)"
                            @update:done-action="doneAction"
                        />
                    </div>
                </div>
            </div>
        </template>

        <!-- Manual Mode (Fallback) -->
        <template v-else>
            <div class="flex min-h-0 flex-1 flex-col space-y-2">
                <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
                    Original Prompt
                </h3>
                <UiGraphNodeUtilsTextarea
                    class="grow"
                    :reply="node.data.prompt"
                    :readonly="false"
                    color="grey"
                    placeholder="Enter your prompt here"
                    :autoscroll="false"
                    :parse-error="false"
                    @update:reply="(value: string) => setNodeDataKey('prompt', value)"
                    @update:done-action="doneAction"
                />
            </div>
        </template>
    </div>
</template>

<style scoped></style>
