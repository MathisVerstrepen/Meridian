<script lang="ts" setup>
import type { FileTreeNode } from '@/types/github';
import type { Repo } from '@/types/github';

// --- Props ---
const props = defineProps<{
    files: FileTreeNode[];
    setFiles: (files: FileTreeNode[]) => void;
    repo: Repo;
}>();

// --- Composables ---
const { getRepoTree } = useAPI();
const graphEvents = useGraphEvents();

// --- Local State ---
const loading = ref(false);
const error = ref<string | null>(null);
const selectedFiles = ref<FileTreeNode[]>(props.files);

// --- Core Logic Functions ---
const fetchRepoTree = async () => {
    if (!props.repo) return;

    loading.value = true;
    error.value = null;

    const [owner, repoName] = props.repo.full_name.split('/');

    try {
        const fileTree = await getRepoTree(owner, repoName);
        if (!fileTree) {
            error.value = 'Failed to fetch repository structure';
            return;
        }
        graphEvents.emit('open-github-file-select', {
            repoContent: { repo: props.repo, files: fileTree, selectedFiles: selectedFiles.value },
        });
    } catch (err) {
        error.value = 'Failed to fetch repository structure';
        console.error('Error fetching repo tree:', err);
    } finally {
        loading.value = false;
    }
};

watch(
    () => selectedFiles.value,
    (newSelectedFiles) => {
        props.setFiles(newSelectedFiles);
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('close-github-file-select', async (selectedFilePaths) => {
        selectedFiles.value = selectedFilePaths.selectedFilePaths;
    });

    onUnmounted(unsubscribe);
});
</script>

<template>
    <div class="w-full grow">
        <button
            v-if="props.files"
            class="group nodrag text-stone-gray/50 bg-stone-gray/5 hover:text-stone-gray relative flex h-full w-full
                cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl p-1
                duration-300 ease-in-out"
            @click="fetchRepoTree"
            :disabled="loading"
        >
            <div
                class="absolute inset-0 opacity-0 transition-opacity duration-300 ease-in-out group-hover:opacity-100"
                style="
                    background-image:
                        radial-gradient(
                            circle at 0% 0%,
                            color-mix(in oklab, var(--color-soft-silk) 3%, transparent) 0%,
                            transparent 40%
                        ),
                        radial-gradient(
                            circle at 100% 0%,
                            color-mix(in oklab, var(--color-soft-silk) 3%, transparent) 0%,
                            transparent 40%
                        ),
                        radial-gradient(
                            circle at 0% 100%,
                            color-mix(in oklab, var(--color-soft-silk) 3%, transparent) 0%,
                            transparent 40%
                        ),
                        radial-gradient(
                            circle at 100% 100%,
                            color-mix(in oklab, var(--color-soft-silk) 3%, transparent) 0%,
                            transparent 40%
                        );
                "
            ></div>
            <UiIcon name="MdiFileOutline" class="h-6 w-6" />
            <span>
                {{ loading ? 'Loading...' : 'Select Files' }}
            </span>
            <span class="text-xs font-bold">
                {{ selectedFiles.filter((file) => file.type === 'file').length }} file(s) selected
            </span>
        </button>
    </div>
</template>

<style scoped></style>
