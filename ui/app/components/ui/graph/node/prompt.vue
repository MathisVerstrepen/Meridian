<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { NodeTypeEnum } from '@/types/enums';
import type { DataPrompt } from '@/types/graph';
import type { PromptTemplate } from '@/types/settings';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode', 'update:unlinkNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const { saveGraph } = useCanvasSaveStore();
const { searchNode, getPromptTemplates } = useAPI();
const nodeRegistry = useNodeRegistry();
const blockDefinition = getBlockById('primary-prompt-text');

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataPrompt>>();

// --- Local State ---
const templates = ref<PromptTemplate[]>([]);

// --- Computed Properties ---
const isTemplateMode = computed(() => !!props.data.templateId);

const selectedTemplate = computed(() => {
    return templates.value.find((t) => t.id === props.data.templateId);
});

const templateParts = computed(() => {
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

// --- Methods ---
const assemblePromptFromTemplate = () => {
    if (!isTemplateMode.value || !selectedTemplate.value) {
        return props.data.prompt;
    }
    return selectedTemplate.value.templateText.replace(
        /\{\{([a-zA-Z0-9_]+)\}\}/g,
        (_, varName) => props.data.templateVariables[varName] || '',
    );
};

const doneAction = async (generateNext: boolean) => {
    props.data.prompt = assemblePromptFromTemplate();

    await saveGraph();
    if (!generateNext) {
        emit('updateNodeInternals');
        return;
    }
    const nodes = await searchNode(graphId.value, props.id, 'downstream', [
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

const handleSelectTemplate = (template: PromptTemplate) => {
    props.data.templateId = template.id;

    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const matches = template.templateText.matchAll(regex);
    const variables = new Set(Array.from(matches, (m) => m[1]));

    const newVars: Record<string, string> = {};
    variables.forEach((v) => {
        newVars[v] = props.data.templateVariables?.[v] || '';
    });
    props.data.templateVariables = newVars;
    emit('updateNodeInternals');
};

const handleClearTemplate = () => {
    props.data.templateId = null;
    props.data.templateVariables = {};
    emit('updateNodeInternals');
};

const trimText = (text: string) => {
    const trimmedText = text.replace(/^\n+|\n+$/g, '');

    if (!(trimmedText.length > 100)) {
        return trimmedText;
    }

    const sliceStart = trimmedText.slice(0, 50);
    const sliceEnd = trimmedText.slice(-50);

    return sliceStart + ' ... ' + sliceEnd;
};

// --- Lifecycle Hooks ---
onMounted(async () => {
    templates.value = await getPromptTemplates();

    // Data migration for older nodes
    if (props.data.templateVariables === undefined) {
        props.data.templateVariables = {};
    }
    if (props.data.templateId === undefined) {
        props.data.templateId = null;
    }
});
</script>

<template>
    <NodeResizer
        :is-visible="props.selected"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="input"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        class="bg-slate-blue border-slate-blue-dark relative flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-slate-blue-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex w-fit items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span
                    class="dark:text-soft-silk/80 text-anthracite -translate-y-0.5 text-lg
                        font-bold"
                >
                    {{ blockDefinition?.name }}
                </span>
            </label>
            <div class="flex items-center gap-2">
                <button
                    v-if="isTemplateMode"
                    class="hover:bg-stone-gray/20 bg-stone-gray/10 text-soft-silk flex h-7
                        items-center gap-1 rounded-lg px-2 text-xs font-semibold transition-colors"
                    @click="handleClearTemplate"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    <span>Clear</span>
                </button>
                <UiGraphNodeUtilsTemplateSelector
                    :templates="templates"
                    :selected-template-id="props.data.templateId"
                    @select="handleSelectTemplate"
                />
            </div>
        </div>

        <!-- Standard Mode: Textarea for Prompt -->
        <UiGraphNodeUtilsTextarea
            v-if="!isTemplateMode"
            :reply="props.data.prompt"
            :readonly="false"
            color="slate-blue"
            placeholder="Enter your prompt here, or select a template."
            :autoscroll="false"
            :parse-error="false"
            @update:reply="(value: string) => (props.data.prompt = value)"
            @update:done-action="doneAction"
        />

        <!-- Template Mode: Rendered Template -->
        <div
            v-else
            class="custom_scroll nodrag nowheel flex h-full w-full flex-col gap-2 overflow-y-auto
                pr-1"
        >
            <template v-for="(part, index) in templateParts" :key="index">
                <p
                    v-if="part.type === 'text'"
                    class="dark:text-soft-silk/90 text-anthracite text-sm whitespace-pre-wrap"
                >
                    {{ trimText(part.content) }}
                </p>
                <div v-else-if="part.type === 'variable'" class="flex h-32 flex-col">
                    <label
                        class="text-anthracite/80 dark:text-soft-silk/60 mb-1 text-xs font-semibold"
                    >
                        {{ trimText(part.content) }}
                    </label>
                    <UiGraphNodeUtilsTextarea
                        :reply="props.data.templateVariables[part.content]"
                        :readonly="false"
                        color="slate-blue"
                        :placeholder="`Value for ${part.content}...`"
                        :autoscroll="false"
                        :parse-error="false"
                        @update:reply="
                            (value: string) => (props.data.templateVariables[part.content] = value)
                        "
                        @update:done-action="doneAction"
                    />
                </div>
            </template>
        </div>
    </div>

    <UiGraphNodeUtilsHandlePrompt :id="props.id" type="target" :is-dragging="props.dragging" is-visible />
    <UiGraphNodeUtilsHandlePrompt :id="props.id" type="source" :is-dragging="props.dragging" is-visible />
</template>
