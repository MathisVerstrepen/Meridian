<script lang="ts" setup>
import { NodeTypeEnum, MessageRoleEnum } from '@/types/enums';

const props = defineProps<{
    data: any;
    nodeType: NodeTypeEnum;
    isStreaming?: boolean;
}>();

// --- Stores ---
const modelStore = useModelStore();

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;

console.log('data', props.data);
</script>

<template>
    <HeadlessDisclosure v-slot="{ open }" v-if="data">
        <HeadlessDisclosureButton
            class="bg-anthracite hover:bg-anthracite/75 mb-2 flex cursor-pointer items-center gap-2 rounded-lg px-4
                py-2 transition-colors duration-200 ease-in-out w-fit h-fit shrink-0"
            :class="{
                'animate-pulse': nodeType === NodeTypeEnum.STREAMING,
            }"
        >
            <UiIcon name="HugeiconsDistributeHorizontalCenter" class="text-soft-silk/80 h-4 w-4" />
            <span class="text-soft-silk/80 text-sm font-bold">From {{ data.length }} models</span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="text-soft-silk/80 h-4 w-4 transition-transform duration-200"
                :class="open ? 'rotate-0' : 'rotate-180'"
            />
        </HeadlessDisclosureButton>
        <HeadlessDisclosurePanel as="div" class="flex h-full max-w-full items-stretch gap-4 col-start-1 col-span-2">
            <div class="w-full px-2 py-2 sm:px-0">
                <HeadlessTabGroup>
                    <HeadlessTabList
                        class="bg-anthracite small_scrollbar flex space-x-1 overflow-x-auto rounded-xl p-1 w-full"
                    >
                        <HeadlessTab
                            v-for="model in data"
                            as="template"
                            :key="model.id"
                            v-slot="{ selected }"
                        >
                            <template v-for="modelInfo in [getModel(model.model)]">
                                <button
                                    class="ring-offset-terracotta-clay-dark w-52 shrink-0 cursor-pointer rounded-lg p-1 text-xs leading-5
                                        font-medium transition-colors duration-200 ease-in-out"
                                    :class="[
                                        selected
                                            ? 'bg-obsidian text-terracotta-clay shadow'
                                            : 'text-soft-silk hover:bg-soft-silk/10',
                                    ]"
                                >
                                    <div>
                                        <UiIcon
                                            :name="'models/' + modelInfo.icon"
                                            class="mr-1 h-4 w-4"
                                        />
                                        {{ modelInfo.name }}
                                    </div>
                                </button>
                            </template>
                        </HeadlessTab>
                    </HeadlessTabList>

                    <HeadlessTabPanels class="mt-2  w-full">
                        <HeadlessTabPanel
                            class="border-anthracite rounded-xl border-2 p-3  w-full"
                            v-for="model in data"
                            :key="model.id"
                        >
                            <UiChatMarkdownRenderer
                                :message="{
                                    role: MessageRoleEnum.assistant,
                                    content: model.reply,
                                    model: model.model,
                                    node_id: model.id,
                                    type: NodeTypeEnum.TEXT_TO_TEXT,
                                    data: null,
                                }"
                                :disableHighlight="false"
                                :editMode="false"
                            />

                            <UiChatMessageFooter
                                :message="{
                                    role: MessageRoleEnum.assistant,
                                    content: model.reply,
                                    model: model.model,
                                    node_id: model.id,
                                    type: NodeTypeEnum.TEXT_TO_TEXT,
                                    data: null,
                                }"
                                :isStreaming="false"
                                :isLastMessage="false"
                                @regenerate="() => {}"
                            />
                        </HeadlessTabPanel>
                    </HeadlessTabPanels>
                </HeadlessTabGroup>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>

<style scoped>
.small_scrollbar {
    scrollbar-width: thin;
}
.small_scrollbar::-webkit-scrollbar {
    width: 4px;
}
</style>
