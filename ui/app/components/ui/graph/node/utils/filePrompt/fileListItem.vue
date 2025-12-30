<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    item: FileSystemObject;
    isSelected: boolean;
    hasSelectedDescendants?: boolean;
}>();

// --- Emits ---
const emit = defineEmits(['navigate', 'select', 'contextmenu', 'select-folder-contents']);

// --- Composables ---
const { formatFileSize } = useFormatters();
const { getIconForFile } = useFileIcons();

// --- Computed ---
const icon = computed(() => {
    if (props.item.type === 'folder') {
        return 'MdiFolderOutline';
    }
    const fileIcon = getIconForFile(props.item.name);
    return fileIcon ? `fileTree/${fileIcon}` : 'MdiFileOutline';
});

// --- Methods ---
const handleClick = (event: MouseEvent) => {
    if (props.item.type === 'folder') {
        if (event.metaKey || event.ctrlKey) {
            emit('select-folder-contents', props.item);
        } else {
            emit('navigate', props.item);
        }
    } else {
        emit('select', props.item);
    }
};
</script>

<template>
    <div
        class="group hover:bg-stone-gray/5 grid cursor-pointer grid-cols-[1fr_8rem_8rem_10rem]
            items-center gap-4 rounded-md px-3 py-2 text-sm transition-colors duration-200"
        :class="[isSelected ? 'bg-ember-glow/20' : '']"
        @click="handleClick"
        @contextmenu.prevent="emit('contextmenu', $event, item)"
    >
        <!-- Name -->
        <div class="flex items-center gap-3 overflow-hidden">
            <UiIcon
                :name="icon"
                class="h-5 w-5 shrink-0 text-transparent"
                :class="{
                    '!text-stone-gray/70': item.type === 'folder' || icon === 'MdiFileOutline',
                }"
            />
            <span class="text-soft-silk truncate font-medium" :title="item.name">{{
                item.name
            }}</span>
            <!-- Selected Descendants Indicator (Folder only) -->
            <div
                v-if="item.type === 'folder' && hasSelectedDescendants"
                class="bg-ember-glow h-2.5 w-2.5 rounded-full shadow-sm"
                title="Contains selected files"
            />
        </div>

        <!-- Size -->
        <div class="text-stone-gray/60 text-xs">
            {{ item.type === 'file' ? formatFileSize(item.size || 0) : '-' }}
        </div>

        <!-- Type -->
        <div class="text-stone-gray/60 truncate text-xs capitalize">
            {{ item.type }}
        </div>

        <!-- Date -->
        <NuxtTime
            :datetime="item['updated_at'] ? new Date(item['updated_at']) : new Date()"
            class="text-stone-gray/60 text-xs"
            format="short"
        />
    </div>
</template>
