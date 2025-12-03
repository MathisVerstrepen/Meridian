<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    item: FileSystemObject;
    isSelected: boolean;
    previewUrl?: string;
}>();

// --- Emits ---
const emit = defineEmits(['navigate', 'select', 'delete']);

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
    >
        <button
            class="text-stone-gray/60 absolute top-1 right-1 z-10 flex h-6 w-6 items-center
                justify-center rounded-full bg-black/10 opacity-0 transition-all duration-200
                group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400"
            title="Delete"
            @click.stop="$emit('delete', item)"
        >
            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
        </button>

        <UiIcon
            v-if="item.type === 'file' && item.cached"
            name="OcticonCache16"
            class="text-stone-gray/20 absolute top-2 left-2 z-10 h-4 w-4"
            title="Extracted Content Cached"
        />

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
        <p class="text-soft-silk line-clamp-2 w-full text-xs break-words" :title="item.name">
            {{ item.name }}
        </p>
    </div>
</template>
