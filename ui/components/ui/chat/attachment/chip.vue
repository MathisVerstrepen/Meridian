<script lang="ts" setup>
import { FileType } from '@/types/enums';
import type { File } from '@/types/files';

defineEmits<{
    (e: 'removeFile'): void;
}>();

// --- Props ---
defineProps<{
    file: File;
    removeFiles?: boolean;
}>();

// --- Composables ---
const { getFileType } = useFiles();
</script>

<template>
    <li
        :key="file.id"
        class="text-soft-silk/70 border-stone-gray/30 relative flex items-center rounded-xl border py-1.5 pr-1.5
            pl-3 text-sm font-bold transition-colors duration-200"
    >
        <template v-for="fileType in [getFileType(file.name)]">
            <UiIcon v-if="fileType === FileType.Other" class="h-5 w-5" name="BxBxsFileBlank" />
            <UiIcon v-else-if="fileType === FileType.PDF" class="h-5 w-5" name="BxBxsFilePdf" />
            <UiIcon
                v-else-if="fileType === FileType.Image"
                class="h-5 w-5"
                name="MaterialSymbolsImageRounded"
            />
        </template>
        <span class="px-2">
            {{ file.name.length > 20 ? file.name.slice(0, 20) + '…' : file.name }}
        </span>
        <button
            class="text-soft-silk/70 hover:text-soft-silk/100 bg-stone-gray/10 hover:bg-stone-gray/10 flex h-5 w-5
                cursor-pointer items-center justify-center rounded-lg transition-colors duration-200"
            @click="$emit('removeFile')"
            v-if="removeFiles"
        >
            <UiIcon class="h-4 w-4" name="MaterialSymbolsClose" />
        </button>
    </li>
</template>

<style scoped></style>
