<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    item: FileSystemObject;
    isSelected: boolean;
}>();

// --- Emits ---
const emit = defineEmits(['navigate', 'select', 'delete']);

// --- Composables ---
const { getIconForFile } = useFileIcons();
const { formatFileSize } = useFormatters();

// --- Computed ---
const icon = computed(() => {
    if (props.item.type === 'folder') {
        return 'MdiFolderOutline';
    }
    const fileIcon = getIconForFile(props.item.name);
    return fileIcon ? `fileTree/${fileIcon}` : 'MdiFileOutline';
});

const formattedDate = computed(() => {
    return new Date(props.item.created_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
});

const fileType = computed(() => {
    if (props.item.type === 'folder') return 'Folder';
    const ext = props.item.name.split('.').pop();
    return ext ? `${ext.toUpperCase()} File` : 'File';
});

// --- Methods ---
const handleClick = () => {
    if (props.item.type === 'folder') {
        emit('navigate', props.item);
    } else {
        emit('select', props.item);
    }
};
</script>

<template>
    <div
        class="group border-stone-gray/5 hover:bg-stone-gray/10 relative grid cursor-pointer
            grid-cols-[1fr_8rem_8rem_10rem_2rem] items-center gap-4 rounded-md border-b px-3 py-2
            text-sm transition-colors duration-200 last:border-0"
        :class="[isSelected ? 'bg-ember-glow/20 ring-ember-glow/50 ring-1' : 'bg-transparent']"
        @click="handleClick"
    >
        <!-- Name & Icon -->
        <div class="flex min-w-0 items-center gap-3">
            <UiIcon
                :name="icon"
                class="h-5 w-5 shrink-0 text-transparent"
                :class="{
                    '!text-stone-gray/70':
                        props.item.type === 'folder' || icon === 'MdiFileOutline',
                }"
            />
            <span class="text-soft-silk truncate font-medium" :title="props.item.name">
                {{ props.item.name }}
            </span>

            <!-- Cache Indicator -->
            <UiIcon
                v-if="item.type === 'file' && item.cached"
                name="OcticonCache16"
                class="text-stone-gray/40 h-3.5 w-3.5 shrink-0"
                title="Extracted Content Cached"
            />
        </div>

        <!-- Size -->
        <div class="text-stone-gray/60 truncate text-xs">
            {{ props.item.type === 'folder' ? '-' : formatFileSize(props.item.size || 0) }}
        </div>

        <!-- Type -->
        <div class="text-stone-gray/60 truncate text-xs">
            {{ fileType }}
        </div>

        <!-- Date -->
        <div class="text-stone-gray/60 truncate text-xs">
            {{ formattedDate }}
        </div>

        <!-- Actions -->
        <div class="flex justify-end">
            <button
                class="text-stone-gray/60 flex h-6 w-6 items-center justify-center rounded-full
                    opacity-0 transition-all duration-200 group-hover:opacity-100
                    hover:bg-red-500/20 hover:text-red-400"
                title="Delete"
                @click.stop="$emit('delete', item)"
            >
                <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
            </button>
        </div>
    </div>
</template>
