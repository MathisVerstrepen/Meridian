<script setup lang="ts">
const props = defineProps<{ nodeId: string; execution?: JsonObject }>();
const runs = useSubagentRuns(
    () => props.nodeId,
    () => props.execution,
);
const names = computed(() =>
    [...new Map(runs.value.map((run) => [run.agent_id ?? run.id, run.name])).values()].join(', '),
);
</script>

<template>
    <div
        v-if="names"
        role="group"
        aria-label="Executed subagents"
        class="nodrag text-obsidian/80 mb-2 flex min-w-0 shrink-0 items-center gap-2 text-xs"
    >
        <UiIcon name="RiBrain2Line" class="size-4 shrink-0" />
        <span :title="names" class="min-w-0 truncate">
            <span class="font-semibold">Subagents:</span> {{ names }}
        </span>
    </div>
</template>
