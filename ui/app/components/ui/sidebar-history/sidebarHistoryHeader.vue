<script lang="ts" setup>
// --- Props ---
defineProps({
    isMac: {
        type: Boolean,
        required: true,
    },
    isTemporaryOpen: {
        type: Boolean,
        required: true,
    },
});

// --- Emits ---
defineEmits<{
    (e: 'createGraph' | 'createFolder' | 'createTemporaryGraph'): void;
}>();
</script>

<template>
    <div class="hide-close flex items-center gap-2">
        <!-- New canvas button -->
        <div
            class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit
                dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-14 shrink-0 grow
                cursor-pointer items-center space-x-2 rounded-xl pr-3 pl-5 font-bold transition
                duration-200 ease-in-out"
            role="button"
            :title="`Create New Canvas (${isMac ? '⌘' : 'ALT'} + N)`"
            @click="$emit('createGraph')"
        >
            <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-4 w-4" />
            <span>New Canvas</span>
            <div
                class="text-stone-gray/30 ml-auto rounded-md border px-1 py-0.5 text-[10px]
                    font-bold"
            >
                {{ isMac ? '⌘ + N' : 'ALT + N' }}
            </div>
        </div>

        <!-- New Folder Button -->
        <button
            class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray dark:hover:bg-stone-gray/20
                hover:bg-obsidian/75 flex h-14 w-14 items-center justify-center rounded-xl
                transition duration-200 ease-in-out hover:cursor-pointer"
            title="Create New Folder"
            @click="$emit('createFolder')"
        >
            <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
        </button>

        <!-- Temporary chat button -->
        <button
            class="flex h-14 w-14 items-center justify-center rounded-xl transition duration-200
                ease-in-out hover:cursor-pointer"
            :class="{
                'bg-ember-glow/20 border-ember-glow/50 text-ember-glow border-2': isTemporaryOpen,
                [`dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray dark:hover:bg-stone-gray/20
                hover:bg-obsidian/75`]: !isTemporaryOpen,
            }"
            title="New temporary chat (no save)"
            @click="$emit('createTemporaryGraph')"
        >
            <UiIcon name="LucideMessageCircleDashed" class="h-5 w-5" />
        </button>
    </div>
</template>
