<script lang="ts" setup>
import UiUtilsSearchBar from '~/components/ui/utils/searchBar.vue';

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
const searchScope = defineModel<'workspace' | 'global'>('searchScope', {
    required: true,
    default: 'workspace',
});
const searchBarRef = ref<InstanceType<typeof UiUtilsSearchBar> | null>(null);

// --- Handlers ---
const handleFileChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files.length > 0) {
        emit('import', target.files);
        target.value = '';
    }
};

// Expose focus method for parent component
defineExpose({
    focus: () => searchBarRef.value?.focus(),
});
</script>

<template>
    <div class="hide-close mt-2 flex items-center gap-2">
        <UiUtilsSearchBar
            ref="searchBarRef"
            v-model:search-query="searchQuery"
            v-model:search-scope="searchScope"
            :is-mac="isMac"
        />

        <label
            class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit
                dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-9 w-14 shrink-0 items-center
                justify-center rounded-xl transition duration-200 ease-in-out hover:cursor-pointer"
            title="Import Canvas Backup"
        >
            <UiIcon name="UilUpload" class="text-stone-gray h-5 w-5" />
            <input type="file" accept=".json" class="hidden" @change="handleFileChange" />
        </label>
    </div>
</template>
