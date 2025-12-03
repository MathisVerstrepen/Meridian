<script lang="ts" setup>
import { onClickOutside } from '@vueuse/core';

const props = defineProps<{
    position: { x: number; y: number };
    item: FileSystemObject;
}>();

const emit = defineEmits(['close', 'open', 'select', 'rename', 'download', 'delete']);

const menuRef = useTemplateRef<HTMLElement>('menuRef');

onClickOutside(menuRef, () => emit('close'));

const style = computed(() => ({
    top: `${props.position.y - 30}px`,
    left: `${props.position.x - 50}px`,
}));
</script>

<template>
    <div
        ref="menuRef"
        class="bg-obsidian border-stone-gray/20 text-soft-silk fixed z-[100] flex min-w-[160px]
            flex-col rounded-lg border py-1 shadow-xl backdrop-blur-md"
        :style="style"
        @contextmenu.prevent
    >
        <!-- Menu Items -->
        <button
            v-if="item.type === 'folder'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5 text-left
                text-sm"
            @click="emit('open', item)"
        >
            <UiIcon :name="'MdiFolderOpenOutline'" class="h-4 w-4" />
            Open
        </button>

        <button
            v-if="item.type === 'file'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5 text-left
                text-sm"
            @click="emit('select', item)"
        >
            <UiIcon name="MaterialSymbolsCheckCircleOutlineRounded" class="h-4 w-4" />
            Select
        </button>

        <div class="bg-stone-gray/20 my-1 h-px w-full" />

        <button
            class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5 text-left
                text-sm"
            @click="emit('rename', item)"
        >
            <UiIcon name="MdiRename" class="h-4 w-4" />
            Rename
        </button>

        <button
            v-if="item.type === 'file'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5 text-left
                text-sm"
            @click="emit('download', item)"
        >
            <UiIcon name="UilDownloadAlt" class="h-4 w-4" />
            Download
        </button>

        <div class="bg-stone-gray/20 my-1 h-px w-full" />

        <button
            class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-red-400
                hover:bg-red-500/10"
            @click="emit('delete', item)"
        >
            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
            Delete
        </button>
    </div>
</template>
