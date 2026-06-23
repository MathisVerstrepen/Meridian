<script lang="ts" setup>
import { onClickOutside } from '@vueuse/core';

const props = defineProps<{
    position: { x: number; y: number };
    item: FileSystemObject;
    canMoveCopy: boolean;
    canCopy: boolean;
    isPinned: boolean;
}>();

const emit = defineEmits([
    'close',
    'open',
    'select',
    'pin',
    'rename',
    'download',
    'move',
    'copy',
    'delete',
]);

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
        class="bg-obsidian/95 border-stone-gray/20 text-soft-silk fixed z-100 flex min-w-[200px]
            flex-col rounded-xl border py-1.5 shadow-2xl backdrop-blur-md"
        :style="style"
        @contextmenu.prevent
    >
        <!-- Open / Navigate section -->
        <button
            v-if="item.type === 'folder'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('open', item)"
        >
            <UiIcon name="MdiFolderOpenOutline" class="text-stone-gray/70 h-4 w-4 shrink-0" />
            <span>Open</span>
        </button>

        <button
            v-if="item.type === 'folder'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('pin', item)"
        >
            <UiIcon
                :name="isPinned ? 'MajesticonsUnpin' : 'MajesticonsPin'"
                class="text-stone-gray/70 h-4 w-4 shrink-0"
            />
            <span>{{ isPinned ? 'Unpin Folder' : 'Pin Folder' }}</span>
        </button>

        <button
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('select', item)"
        >
            <UiIcon
                name="MaterialSymbolsCheckCircleOutlineRounded"
                class="text-stone-gray/70 h-4 w-4 shrink-0"
            />
            <span>{{ item.type === 'folder' ? 'Select Folder Contents' : 'Select' }}</span>
        </button>

        <!-- Divider -->
        <div v-if="item.type === 'folder'" class="bg-stone-gray/15 my-1 mx-2 h-px" />

        <!-- Actions section -->
        <button
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('rename', item)"
        >
            <UiIcon name="MdiRename" class="text-stone-gray/70 h-4 w-4 shrink-0" />
            <span>Rename</span>
            <kbd
                class="text-stone-gray/40 ml-auto rounded border border-current/20 px-1.5 py-0.5 text-[10px]
                    font-mono"
            >
                F2
            </kbd>
        </button>

        <button
            v-if="item.type === 'file'"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('download', item)"
        >
            <UiIcon name="UilDownloadAlt" class="text-stone-gray/70 h-4 w-4 shrink-0" />
            <span>Download</span>
        </button>

        <button
            v-if="canMoveCopy"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors"
            @click="emit('move', item)"
        >
            <UiIcon name="MdiFolderMoveOutline" class="text-stone-gray/70 h-4 w-4 shrink-0" />
            <span>Move</span>
        </button>

        <button
            v-if="canMoveCopy"
            class="hover:bg-stone-gray/10 flex w-full items-center gap-3 px-3 py-2 text-left text-sm
                transition-colors disabled:cursor-not-allowed disabled:opacity-40"
            :disabled="!canCopy"
            @click="emit('copy', item)"
        >
            <UiIcon
                name="MaterialSymbolsContentCopyOutlineRounded"
                class="text-stone-gray/70 h-4 w-4 shrink-0"
            />
            <span>Copy</span>
        </button>

        <!-- Divider -->
        <div class="bg-stone-gray/15 my-1 mx-2 h-px" />

        <!-- Destructive -->
        <button
            class="flex w-full items-center gap-3 px-3 py-2 text-left text-sm text-red-400
                transition-colors hover:bg-red-500/10"
            @click="emit('delete', item)"
        >
            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4 shrink-0" />
            <span>Delete</span>
            <kbd
                class="text-stone-gray/40 ml-auto rounded border border-current/20 px-1.5 py-0.5 text-[10px]
                    font-mono"
            >
                Del
            </kbd>
        </button>
    </div>
</template>
