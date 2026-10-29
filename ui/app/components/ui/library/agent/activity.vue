<script setup lang="ts">
const props = defineProps<{ nodeId: string; execution?: JsonObject; theme?: 'light' }>();
const emit = defineEmits<{ triggerScroll: [] }>();
const runs = useSubagentRuns(
    () => props.nodeId,
    () => props.execution,
);
const statusLabel = (status: string) => {
    switch (status) {
        case 'running':
            return 'Running';
        case 'completed':
            return 'Completed';
        case 'paused':
            return 'Needs your input';
        case 'failed':
            return 'Failed';
        case 'cancelled':
            return 'Cancelled';
        default:
            return status;
    }
};
const handleToggle = async (open: boolean) => {
    if (open) {
        await nextTick();
        emit('triggerScroll');
    }
};
</script>

<template>
    <div
        v-if="runs.length"
        class="nodrag my-2 flex min-w-0 flex-col"
        aria-label="Subagent activity"
    >
        <div v-for="run in runs" :key="run.id" :data-run-id="run.id" class="min-w-0">
            <HeadlessDisclosure v-slot="{ open }">
                <HeadlessDisclosureButton
                    data-testid="subagent-disclosure-button"
                    class="mb-2 flex min-h-9 max-w-full cursor-pointer items-center gap-2 rounded-lg
                        text-left transition-colors duration-200 ease-in-out"
                    :class="[
                        props.theme === 'light'
                            ? 'text-obsidian/80 hover:text-obsidian/60'
                            : `dark:hover:text-soft-silk/60 hover:text-anthracite/20
                                dark:text-soft-silk/80 text-obsidian`,
                        { 'text-red-500!': run.status === 'failed' },
                    ]"
                    @click="handleToggle(open)"
                >
                    <UiIcon
                        :name="
                            run.status === 'running' ? 'LineMdLoadingTwotoneLoop' : 'RiBrain2Line'
                        "
                        class="size-4 shrink-0"
                    />
                    <span class="min-w-0 text-sm font-bold wrap-break-word"
                        >Subagent · {{ run.name }}</span
                    >
                    <span
                        class="border-stone-gray/20 shrink-0 rounded-full border px-2 py-1 text-xs
                            font-semibold"
                        :class="{ 'text-amber-500 dark:text-amber-300': run.status === 'paused' }"
                        role="status"
                        >{{ statusLabel(run.status) }}</span
                    >
                    <UiIcon
                        name="LineMdChevronSmallUp"
                        class="size-4 shrink-0 transition-transform duration-200"
                        :class="open ? 'rotate-0' : 'rotate-180'"
                    />
                </HeadlessDisclosureButton>
                <HeadlessDisclosurePanel
                    data-testid="subagent-disclosure-panel"
                    as="div"
                    class="mb-3 flex min-w-0 items-stretch gap-4"
                >
                    <div class="dark:bg-anthracite bg-anthracite/20 w-1 shrink-0 rounded" />
                    <UiLibraryAgentRunPanel
                        :run="run"
                        :node-id="props.nodeId"
                        :class="
                            props.theme === 'light'
                                ? 'dark bg-obsidian text-soft-silk rounded-xl p-3'
                                : ''
                        "
                    />
                </HeadlessDisclosurePanel>
            </HeadlessDisclosure>
        </div>
    </div>
</template>
