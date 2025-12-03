<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    item: FileSystemObject;
    isSelected: boolean;
    hasSelectedDescendants?: boolean;
    previewUrl?: string;
}>();

// --- Emits ---
const emit = defineEmits(['navigate', 'select', 'contextmenu']);

// --- Composables ---
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
        class="group relative flex h-32 w-32 cursor-pointer flex-col items-center justify-center
            gap-2 rounded-lg p-2 text-center transition-colors duration-200"
        :class="[
            isSelected
                ? 'bg-ember-glow/20 ring-ember-glow ring-2'
                : 'bg-stone-gray/5 hover:bg-stone-gray/10',
        ]"
        @click="handleClick"
        @contextmenu.prevent="emit('contextmenu', $event, item)"
    >
        <!-- Cached Indicator -->
        <UiIcon
            v-if="item.type === 'file' && item.cached"
            name="OcticonCache16"
            class="text-stone-gray/20 absolute top-2 left-2 z-10 h-4 w-4"
            title="Extracted Content Cached"
        />

        <!-- Selected Descendants Indicator (Folder only) -->
        <div
            v-if="item.type === 'folder' && hasSelectedDescendants"
            class="bg-ember-glow absolute top-2 right-2 z-10 h-2.5 w-2.5 rounded-full shadow-sm"
            title="Contains selected files"
        />

        <!-- Preview / Icon -->
        <div v-if="previewUrl" class="h-12 w-12 shrink-0 overflow-hidden rounded-md">
            <img
                :src="previewUrl"
                class="h-full w-full object-cover"
                :alt="item.name"
                loading="lazy"
            />
        </div>
        <UiIcon
            v-else
            :name="icon"
            class="h-12 w-12 shrink-0 text-transparent"
            :class="{
                '!text-stone-gray/70': item.type === 'folder' || icon === 'MdiFileOutline',
            }"
        />

        <!-- Name -->
        <p class="text-soft-silk line-clamp-2 w-full text-xs break-words" :title="item.name">
            {{ item.name }}
        </p>
    </div>
</template>
