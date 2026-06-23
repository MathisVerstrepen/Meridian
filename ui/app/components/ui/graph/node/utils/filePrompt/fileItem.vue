<script lang="ts" setup>
// --- Props ---
const props = withDefaults(
    defineProps<{
        item: FileSystemObject;
        isSelected: boolean;
        hasSelectedDescendants?: boolean;
        previewUrl?: string;
        viewMode?: 'grid' | 'gallery';
        canDrag?: boolean;
        isDragging?: boolean;
        isDragMoveActive?: boolean;
        isDropTarget?: boolean;
    }>(),
    {
        previewUrl: undefined,
        viewMode: 'grid',
        canDrag: false,
        isDragging: false,
        isDragMoveActive: false,
        isDropTarget: false,
    },
);

// --- Emits ---
const emit = defineEmits([
    'navigate',
    'select',
    'contextmenu',
    'select-folder-contents',
    'delete',
    'drag-move-start',
    'drag-move-end',
    'drag-move-over',
    'drag-move-leave',
    'drag-move-drop',
]);

// --- Composables ---
const { getIconForFileSystemObject } = useFileIcons();

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
const icon = computed(() => getIconForFileSystemObject(props.item));

const isGallery = computed(() => props.viewMode === 'gallery');
const hasPreview = computed(() => props.previewUrl && !imageLoadError.value);
const isPartial = computed(
    () => props.item.type === 'folder' && props.hasSelectedDescendants && !props.isSelected,
);

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

const handleBadgeClick = (event: MouseEvent) => {
    event.stopPropagation();
    if (props.item.type === 'folder') {
        emit('select-folder-contents', props.item);
    } else {
        emit('select', props.item);
    }
};

const handleDragStart = (event: DragEvent) => {
    emit('drag-move-start', event, props.item);
};

const handleDragOver = (event: DragEvent) => {
    if (props.item.type !== 'folder' || !props.isDragMoveActive) return;
    event.preventDefault();
    event.stopPropagation();
    emit('drag-move-over', event, props.item);
};

const handleDragLeave = (event: DragEvent) => {
    if (props.item.type !== 'folder' || !props.isDragMoveActive) return;
    emit('drag-move-leave', event, props.item);
};

const handleDrop = (event: DragEvent) => {
    if (props.item.type !== 'folder' || !props.isDragMoveActive) return;
    event.preventDefault();
    event.stopPropagation();
    emit('drag-move-drop', event, props.item);
};
</script>

<template>
    <div
        class="group bg-stone-gray/5 hover:bg-stone-gray/10 relative flex cursor-pointer flex-col
            items-center justify-center gap-2 rounded-xl p-2 text-center transition-all duration-200"
        :class="[
            isSelected
                ? 'bg-ember-glow/15 ring-ember-glow ring-2'
                : 'hover:ring-stone-gray/20 ring-stone-gray/10 ring-1',
            isDropTarget ? 'bg-ember-glow/10 ring-ember-glow/70 ring-2' : '',
            isDragging ? 'scale-[0.98] opacity-40' : '',
            'w-full overflow-hidden',
        ]"
        :draggable="canDrag"
        :data-file-draggable="canDrag ? 'true' : undefined"
        tabindex="0"
        @click="handleClick"
        @keydown.enter.prevent="handleClick"
        @keydown.delete.prevent="emit('delete', item)"
        @contextmenu.prevent="emit('contextmenu', $event, item)"
        @dragstart="handleDragStart"
        @dragend="emit('drag-move-end')"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
    >
        <!-- Cached Indicator -->
        <UiIcon
            v-if="item.type === 'file' && item.cached"
            name="OcticonCache16"
            class="text-stone-gray/30 absolute top-1.5 left-1.5 z-10 h-4 w-4"
            title="Extracted Content Cached"
        />

        <!-- Selection Badge -->
        <div
            class="absolute top-1.5 right-1.5 z-10 flex h-5 w-5 cursor-pointer items-center justify-center
                rounded-full border-2 transition-all duration-200"
            :class="
                isSelected
                    ? 'border-ember-glow bg-ember-glow text-obsidian'
                    : isPartial
                      ? 'border-ember-glow bg-ember-glow/20 text-ember-glow'
                      : 'border-stone-gray/30 bg-obsidian/60 text-transparent opacity-0 group-hover:opacity-100'
            "
            :title="
                item.type === 'folder'
                    ? isSelected
                        ? 'Folder contents selected'
                        : 'Select folder contents'
                    : 'Select file'
            "
            @click="handleBadgeClick"
        >
            <UiIcon
                :name="isPartial ? 'Fa6SolidMinus' : 'MaterialSymbolsCheckSmallRounded'"
                class="h-3 w-3"
            />
        </div>

        <!-- Preview / Icon -->
        <div
            class="shrink-0 overflow-hidden rounded-lg"
            :class="[
                'aspect-square w-full',
                hasPreview ? '' : 'bg-stone-gray/10',
            ]"
        >
            <img
                v-if="hasPreview"
                :src="previewUrl"
                class="h-full w-full object-cover"
                :alt="item.name"
                loading="lazy"
                @error="imageLoadError = true"
            />
            <div v-else class="flex h-full w-full items-center justify-center">
                <UiIcon
                    :name="icon"
                    class="text-transparent transition-colors"
                    :class="[
                        {
                            'text-stone-gray/70!': item.type === 'folder' || icon === 'MdiFileOutline',
                            'text-ember-glow/60!': item.type === 'file' && icon !== 'MdiFileOutline',
                        },
                        isGallery ? 'h-16 w-16' : 'h-12 w-12',
                    ]"
                />
            </div>
        </div>

        <!-- Name -->
        <p
            class="text-soft-silk line-clamp-2 mt-1 w-full text-xs wrap-break-word"
            :title="item.name"
        >
            {{ item.name }}
        </p>
    </div>
</template>
