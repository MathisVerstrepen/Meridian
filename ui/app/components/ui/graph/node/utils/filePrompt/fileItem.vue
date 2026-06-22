<script lang="ts" setup>
// --- Props ---
const props = withDefaults(
    defineProps<{
        item: FileSystemObject;
        isSelected: boolean;
        hasSelectedDescendants?: boolean;
        previewUrl?: string;
        viewMode?: 'grid' | 'gallery';
    }>(),
    {
        previewUrl: undefined,
        viewMode: 'grid',
    },
);

// --- Emits ---
const emit = defineEmits(['navigate', 'select', 'contextmenu', 'select-folder-contents', 'delete']);

// --- Composables ---
const { getIconForFile } = useFileIcons();

// --- State ---
const imageLoadError = ref(false);

// --- Watchers ---
watch(
    () => props.previewUrl,
    () => {
        imageLoadError.value = false;
    },
);

// --- Computed ---
const icon = computed(() => {
    if (props.item.type === 'folder') {
        return 'MdiFolderOutline';
    }
    const fileIcon = getIconForFile(props.item.name);
    return fileIcon ? `fileTree/${fileIcon}` : 'MdiFileOutline';
});

const isGallery = computed(() => props.viewMode === 'gallery');

// --- Methods ---
const handleClick = (event: MouseEvent | KeyboardEvent) => {
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
        class="group relative flex cursor-pointer flex-col items-center justify-center gap-2
            rounded-lg p-2 text-center transition-colors duration-200"
        :class="[
            isSelected
                ? 'bg-ember-glow/20 ring-ember-glow ring-2'
                : 'bg-stone-gray/5 hover:bg-stone-gray/10',
            isGallery ? 'w-full' : 'h-32 w-32',
        ]"
        tabindex="0"
        @click="handleClick"
        @keydown.enter.prevent="handleClick"
        @keydown.delete.prevent="emit('delete', item)"
        @contextmenu.prevent="emit('contextmenu', $event, item)"
    >
        <!-- Cached Indicator -->
        <UiIcon
            v-if="item.type === 'file' && item.cached"
            name="OcticonCache16"
            class="text-stone-gray/20 absolute top-1.5 left-1.5 z-10 h-4 w-4"
            title="Extracted Content Cached"
        />

        <!-- Selected Descendants Indicator (Folder only) -->
        <div
            v-if="item.type === 'folder' && hasSelectedDescendants"
            class="bg-ember-glow absolute top-1.5 right-1.5 z-10 h-2.5 w-2.5 rounded-full shadow-sm"
            title="Contains selected files"
        />

        <!-- Preview / Icon -->
        <div
            v-if="previewUrl && !imageLoadError"
            class="shrink-0 overflow-hidden rounded-md"
            :class="isGallery ? 'aspect-square w-full' : 'h-12 w-12'"
        >
            <img
                :src="previewUrl"
                class="h-full w-full object-cover"
                :alt="item.name"
                loading="lazy"
                @error="imageLoadError = true"
            />
        </div>
        <div
            v-else
            class="shrink-0 overflow-hidden rounded-md"
            :class="isGallery ? 'aspect-square w-full' : 'h-12 w-12'"
        >
            <div
                class="flex h-full w-full items-center justify-center"
            >
                <UiIcon
                    :name="icon"
                    class="text-transparent"
                    :class="[
                        {
                            'text-stone-gray/70!': item.type === 'folder' || icon === 'MdiFileOutline',
                        },
                        isGallery ? 'h-16 w-16' : 'h-12 w-12',
                    ]"
                />
            </div>
        </div>

        <!-- Name -->
        <p
            class="text-soft-silk line-clamp-2 w-full text-xs wrap-break-word"
            :class="isGallery ? 'mt-1' : ''"
            :title="item.name"
        >
            {{ item.name }}
        </p>
    </div>
</template>
