<script setup lang="ts">
import type { Node } from '@vue-flow/core';
import { ToolEnum } from '@/types/enums';

const props = defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
    availableTools?: ToolEnum[];
}>();

interface Tool {
    name: string;
    type: ToolEnum;
    icon: string;
    description: string;
    linkedTools?: ToolEnum[];
}

const TOOLS: Tool[] = [
    {
        name: 'Web Search',
        type: ToolEnum.WEB_SEARCH,
        icon: 'MdiWeb',
        description:
            'Websearch allows the node to perform web searches to gather up-to-date information.',
        linkedTools: [ToolEnum.LINK_EXTRACTION],
    },
    {
        name: 'Link Extraction',
        type: ToolEnum.LINK_EXTRACTION,
        icon: 'MdiLinkVariant',
        description:
            'Link Extraction enables the node to extract and process links from provided text or data sources.',
    },
    {
        name: 'Image Gen',
        type: ToolEnum.IMAGE_GENERATION,
        icon: 'MdiImageMultipleOutline',
        description: 'Image Generation allows the node to generate images based on prompts.',
    },
];

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
                :class="[
                    node.data.selectedTools?.includes(tool.type)
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
