<script setup lang="ts">
const props = defineProps<{ nodeId?: string | null }>();
const retryStore = useStreamRetryStore();
const statuses = computed(() => (props.nodeId ? (retryStore.statuses[props.nodeId] ?? {}) : {}));
</script>

<template>
    <div
        v-if="Object.keys(statuses).length"
        role="status"
        aria-live="polite"
        class="my-2 text-xs opacity-70"
    >
        <p v-for="(status, modelId) in statuses" :key="modelId">{{ status.message }}</p>
    </div>
</template>
