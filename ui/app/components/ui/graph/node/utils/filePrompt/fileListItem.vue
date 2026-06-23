<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    item: FileSystemObject;
    isSelected: boolean;
    hasSelectedDescendants?: boolean;
    canDrag?: boolean;
    isDragging?: boolean;
    isDragMoveActive?: boolean;
    isDropTarget?: boolean;
}>();

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
const { formatFileSize } = useFormatters();
const { getIconForFileSystemObject } = useFileIcons();

// --- Computed ---
const icon = computed(() => getIconForFileSystemObject(props.item));

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
        emit('select', props.item, event);
    }
};

const handleCheckboxClick = (event: MouseEvent) => {
    event.stopPropagation();
    if (props.item.type === 'folder') {
        emit('select-folder-contents', props.item);
    } else {
        emit('select', props.item, event);
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
        class="group grid cursor-pointer grid-cols-[1fr_8rem_8rem_10rem] items-center gap-4 rounded-lg px-3
            py-2 text-sm transition-all duration-200"
        :class="[
            isSelected
                ? 'bg-ember-glow/15 ring-ember-glow/40 ring-1'
                : 'hover:bg-stone-gray/8 ring-stone-gray/5 ring-1',
            isDropTarget ? 'bg-ember-glow/10 ring-ember-glow/70 ring-2' : '',
            isDragging ? 'opacity-40' : '',
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
        <!-- Name -->
        <div class="flex items-center gap-3 overflow-hidden">
            <!-- Selection Checkbox -->
            <div
                class="flex h-4 w-4 shrink-0 cursor-pointer items-center justify-center rounded border-2
                    transition-all duration-200"
                :class="
                    isSelected
                        ? 'border-ember-glow bg-ember-glow text-obsidian'
                        : isPartial
                          ? 'border-ember-glow bg-ember-glow/20 text-ember-glow'
                          : 'border-stone-gray/30 group-hover:border-stone-gray/50 text-transparent'
                "
                :title="
                    item.type === 'folder'
                        ? isSelected
                            ? 'Folder contents selected'
                            : 'Select folder contents'
                        : 'Select file'
                "
                @click="handleCheckboxClick"
            >
                <UiIcon
                    :name="isPartial ? 'Fa6SolidMinus' : 'MaterialSymbolsCheckSmallRounded'"
                    class="h-2.5 w-2.5"
                />
            </div>
            <UiIcon
                :name="icon"
                class="h-5 w-5 shrink-0 text-transparent transition-colors"
                :class="{
                    'text-stone-gray/70!': item.type === 'folder' || icon === 'MdiFileOutline',
                    'text-ember-glow/60!': item.type === 'file' && icon !== 'MdiFileOutline',
                }"
            />
            <span class="text-soft-silk truncate font-medium" :title="item.name">{{
                item.name
            }}</span>
        </div>

        <!-- Size -->
        <div class="text-stone-gray/60 text-xs">
            {{ item.type === 'file' ? formatFileSize(item.size || 0) : '—' }}
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
