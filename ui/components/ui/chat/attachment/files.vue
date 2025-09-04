<script lang="ts" setup>
import type { MessageContentFile } from '@/types/graph';

// --- Props ---
defineProps<{
    files: MessageContentFile[];
}>();

// --- Composables ---
const { getFileType } = useFiles();
</script>

<template>
    <ul v-if="files.length > 0" class="decoration-none flex w-fit list-none flex-wrap gap-2">
        <UiChatAttachmentChipListItem
            v-for="(file, index) in files"
            :key="index"
            :file="{
                id: index.toString(),
                name: file.filename,
                size: 0,
                type: getFileType(file.filename),
            }"
            :remove-files="false"
            @remove-file="() => {}"
        />
    </ul>
</template>

<style scoped></style>
