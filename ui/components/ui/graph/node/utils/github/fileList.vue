<script lang="ts" setup>
import type { FileTreeNode, Repo } from '@/types/github';

// --- Props ---
const props = defineProps<{
    files: FileTreeNode[];
    branch: string | undefined;
    setFiles: (files: FileTreeNode[]) => void;
    setBranch: (branch: string) => void;
    repo: Repo;
    nodeId: string;
}>();

// --- Composables ---
const { getIconForFile } = useFileIcons();
const graphEvents = useGraphEvents();

// --- Local State ---
const selectedFiles = ref<FileTreeNode[]>(props.files);
const iconFilesMost = computed(() => {
    const map: Record<string, number> = {};
    selectedFiles.value.forEach((file) => {
        const icon = getIconForFile(file.name) || 'MdiFileOutline';
        map[icon] = (map[icon] || 0) + 1;
    });
    return Object.entries(map)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
        .map(([icon]) => icon);
});

// --- Core Logic Functions ---
const fetchRepoTree = async () => {
    if (!props.repo) return;

    const initialBranch = props.branch || props.repo.default_branch || 'main';

    graphEvents.emit('open-github-file-select', {
        repoContent: {
            repo: props.repo,
            selectedFiles: selectedFiles.value,
            currentBranch: initialBranch,
        },
        nodeId: props.nodeId,
    });
};

watch(
    () => selectedFiles.value,
    (newSelectedFiles) => {
        props.setFiles(newSelectedFiles);
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on(
        'close-github-file-select',
        ({ selectedFilePaths, nodeId, branch }) => {
            if (nodeId === props.nodeId) {
                selectedFiles.value = selectedFilePaths;
                if (branch) {
                    props.setBranch(branch);
                }
            }
        },
    );

    onUnmounted(unsubscribe);
});
</script>

<template>
    <div class="w-full grow">
        <button
            v-if="props.files"
            class="group nodrag bg-stone-gray/5 text-stone-gray/50 hover:text-stone-gray relative flex h-full w-full
                cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl p-1
                duration-300 ease-in-out"
            :class="{
                'border-stone-gray/20 hover:border-stone-gray/30 border-2 border-dashed':
                    selectedFiles.length === 0,
            }"
            @click.prevent="fetchRepoTree"
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
            />

            <div
                v-if="selectedFiles.length === 0"
                class="relative z-10 flex flex-col items-center gap-2 text-center"
            >
                <UiIcon
                    name="Fa6SolidPlus"
                    class="text-stone-gray/50 group-hover:text-stone-gray h-5 w-5 transition-colors"
                />
                <div class="flex flex-col">
                    <span class="font-semibold">Select Files</span>
                    <span class="text-xs">from repository</span>
                </div>
            </div>

            <div v-else class="relative z-10 flex flex-col items-center gap-2 text-center">
                <div
                    class="border-soft-silk/10 bg-github/80 flex w-fit items-center gap-1 rounded-lg border p-1.5"
                >
                    <UiIcon
                        v-for="icon in iconFilesMost"
                        :key="icon"
                        :name="`fileTree/${icon}`"
                        class="h-5 w-5 text-transparent"
                        :class="{
                            '!text-white/80': icon === 'MdiFileOutline',
                        }"
                    />
                </div>
                <div class="flex flex-col">
                    <span class="font-semibold">{{ selectedFiles.length }} file(s) selected</span>
                    <span class="text-xs group-hover:underline">Click to edit</span>
                </div>
            </div>
        </button>
    </div>
</template>

<style scoped></style>
