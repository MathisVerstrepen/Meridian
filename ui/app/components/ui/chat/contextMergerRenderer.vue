<script lang="ts" setup>
import type { Message } from '@/types/graph';

defineProps<{
    message: Message;
}>();

const emit = defineEmits(['rendered', 'triggerScroll']);

onMounted(() => {
    emit('rendered');
    emit('triggerScroll');
});
</script>

<template>
    <div
        class="dark:bg-obsidian/50 bg-soft-silk/75 border-soft-silk/25 flex w-full flex-col gap-4
            rounded-t rounded-b-2xl border-b-2 py-2 text-center font-bold backdrop-blur-2xl"
    >
        Merged Context from previous branches
    </div>
</template>

<style scoped></style>
