<script lang="ts" setup>
const props = defineProps<{
    files: FileSystemObject[];
}>();
const emit = defineEmits<{
    (e: 'delete-file', fileIndex: number): void;
}>();

// --- Composables ---
const { formatFileSize } = useFormatters();
const { getIconForFile } = useFileIcons();

const getIcon = (file: FileSystemObject) => {
    if (file.type === 'folder') {
        return 'MdiFolderOutline';
    }
    const fileIcon = getIconForFile(file.name);
    return fileIcon ? `fileTree/${fileIcon}` : 'MdiFileOutline';
};
</script>

<template>
    <div v-if="props.files.length" class="purple-scrollbar grow overflow-y-auto">
        <ul class="nodrag nowheel grid grid-cols-[repeat(auto-fill,minmax(12rem,1fr))] gap-2">
            <li
                v-for="(file, index) in props.files"
                :key="file.id"
                class="group dark:text-soft-silk text-anthracite bg-dried-heather-dark/50 hover:bg-dried-heather-dark
                    relative flex items-center justify-start gap-2 overflow-hidden rounded-lg p-2 text-sm transition-all
                    duration-200"
            >
                <!-- File Icon -->
                <div class="flex shrink-0 items-center justify-center overflow-hidden rounded-md">
                    <UiIcon :name="getIcon(file)" class="h-5 w-5 shrink-0 text-transparent" />
                </div>

                <!-- File Info & Delete Button -->
                <div class="relative z-10 flex w-full min-w-0 items-center justify-between gap-1">
                    <div class="flex min-w-0 flex-col text-left">
                        <p class="truncate text-[11px] font-medium" :title="file.name">
                            {{ file.name }}
                        </p>
                        <p class="text-[10px] opacity-60">
                            {{ formatFileSize(file.size || 0) }}
                        </p>
                    </div>
                    <button
                        type="button"
                        class="bg-dried-heather/50 flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-md
                            opacity-0 transition-all duration-200 group-hover:opacity-100 hover:bg-red-500/50"
                        title="Delete file"
                        @click.stop="emit('delete-file', index)"
                    >
                        <UiIcon name="MaterialSymbolsDeleteRounded" class="h-3.5 w-3.5" />
                    </button>
                </div>
            </li>
        </ul>
    </div>
</template>

<style scoped>
.purple-scrollbar {
    --scrollbar-track: var(--color-dried-heather);
    --scrollbar-thumb: var(--color-dried-heather-dark);
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

.purple-scrollbar::-webkit-scrollbar-track {
    background: var(--scrollbar-track);
}

.purple-scrollbar::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 4px;
}

.purple-scrollbar::-webkit-scrollbar {
    width: 8px;
}
</style>
