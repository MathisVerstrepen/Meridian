<script lang="ts" setup>
import type { Message, DataParallelizationModel } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';
import { motion } from 'motion-v';

interface UsageData {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost: number;
}

// --- Props ---
const props = defineProps<{
    message: Message;
}>();

// --- Composables ---
const { formatMessageCost } = useFormatters();

// --- State ---
const open = ref(false);
const usageDataTotal = computed(() => {
    // For parallelization, we combine usage data from all models
    if (props.message.type === NodeTypeEnum.PARALLELIZATION && props.message.data) {
        const modelsUsageData = props.message.data.map(
            (data: { usageData: unknown }) => data.usageData,
        );
        const aggregatorUsageData = props.message.usageData;
        const allUsageData = [...modelsUsageData, aggregatorUsageData];

        const filteredUsageData = allUsageData.filter(
            (data) => data !== null && data !== undefined,
        );

        // Sum all usage data
        return filteredUsageData.reduce(
            (acc: UsageData, curr: UsageData) => ({
                prompt_tokens: acc.prompt_tokens + curr.prompt_tokens,
                completion_tokens: acc.completion_tokens + curr.completion_tokens,
                total_tokens: acc.total_tokens + curr.total_tokens,
                cost: acc.cost + curr.cost,
            }),
            {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0,
                cost: 0,
            },
        );
    }

    return (
        props.message?.usageData || {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
            cost: 0,
        }
    );
});
</script>

<template>
    <HeadlessPopover v-if="message.usageData && usageDataTotal" class="relative">
        <HeadlessPopoverButton
            as="div"
            class="dark:border-anthracite border-stone-gray dark:text-stone-gray/50 text-stone-gray cursor-pointer
                rounded-lg border px-2 py-1 text-xs font-bold"
            @mouseover="open = true"
            @mouseleave="open = false"
        >
            {{ formatMessageCost(usageDataTotal.cost) }}
        </HeadlessPopoverButton>

        <AnimatePresence>
            <motion.div
                v-if="open"
                key="usage-data-popover"
                :initial="{ opacity: 0.75, scale: 0.95, translateY: 15 }"
                :animate="{
                    opacity: 1,
                    scale: 1,
                    translateY: 0,
                    transition: { duration: 0.2, ease: 'easeOut' },
                }"
                :exit="{
                    opacity: 0.75,
                    scale: 0.95,
                    translateY: 15,
                    transition: { duration: 0.15, ease: 'easeIn' },
                }"
                class="bg-obsidian/75 text-stone-gray border-stone-gray/20 absolute bottom-9 left-0 z-10 w-max max-w-[45vw]
                    min-w-52 -translate-x-[36%] gap-4 rounded-lg border p-4 pt-3 shadow-lg backdrop-blur-md"
            >
                <HeadlessPopoverPanel
                    static
                    class="flex w-full flex-wrap items-end justify-start gap-4"
                >
                    <!-- Standard Usage Data for TextToText and Routing -->
                    <template
                        v-if="
                            message.type === NodeTypeEnum.TEXT_TO_TEXT ||
                            message.type === NodeTypeEnum.ROUTING
                        "
                    >
                        <UiChatUtilsUsageDataTable
                            :usage-data="message.usageData"
                            :title="'Usage Details'"
                        />
                    </template>

                    <!-- Detailed Usage Data for Parallelization -->
                    <template v-if="message.type === NodeTypeEnum.PARALLELIZATION">
                        <!-- Models -->
                        <template
                            v-for="(model, index) in message.data as DataParallelizationModel[]"
                            :key="model.id"
                        >
                            <UiChatUtilsUsageDataTable
                                v-if="model.usageData"
                                :usage-data="model.usageData"
                                :title="`Model #${index}`"
                                :subtitle="model.model.split('/').pop()"
                            />

                            <div
                                v-if="model.usageData"
                                class="border-stone-gray/20 mb-16 font-bold"
                            >
                                +
                            </div>
                        </template>

                        <!-- Aggregator -->
                        <UiChatUtilsUsageDataTable
                            v-if="message.usageData && message.model"
                            :usage-data="message.usageData"
                            title="Aggregator"
                            :subtitle="message.model.split('/').pop()"
                        />

                        <div
                            v-if="message.usageData && message.model"
                            class="border-stone-gray/20 mb-16 font-bold"
                        >
                            =
                        </div>

                        <!-- Total -->
                        <UiChatUtilsUsageDataTable
                            :usage-data="usageDataTotal"
                            :title="'Total Usage'"
                        />
                    </template>
                </HeadlessPopoverPanel>
            </motion.div>
        </AnimatePresence>
    </HeadlessPopover>
</template>

<style scoped></style>
