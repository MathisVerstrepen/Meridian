<script lang="ts" setup>
// --- Props ---
defineProps({
    isMac: {
        type: Boolean,
        required: true,
    },
    placeholder: {
        type: String,
        default: undefined,
    },
});

// --- Models ---
const searchQuery = defineModel<string>('searchQuery', { required: true });
const searchScope = defineModel<'workspace' | 'global'>('searchScope', {
    required: true,
    default: 'workspace',
});

// --- Local State ---
const inputRef = ref<HTMLInputElement | null>(null);

// --- Handlers ---
const handleShiftSpace = () => document.execCommand('insertText', false, ' ');

const toggleScope = () => {
    searchScope.value = searchScope.value === 'workspace' ? 'global' : 'workspace';
};

// Expose focus method
defineExpose({
    focus: () => inputRef.value?.focus(),
});
</script>

<template>
    <div class="relative w-full">
        <UiIcon
            name="MdiMagnify"
            class="text-stone-gray/50 pointer-events-none absolute top-1/2 left-3 h-5 w-5
                -translate-y-1/2"
        />
        <input
            ref="inputRef"
            v-model="searchQuery"
            type="text"
            :placeholder="
                placeholder ||
                (searchScope === 'workspace' ? 'Search in workspace...' : 'Search all canvas...')
            "
            class="dark:bg-stone-gray/25 bg-obsidian/50 placeholder:text-stone-gray/50
                text-stone-gray block h-9 w-full rounded-xl border-transparent px-3 py-2 pr-24 pl-10
                text-sm font-semibold focus:border-transparent focus:ring-0 focus:outline-none"
            @keydown.space.shift.exact.prevent="handleShiftSpace"
        />

        <div class="absolute top-1/2 right-3 flex -translate-y-1/2 items-center gap-2">
            <!-- Scope Toggle -->
            <button
                class="hover:bg-stone-gray/20 text-stone-gray/50 hover:text-stone-gray flex
                    items-center justify-center rounded-md p-0.5 transition-colors"
                :title="
                    searchScope === 'workspace'
                        ? 'Searching: Workspace Only'
                        : 'Searching: All Canvas'
                "
                @click="toggleScope"
            >
                <UiIcon
                    v-if="searchScope === 'workspace'"
                    name="MdiBriefcaseOutline"
                    class="h-4 w-4"
                />
                <UiIcon v-else name="MdiWeb" class="h-4 w-4" />
            </button>

            <!-- Shortcut Hint -->
            <div class="text-stone-gray/30 rounded-md border px-1 py-0.5 text-[10px] font-bold">
                {{ isMac ? '⌘ + K' : 'CTRL + K' }}
            </div>
        </div>
    </div>
</template>
