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
const { searchNode } = useAPI();
const { success } = useToast();
const nodeRegistry = useNodeRegistry();
const blockDefinition = getBlockById('primary-prompt-text');
const { nodeRef, isVisible } = useNodeVisibility();
const graphEvents = useGraphEvents();
const promptTemplateStore = usePromptTemplateStore();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataPrompt>>();

// --- Local State ---
const minHeight = ref(blockDefinition?.minSize?.height);
const extraTemplate = ref<PromptTemplate | null>(null);

// --- Computed Properties ---
const isTemplateMode = computed(() => !!props.data.templateId);

const templates = computed(() => {
    const base = promptTemplateStore.allAvailableTemplates;

    if (extraTemplate.value && !base.find((t) => t.id === extraTemplate.value!.id)) {
        return [...base, extraTemplate.value];
    }
    return base;
});

const selectedTemplate = computed(() => {
    return templates.value.find((t) => t.id === props.data.templateId);
});

const isOwnedTemplate = computed(() => {
    if (!selectedTemplate.value) return false;
    return promptTemplateStore.userTemplates.some((t) => t.id === selectedTemplate.value?.id);
});

// Parses the template into parts for the Preview display
const templatePreviewParts = computed(() => {
    if (!selectedTemplate.value) return [];
    const text = selectedTemplate.value.templateText;
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
        }
        const content = match[2] ? `${match[1]}:${match[2]}` : match[1];
        parts.push({ type: 'variable', content });
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
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const matches = selectedTemplate.value.templateText.matchAll(regex);
    return Array.from(new Set(Array.from(matches, (m) => m[1])));
});

const variableDefaults = computed(() => {
    if (!selectedTemplate.value) return {};
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const matches = selectedTemplate.value.templateText.matchAll(regex);
    const defaults: Record<string, string> = {};
    for (const m of matches) {
        if (m[2]) defaults[m[1]] = m[2];
    }
    return defaults;
});

// --- Methods ---
const fetchTemplates = async (force = false) => {
    // Fetch both user and bookmarked templates
    await promptTemplateStore.fetchLibrary(force);

    // 2. If the node refers to a template NOT in the user's list (i.e., a public one),
    // we must fetch it specifically to hydrate the node correctly.
    if (props.data.templateId) {
        const exists = promptTemplateStore.allAvailableTemplates.find(
            (t) => t.id === props.data.templateId,
        );
        if (!exists) {
            const template = await promptTemplateStore.fetchTemplateById(props.data.templateId);
            if (template) {
                extraTemplate.value = template;
            }
        }
    }
};

const assemblePromptFromTemplate = () => {
    if (!isTemplateMode.value || !selectedTemplate.value) {
        return props.data.prompt;
    }
    return selectedTemplate.value.templateText.replace(
        /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g,
        (_, varName, defaultValue) => props.data.templateVariables[varName] || defaultValue || '',
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

const extractTemplateVariables = (template: PromptTemplate) => {
    const regex = /\{\{([a-zA-Z0-9_]+)(?::(.*?))?\}\}/g;
    const matches = template.templateText.matchAll(regex);
    const varsRecord: Record<string, string> = {};
    for (const m of matches) {
        const varName = m[1];
        const defaultValue = m[2] || '';
        varsRecord[varName] = defaultValue;
    }
    return varsRecord;
};

const handleSelectTemplate = (template: PromptTemplate) => {
    props.data.templateId = template.id;

    // If the selected template came from the marketplace (not in our list), add it to local extra
    if (!promptTemplateStore.allAvailableTemplates.find((t) => t.id === template.id)) {
        extraTemplate.value = template;
    }

    const variables = extractTemplateVariables(template);
    props.data.templateVariables = variables;
    props.data.prompt = assemblePromptFromTemplate();

    minHeight.value = Math.max(
        blockDefinition?.minSize?.height || 0,
        200 + Object.keys(variables).length * 110,
    );

    emit('updateNodeInternals');
};

const handleClearTemplate = () => {
    props.data.templateId = null;
    props.data.templateVariables = {};
    minHeight.value = Math.max(blockDefinition?.minSize?.height || 0, 200);
    emit('updateNodeInternals');
};

const handleEditTemplate = async () => {
    if (!selectedTemplate.value) return;

    if (isOwnedTemplate.value) {
        graphEvents.emit('open-prompt-template-editor', { template: selectedTemplate.value });
    } else {
        try {
            const newTemplate = await promptTemplateStore.forkTemplate(selectedTemplate.value);

            handleSelectTemplate(newTemplate);

            success('Template forked. You are now editing your copy.');
            graphEvents.emit('open-prompt-template-editor', { template: newTemplate });
        } catch (error) {
            console.error('Failed to fork template for editing:', error);
        }
    }
};

// --- Lifecycle Hooks ---
let unsubscribe: (() => void) | null = null;

onMounted(async () => {
    await fetchTemplates();
    unsubscribe = graphEvents.on('prompt-template-saved', () => fetchTemplates(true));

    // Data migration for older nodes
    if (props.data.templateVariables === undefined) {
        props.data.templateVariables = {};
    }
    if (props.data.templateId === undefined) {
        props.data.templateId = null;
    }

    minHeight.value = Math.max(
        blockDefinition?.minSize?.height || 0,
        200 + Object.keys(props.data.templateVariables).length * 110,
    );
});

onUnmounted(() => {
    unsubscribe?.();
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
            <div v-if="isVisible" class="flex items-center">
                <!-- Edit Button (New) -->
                <button
                    v-if="isTemplateMode"
                    class="hover:bg-stone-gray/10 hover:text-soft-silk text-stone-gray flex h-7
                        cursor-pointer items-center gap-1 rounded-lg px-1.5 text-xs font-bold
                        transition-colors"
                    :title="isOwnedTemplate ? 'Edit Template' : 'Fork & Edit Template'"
                    @click="handleEditTemplate"
                >
                    <UiIcon
                        :name="
                            isOwnedTemplate
                                ? 'MaterialSymbolsEditRounded'
                                : 'MaterialSymbolsForkRightRounded'
                        "
                        class="h-4 w-4"
                    />
                </button>

                <button
                    v-if="isTemplateMode"
                    class="hover:bg-stone-gray/10 hover:text-soft-silk text-stone-gray flex h-7
                        cursor-pointer items-center gap-1 rounded-lg px-1.5 text-xs font-semibold
                        transition-colors"
                    title="Clear Template"
                    @click="handleClearTemplate"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                </button>

                <UiGraphNodeUtilsTemplateSelector
                    :templates="templates"
                    :selected-template-id="props.data.templateId"
                    class="ml-2"
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
                class="dark-scrollbar flex min-h-[80px] shrink-0 flex-col overflow-y-auto pr-1"
            >
                <div
                    v-for="varName in uniqueVariables"
                    :key="varName"
                    class="flex flex-col gap-1.5 rounded-xl py-2"
                >
                    <div class="flex items-center justify-between px-1">
                        <label
                            class="text-soft-silk/80 ml-1 text-[10px] font-bold tracking-widest
                                uppercase"
                        >
                            {{ varName }}
                        </label>
                        <UiIcon name="MdiVariable" class="text-soft-silk/50 h-4 w-4" />
                    </div>
                    <div class="relative w-full">
                        <UiGraphNodeUtilsTextarea
                            :reply="props.data.templateVariables[varName]"
                            :readonly="false"
                            color="slate-blue"
                            :placeholder="
                                variableDefaults[varName]
                                    ? `Enter value (default: ${variableDefaults[varName]})...`
                                    : `Enter value for ${varName}...`
                            "
                            :autoscroll="false"
                            :parse-error="false"
                            class="min-h-[60px]"
                            resizable
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
