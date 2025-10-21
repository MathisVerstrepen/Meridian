<script lang="ts" setup>
import { ToolEnum } from '@/types/enums';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { toolsSettings } = storeToRefs(settingsStore);

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
        description: 'Allows the model to perform web searches to gather up-to-date information.',
        linkedTools: [ToolEnum.LINK_EXTRACTION],
    },
    {
        name: 'Link Extraction',
        type: ToolEnum.LINK_EXTRACTION,
        icon: 'MdiLinkVariant',
        description:
            'Enables the model to extract and process links from provided text or data sources.',
    },
];

const toggleLinkedTools = (toolType: ToolEnum, enable: boolean) => {
    const updateSelectedTools = (type: ToolEnum, enable: boolean) => {
        if (!toolsSettings.value.defaultSelectedTools) {
            toolsSettings.value.defaultSelectedTools = [];
        }
        const selectedTools = toolsSettings.value.defaultSelectedTools;
        const index = selectedTools.indexOf(type);

        if (enable && index === -1) {
            selectedTools.push(type);
        } else if (!enable && index > -1) {
            selectedTools.splice(index, 1);
        }
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
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Default selected tools -->
        <div class="py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Selected Tools</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose which tools are selected by default when you start a new conversation.
                </p>
            </div>
            <div class="mt-6 flex flex-wrap gap-3 px-1">
                <template v-for="tool in TOOLS" :key="tool.type">
                    <button
                        class="group relative flex h-16 w-32 cursor-pointer flex-col items-center
                            justify-center gap-1 rounded-lg p-2 text-center text-sm font-bold ring-2
                            transition-all duration-200 ease-in-out"
                        :title="tool.description"
                        :class="[
                            toolsSettings.defaultSelectedTools?.includes(tool.type)
                                ? 'bg-ember-glow/10 ring-ember-glow text-ember-glow'
                                : `bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk/80
                                    hover:text-soft-silk/90 ring-stone-gray/20
                                    hover:ring-stone-gray/40`,
                        ]"
                        @click="
                            toggleLinkedTools(
                                tool.type,
                                !toolsSettings.defaultSelectedTools?.includes(tool.type),
                            )
                        "
                    >
                        <UiIcon :name="tool.icon" class="h-5 w-5" />
                        {{ tool.name }}
                    </button>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
