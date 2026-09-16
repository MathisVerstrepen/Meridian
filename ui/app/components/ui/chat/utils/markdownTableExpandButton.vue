<script setup lang="ts">
const props = defineProps<{ scrollId: string }>();
const emit = defineEmits<{ expand: [table: HTMLTableElement] }>();

const expand = () => {
    const table = document.getElementById(props.scrollId)?.querySelector('table');
    if (table) emit('expand', table);
};
</script>

<template>
    <button
        type="button"
        aria-label="Expand table"
        aria-haspopup="dialog"
        class="text-soft-silk/80 hover:bg-stone-gray/20 focus-visible:ring-soft-silk/60 flex h-8
            w-8 items-center justify-center rounded-md focus-visible:ring-2"
        @click="expand"
    >
        <UiIcon name="MingcuteFullscreen2Line" class="h-5 w-5" />
    </button>
</template>
