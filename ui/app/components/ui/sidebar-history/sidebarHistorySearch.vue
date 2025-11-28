<script lang="ts" setup>
// --- Props ---
defineProps({
    isMac: {
        type: Boolean,
        required: true,
    },
});

// --- Emits ---
const emit = defineEmits<{
    (e: 'update:searchQuery', value: string): void;
    (e: 'import', files: FileList): void;
}>();

// --- Local State ---
const searchQuery = defineModel<string>('searchQuery', { required: true });
const searchInputRef = ref<HTMLInputElement | null>(null);

// --- Handlers ---
const handleShiftSpace = () => document.execCommand('insertText', false, ' ');

const handleFileChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (target.files) {
        emit('import', target.files);
    }
};

// Expose focus method for parent component
defineExpose({
    focus: () => searchInputRef.value?.focus(),
});
</script>

<template>
    <div class="hide-close mt-2 flex items-center gap-2">
        <div class="relative w-full">
            <UiIcon
                name="MdiMagnify"
                class="text-stone-gray/50 pointer-events-none absolute top-1/2 left-3 h-5 w-5
                    -translate-y-1/2"
            />
            <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                placeholder="Search canvas..."
                class="dark:bg-stone-gray/25 bg-obsidian/50 placeholder:text-stone-gray/50
                    text-stone-gray block h-9 w-full rounded-xl border-transparent px-3 py-2 pr-16
                    pl-10 text-sm font-semibold focus:border-transparent focus:ring-0
                    focus:outline-none"
                @keydown.space.shift.exact.prevent="handleShiftSpace"
            />
            <div
                class="text-stone-gray/30 absolute top-1/2 right-3 ml-auto -translate-y-1/2
                    rounded-md border px-1 py-0.5 text-[10px] font-bold"
            >
                {{ isMac ? '⌘ + K' : 'CTRL + K' }}
            </div>
        </div>
        <label
            class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit
                dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-9 w-14 shrink-0 items-center
                justify-center rounded-xl transition duration-200 ease-in-out hover:cursor-pointer"
            title="Import Canvas Backup"
        >
            <UiIcon name="UilUpload" class="text-stone-gray h-5 w-5" />
            <input type="file" multiple class="hidden" @change="handleFileChange" />
        </label>
    </div>
</template>
