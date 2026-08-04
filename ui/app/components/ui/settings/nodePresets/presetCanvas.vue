<script setup lang="ts">
import { ConnectionMode, VueFlow, useVueFlow, type Connection } from '@vue-flow/core';

import { useNodePresetEditor } from '@/composables/useNodePresetEditor';
import type { NodePreset } from '@/types/nodePresets';

const props = defineProps<{
    preset: NodePreset;
    freePlan: boolean;
}>();

const flowId = `node-preset-${props.preset.id}`;
const editor = useNodePresetEditor({ preset: toRef(props, 'preset'), flowId });
const { onConnect } = useVueFlow(flowId);

onConnect((connection: Connection) => editor.connect(connection));

const onKeydown = (event: KeyboardEvent) => {
    if (event.key !== 'Delete' && event.key !== 'Backspace') return;
    const target = event.target as HTMLElement | null;
    if (target?.matches('input, textarea, select, [contenteditable="true"]')) return;
    const selected = editor.getNodes.value.filter((node) => node.selected);
    if (selected.length === 0) return;
    event.preventDefault();
    selected.forEach((node) => editor.removeNode(node.id));
};

defineExpose({ flush: editor.flush, addBlock: editor.addBlock });
</script>

<template>
    <section class="border-stone-gray/15 bg-obsidian/35 flex min-h-[420px] min-w-0 flex-col overflow-hidden rounded-xl border lg:h-full lg:min-h-0">
        <div class="border-stone-gray/15 flex flex-wrap items-center gap-2 border-b px-3 py-2">
            <button type="button" class="bg-stone-gray/10 text-soft-silk rounded-lg px-2.5 py-1.5 text-xs font-semibold" @click="editor.createGroup()">
                Group selection
            </button>
            <button type="button" class="bg-stone-gray/10 text-soft-silk rounded-lg px-2.5 py-1.5 text-xs font-semibold" @click="editor.fit()">
                Fit view
            </button>
            <span class="text-stone-gray/55 ml-auto text-xs">Drag, resize, connect, select, or delete blocks</span>
        </div>

        <div class="relative min-h-[360px] flex-1 lg:min-h-0" tabindex="0" aria-label="Node preset canvas" @keydown="onKeydown">
            <VueFlow
                :id="flowId"
                :connection-mode="ConnectionMode.Strict"
                :min-zoom="0.1"
                :max-zoom="1.5"
                :fit-view-on-init="false"
                :delete-key-code="null"
                :connection-radius="40"
                :is-valid-connection="editor.canConnect"
            >
                <UiGraphBackground pattern-color="var(--color-stone-gray)" :gap="16" />

                <template #connection-line="connectionProps">
                    <UiGraphEdgesCustomConnectionLine v-bind="connectionProps" />
                </template>
                <template #node-prompt="nodeProps">
                    <UiGraphNodePrompt v-bind="nodeProps" preset-editor @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-filePrompt="nodeProps">
                    <UiGraphNodeFilePrompt v-bind="nodeProps" preset-editor @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-github="nodeProps">
                    <UiGraphNodeGithub v-bind="nodeProps" preset-editor @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-textToText="nodeProps">
                    <UiGraphNodeTextToText v-bind="nodeProps" preset-editor :is-graph-name-default="false" @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-parallelization="nodeProps">
                    <UiGraphNodeParallelization v-bind="nodeProps" preset-editor :is-graph-name-default="false" @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-routing="nodeProps">
                    <UiGraphNodeRouting v-bind="nodeProps" preset-editor :is-graph-name-default="false" @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-contextMerger="nodeProps">
                    <UiGraphNodeContextMerger v-bind="nodeProps" preset-editor @update:delete-node="editor.removeNode" @update:unlink-node="editor.unlinkNode" />
                </template>
                <template #node-group="nodeProps">
                    <UiGraphNodeGroup v-bind="nodeProps" preset-editor @update:delete-node="editor.deleteGroup" />
                </template>
                <template #edge-custom="edgeProps">
                    <UiGraphEdgesEdgeCustom v-bind="edgeProps" @update:remove-edges="editor.removeEdge" />
                </template>
            </VueFlow>

            <UiSettingsNodePresetsPresetPalette
                :node-count="editor.getNodes.value.length"
                :free-plan="freePlan"
                @add="editor.addBlock($event, freePlan)"
            />
        </div>

        <div v-if="editor.actionMessage.value || editor.validationIssues.value.length" class="border-stone-gray/15 border-t px-3 py-2 text-xs text-red-400" role="alert">
            <p v-if="editor.actionMessage.value">{{ editor.actionMessage.value }}</p>
            <p v-for="issue in editor.validationIssues.value.slice(0, 3)" :key="`${issue.path.join('.')}-${issue.code}`">
                {{ issue.path.join('.') || 'preset' }}: {{ issue.message }}
            </p>
        </div>
    </section>
</template>
