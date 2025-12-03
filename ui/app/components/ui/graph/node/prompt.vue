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
const { nodeRef, isVisible } = useNodeVisibility();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataPrompt>>();

// --- Local State ---
const templates = ref<PromptTemplate[]>([]);
const minHeight = ref(blockDefinition?.minSize?.height);

// --- Computed Properties ---
const isTemplateMode = computed(() => !!props.data.templateId);

const selectedTemplate = computed(() => {
    return templates.value.find((t) => t.id === props.data.templateId);
});

// Parses the template into parts for the Preview display
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

// Extracts unique variables for the Form display
const uniqueVariables = computed(() => {
    if (!selectedTemplate.value) return [];
    const regex = /\{\{([a-zA-Z0-9_]+)\}\}/g;
    const matches = selectedTemplate.value.templateText.matchAll(regex);
    return Array.from(new Set(Array.from(matches, (m) => m[1])));
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

    minHeight.value = Math.max(minHeight.value || 0, 200 + variables.size * 120);

    emit('updateNodeInternals');
};

const handleClearTemplate = () => {
    props.data.templateId = null;
    props.data.templateVariables = {};
    emit('updateNodeInternals');
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
        :min-height="minHeight"
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
        ref="nodeRef"
        class="bg-slate-blue border-slate-blue-dark relative flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-slate-blue-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-3 flex w-full items-center justify-between">
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
            <div v-if="isVisible" class="flex items-center gap-2">
                <button
                    v-if="isTemplateMode"
                    class="hover:bg-stone-gray/10 hover:text-soft-silk text-stone-gray flex h-7
                        items-center gap-1 rounded-lg px-2 text-xs font-semibold transition-colors"
                    title="Clear Template"
                    @click="handleClearTemplate"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
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

        <!-- Template Mode: Split View (Preview + Form) -->
        <div
            v-else-if="isVisible"
            class="nodrag nowheel flex h-full w-full flex-col gap-4 overflow-hidden"
        >
            <!-- Variables Form Section -->
            <div
                v-if="uniqueVariables.length > 0"
                class="custom_scroll flex min-h-[80px] shrink-0 flex-col gap-3 overflow-y-auto pr-1"
            >
                <div
                    v-for="varName in uniqueVariables"
                    :key="varName"
                    class="bg-slate-blue-dark/30 flex flex-col gap-1.5 rounded-xl p-2"
                >
                    <div class="flex items-center justify-between px-1">
                        <label class="text-soft-silk/80 text-xs font-bold tracking-wide">
                            {{ varName }}
                        </label>
                        <span class="text-stone-gray text-[10px]">Variable</span>
                    </div>
                    <div class="relative w-full">
                        <UiGraphNodeUtilsTextarea
                            :reply="props.data.templateVariables[varName]"
                            :readonly="false"
                            color="slate-blue"
                            :placeholder="`Enter value for ${varName}...`"
                            :autoscroll="false"
                            :parse-error="false"
                            class="min-h-[60px]"
                            @update:reply="
                                (value: string) => (props.data.templateVariables[varName] = value)
                            "
                            @update:done-action="doneAction"
                        />
                    </div>
                </div>
            </div>

            <!-- Preview Section -->
            <div
                class="bg-stone-gray/10 border-stone-gray/10 dark-scrollbar group
                    hover:border-stone-gray/20 relative h-full overflow-y-auto rounded-xl border p-3
                    transition-colors"
            >
                <div
                    class="text-soft-silk/90 font-mono text-xs leading-relaxed whitespace-pre-wrap"
                >
                    <template v-for="(part, index) in templatePreviewParts" :key="index">
                        <span v-if="part.type === 'text'">{{ part.content }}</span>
                        <span
                            v-else-if="part.type === 'variable'"
                            class="text-soft-silk/75 rounded bg-black/20 px-1.5 py-1 text-[10px]
                                font-bold tracking-wider uppercase"
                        >
                            {{ part.content }}
                        </span>
                    </template>
                </div>
                <div
                    class="absolute top-2 right-2 rounded bg-black/20 px-1.5 py-0.5 text-[10px]
                        font-bold tracking-wider text-white/40 uppercase backdrop-blur-sm"
                >
                    Preview
                </div>
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandlePrompt
        :id="props.id"
        type="target"
        :is-dragging="props.dragging"
        is-visible
    />
    <UiGraphNodeUtilsHandlePrompt
        :id="props.id"
        type="source"
        :is-dragging="props.dragging"
        is-visible
    />
</template>
