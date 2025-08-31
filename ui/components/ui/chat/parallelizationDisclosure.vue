<script lang="ts" setup>
import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';

defineProps<{
    data: Record<
        string,
        {
            id: string;
            model: string;
            reply: string;
        }
    >;
    nodeType: NodeTypeEnum;
    isStreaming?: boolean;
}>();

// --- Stores ---
const modelStore = useModelStore();

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;
</script>

<template>
    <HeadlessDisclosure v-if="data" v-slot="{ open }">
        <HeadlessDisclosureButton
            class="dark:bg-anthracite bg-anthracite/20 dark:hover:bg-anthracite/75 hover:bg-anthracite/40 text-obsidian
                dark:text-soft-silk/80 mb-2 flex h-fit w-fit shrink-0 cursor-pointer items-center gap-2 rounded-lg
                px-4 py-2 transition-colors duration-200 ease-in-out"
            :class="{
                'animate-pulse': nodeType === NodeTypeEnum.STREAMING,
            }"
        >
            <UiIcon name="HugeiconsDistributeHorizontalCenter" class="h-4 w-4" />
            <span class="text-sm font-bold">From {{ data.length }} models</span>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="h-4 w-4 transition-transform duration-200"
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
                        class="dark:bg-anthracite bg-anthracite/20 small_scrollbar custom_scroll flex w-full space-x-1
                            overflow-x-auto rounded-xl p-1"
                    >
                        <HeadlessTab
                            v-for="model in data"
                            :key="model.id"
                            v-slot="{ selected }"
                            as="template"
                        >
                            <template
                                v-for="modelInfo in [getModel(model.model)]"
                                :key="modelInfo.id"
                            >
                                <button
                                    class="ring-offset-ember-glow/80 w-52 shrink-0 cursor-pointer rounded-lg p-1 text-xs leading-5 font-medium
                                        transition-colors duration-200 ease-in-out"
                                    :class="[
                                        selected
                                            ? 'dark:bg-obsidian bg-soft-silk/80 text-ember-glow/80 shadow'
                                            : 'dark:text-soft-silk text-obsidian hover:bg-soft-silk/10',
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
                            v-for="model in data"
                            :key="model.id"
                            class="dark:border-anthracite border-anthracite/20 w-full rounded-xl border-2 p-3"
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
                                :edit-mode="false"
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
                                :is-streaming="false"
                                :is-assistant-last-message="false"
                                :is-user-last-message="false"
                                @regenerate="() => {}"
                            />
                        </HeadlessTabPanel>
                    </HeadlessTabPanels>
                </HeadlessTabGroup>
            </div>
        </HeadlessDisclosurePanel>
    </HeadlessDisclosure>
</template>
