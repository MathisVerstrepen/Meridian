<script setup lang="ts">
import { TOOLS } from '@/constants/tools';
import type { ToolEnum } from '@/types/enums';
import type { DataRouting, DataTextToText, SidebarNode } from '@/types/graph';

const props = defineProps<{
    node: SidebarNode<DataRouting | DataTextToText>;
    setNodeDataKey: (key: string, value: unknown) => void;
    availableTools?: ToolEnum[];
    disabled?: boolean;
}>();

const toggleLinkedTools = (toolType: ToolEnum, enable: boolean) => {
    const updateSelectedTools = (type: ToolEnum, enable: boolean) => {
        const selectedTools = props.node.data.selectedTools || [];
        const index = selectedTools.indexOf(type);

        if (enable && index === -1) {
            selectedTools.push(type);
        } else if (!enable && index > -1) {
            selectedTools.splice(index, 1);
        }

        props.setNodeDataKey('selectedTools', selectedTools);
    };

    const tool = TOOLS.find((t) => t.type === toolType);
    if (!tool) return;

    if (tool.linkedTools) {
        tool.linkedTools.forEach((linkedToolType) => {
            updateSelectedTools(linkedToolType, enable);
        });
    }

    updateSelectedTools(tool.type, enable);
};
</script>

<template>
    <div class="mt-1 grid grid-cols-3 gap-3">
        <template v-for="tool in TOOLS" :key="tool.type">
            <button
                v-if="availableTools?.includes(tool.type)"
                class="group relative flex h-16 w-full cursor-pointer flex-col items-center
                    justify-center gap-1 rounded-lg p-2 text-center text-sm font-bold ring-2
                    transition-all duration-200 ease-in-out"
                :title="tool.description"
                :disabled="disabled"
                :class="[
                    disabled
                        ? 'bg-stone-gray/5 text-stone-gray/45 ring-stone-gray/10 cursor-not-allowed opacity-60'
                        : node.data.selectedTools?.includes(tool.type)
                        ? 'bg-ember-glow/10 ring-ember-glow text-ember-glow'
                        : `bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk/80
                            hover:text-soft-silk/90 ring-stone-gray/20 hover:ring-stone-gray/40`,
                ]"
                @click="toggleLinkedTools(tool.type, !node.data.selectedTools?.includes(tool.type))"
            >
                <UiIcon :name="tool.icon" class="h-5 w-5" />
                {{ tool.name }}
            </button>
        </template>
    </div>
</template>

<style scoped></style>
