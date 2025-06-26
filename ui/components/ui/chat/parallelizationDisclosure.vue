<script lang="ts" setup>
import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';

defineProps<{
    data: any;
    nodeType: NodeTypeEnum;
    isStreaming?: boolean;
}>();

// --- Stores ---
const modelStore = useModelStore();

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;
</script>

<template>
    <HeadlessDisclosure v-slot="{ open }" v-if="data">
        <HeadlessDisclosureButton
            class="bg-anthracite hover:bg-anthracite/75 mb-2 flex h-fit w-fit shrink-0 cursor-pointer items-center
                gap-2 rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
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
        <HeadlessDisclosurePanel
            as="div"
            class="col-span-2 col-start-1 flex h-full max-w-full items-stretch gap-4"
        >
            <div class="w-full px-2 py-2 sm:px-0">
                <HeadlessTabGroup>
                    <HeadlessTabList
                        class="bg-anthracite small_scrollbar flex w-full space-x-1 overflow-x-auto custom_scroll rounded-xl p-1"
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

                    <HeadlessTabPanels class="mt-2 w-full">
                        <HeadlessTabPanel
                            class="border-anthracite w-full rounded-xl border-2 p-3"
                            v-for="model in data"
                            :key="model.id"
                        >
                            <UiChatMarkdownRenderer
                                :message="{
                                    role: MessageRoleEnum.assistant,
                                    content: [
                                        {
                                            type: MessageContentTypeEnum.TEXT,
                                            text: model.reply,
                                        },
                                    ],
                                    model: model.model,
                                    node_id: model.id,
                                    type: NodeTypeEnum.TEXT_TO_TEXT,
                                    data: null,
                                    usageData: null,
                                }"
                                :editMode="false"
                            />

                            <UiChatMessageFooter
                                :message="{
                                    role: MessageRoleEnum.assistant,
                                    content: [
                                        {
                                            type: MessageContentTypeEnum.TEXT,
                                            text: model.reply,
                                        },
                                    ],
                                    model: model.model,
                                    node_id: model.id,
                                    type: NodeTypeEnum.TEXT_TO_TEXT,
                                    data: null,
                                    usageData: null,
                                }"
                                :isStreaming="false"
                                :isAssistantLastMessage="false"
                                :isUserLastMessage="false"
                                @regenerate="() => {}"
                            />
                        </HeadlessTabPanel>
                    </HeadlessTabPanels>
                </HeadlessTabGroup>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>