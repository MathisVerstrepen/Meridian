<script lang="ts" setup>
import type { DataParallelizationModel, Message, UsageData, UsageDataRequest } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';
import { motion } from 'motion-v';

// --- Props ---
const props = defineProps<{
    message: Message;
}>();

// --- Composables ---
const { formatMessageCost } = useFormatters();

// --- State ---
const open = ref(false);
const activeTabId = ref<string>('total');
let closeTimer: ReturnType<typeof setTimeout> | null = null;

const handleEnter = () => {
    if (closeTimer) {
        clearTimeout(closeTimer);
        closeTimer = null;
    }
    open.value = true;
};

const handleLeave = () => {
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = setTimeout(() => {
        open.value = false;
    }, 140);
};

const emptyUsageData = (): UsageData => ({
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    cost: 0,
    is_byok: true,
    prompt_tokens_details: {},
    cost_details: {},
    completion_tokens_details: {},
    requests: [],
});

const mergeUsageDetails = (
    left: Record<string, number>,
    right: Record<string, number>,
): Record<string, number> => {
    const merged = { ...left };
    for (const [key, value] of Object.entries(right)) {
        merged[key] = (merged[key] ?? 0) + value;
    }
    return merged;
};

const sumUsageData = (acc: UsageData, curr: UsageData): UsageData => ({
    prompt_tokens: acc.prompt_tokens + curr.prompt_tokens,
    completion_tokens: acc.completion_tokens + curr.completion_tokens,
    total_tokens: acc.total_tokens + curr.total_tokens,
    cost: acc.cost + curr.cost,
    is_byok: acc.is_byok && curr.is_byok,
    prompt_tokens_details: mergeUsageDetails(
        acc.prompt_tokens_details ?? {},
        curr.prompt_tokens_details ?? {},
    ),
    cost_details: mergeUsageDetails(acc.cost_details ?? {}, curr.cost_details ?? {}),
    completion_tokens_details: mergeUsageDetails(
        acc.completion_tokens_details ?? {},
        curr.completion_tokens_details ?? {},
    ),
    requests: [],
});

const formatModelLabel = (model: string | null | undefined) =>
    model?.split('/').pop() ?? 'Unknown model';

const formatRequestSubtitle = (request: UsageDataRequest) => {
    const parts = [formatModelLabel(request.model), request.finish_reason || 'unknown'];
    if (request.tool_names.length > 0) {
        parts.push(request.tool_names.join(', '));
    }
    return parts.join(' · ');
};

const requestBreakdown = computed(() => props.message?.usageData?.requests ?? []);

const parallelizationModels = computed<DataParallelizationModel[]>(() => {
    if (props.message.type !== NodeTypeEnum.PARALLELIZATION || !props.message.data) return [];
    return (props.message.data as DataParallelizationModel[]).filter((m) => m.usageData);
});

const usageDataTotal = computed(() => {
    if (props.message.type === NodeTypeEnum.PARALLELIZATION && props.message.data) {
        const modelsUsageData = (props.message.data as DataParallelizationModel[]).map(
            (data) => data.usageData,
        );
        const aggregatorUsageData = props.message.usageData;
        const allUsageData = [...modelsUsageData, aggregatorUsageData];

        const filteredUsageData = allUsageData.filter(
            (data): data is UsageData => data !== null && data !== undefined,
        );

        return filteredUsageData.reduce(sumUsageData, emptyUsageData());
    }

    return props.message?.usageData || emptyUsageData();
});

interface TabItem {
    id: string;
    label: string;
    subtitle?: string;
    data: UsageData | UsageDataRequest;
    isTotal?: boolean;
}

const tabs = computed<TabItem[]>(() => {
    const list: TabItem[] = [
        {
            id: 'total',
            label: 'Total',
            data: usageDataTotal.value,
            isTotal: true,
        },
    ];

    if (props.message.type === NodeTypeEnum.PARALLELIZATION) {
        parallelizationModels.value.forEach((model, index) => {
            list.push({
                id: `model-${index}`,
                label: `M${index + 1}`,
                subtitle: formatModelLabel(model.model),
                data: model.usageData!,
            });
        });

        if (props.message.usageData && props.message.model) {
            list.push({
                id: 'aggregator',
                label: 'Agg',
                subtitle: formatModelLabel(props.message.model),
                data: props.message.usageData,
            });
        }
    } else if (
        props.message.type === NodeTypeEnum.TEXT_TO_TEXT ||
        props.message.type === NodeTypeEnum.ROUTING
    ) {
        requestBreakdown.value.forEach((request) => {
            list.push({
                id: `request-${request.index}`,
                label: `#${request.index}`,
                subtitle: formatRequestSubtitle(request),
                data: request,
            });
        });
    }

    return list;
});

const activeTab = computed(
    () => tabs.value.find((t) => t.id === activeTabId.value) ?? tabs.value[0],
);

watch(
    () => tabs.value.map((t) => t.id).join('|'),
    () => {
        if (!tabs.value.some((t) => t.id === activeTabId.value)) {
            activeTabId.value = 'total';
        }
    },
);

watch(open, (isOpen) => {
    if (isOpen) activeTabId.value = 'total';
});
</script>

<template>
    <HeadlessPopover
        v-if="message.usageData && usageDataTotal"
        class="relative"
        @mouseenter="handleEnter"
        @mouseleave="handleLeave"
    >
        <HeadlessPopoverButton
            as="div"
            class="dark:border-anthracite border-stone-gray dark:text-stone-gray/50 text-stone-gray
                hover:border-ember-glow/50 hover:text-ember-glow cursor-pointer rounded-lg border px-2 py-1
                text-xs font-bold transition-colors duration-200"
        >
            {{ formatMessageCost(usageDataTotal.cost) }}
        </HeadlessPopoverButton>

        <AnimatePresence>
            <motion.div
                v-if="open"
                key="usage-data-popover"
                :initial="{ opacity: 0, scale: 0.97, translateY: 6 }"
                :animate="{
                    opacity: 1,
                    scale: 1,
                    translateY: 0,
                    transition: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                }"
                :exit="{
                    opacity: 0,
                    scale: 0.97,
                    translateY: 6,
                    transition: { duration: 0.12, ease: 'easeIn' },
                }"
                class="absolute bottom-full left-1/2 z-20 -translate-x-1/2 pb-2"
            >
                <HeadlessPopoverPanel
                    static
                    class="bg-obsidian/90 text-stone-gray border-stone-gray/15 relative flex w-[256px] flex-col
                        overflow-hidden rounded-xl border shadow-[0_14px_36px_-12px_rgba(0,0,0,0.65)]
                        backdrop-blur-xl"
                >
                    <!-- Decorative top accent rail -->
                    <div
                        aria-hidden="true"
                        class="via-ember-glow/40 pointer-events-none absolute inset-x-4 top-0 h-px
                            bg-linear-to-r from-transparent to-transparent"
                    />

                    <!-- Tabs header -->
                    <nav
                        class="hide-scrollbar border-stone-gray/10 flex items-stretch gap-0.5 overflow-x-auto border-b
                            px-2 pt-2"
                        role="tablist"
                        aria-label="Usage breakdown"
                    >
                        <button
                            v-for="tab in tabs"
                            :key="tab.id"
                            type="button"
                            role="tab"
                            :aria-selected="tab.id === activeTabId"
                            class="relative shrink-0 px-2 pt-1 pb-1.5 text-[10px] font-bold tracking-[0.12em] uppercase
                                transition-colors duration-150"
                            :class="
                                tab.id === activeTabId
                                    ? 'text-ember-glow'
                                    : 'text-stone-gray/45 hover:text-stone-gray'
                            "
                            @click="activeTabId = tab.id"
                            @focus="activeTabId = tab.id"
                        >
                            <div class="relative flex items-center gap-1 justify-center">
                                <div
                                    v-if="tab.isTotal"
                                    aria-hidden="true"
                                    class="mb-0.5"
                                    :class="
                                        tab.id === activeTabId
                                            ? 'text-ember-glow'
                                            : 'text-stone-gray/30'
                                    "
                                    >∑</div
                                >
                                <div>{{ tab.label }}</div>
                                
                            </div>
                            <span
                                v-if="tab.id === activeTabId"
                                aria-hidden="true"
                                class="bg-ember-glow absolute -bottom-px right-1.5 left-1.5 h-[1.5px] rounded-full"
                            />
                        </button>
                    </nav>

                    <!-- Active tab content -->
                    <div class="relative">
                        <Transition
                            mode="out-in"
                            enter-active-class="transition-all duration-150 ease-out"
                            leave-active-class="transition-all duration-100 ease-in"
                            enter-from-class="opacity-0 translate-y-0.5"
                            leave-to-class="opacity-0 -translate-y-0.5"
                        >
                            <UiChatUtilsUsageDataTable
                                v-if="activeTab"
                                :key="activeTab.id"
                                :usage-data="activeTab.data"
                                :subtitle="activeTab.subtitle"
                                :is-total="activeTab.isTotal"
                            />
                        </Transition>
                    </div>
                </HeadlessPopoverPanel>
            </motion.div>
        </AnimatePresence>
    </HeadlessPopover>
</template>

<style scoped></style>
