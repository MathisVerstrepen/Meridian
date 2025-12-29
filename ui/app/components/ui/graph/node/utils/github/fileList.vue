<script lang="ts" setup>
import type { FileTreeNode, RepositoryInfo, GithubIssue } from '@/types/github';

// --- Props ---
const props = defineProps<{
    files: FileTreeNode[];
    issues?: GithubIssue[];
    branch: string | undefined;
    setFiles: (files: FileTreeNode[]) => void;
    setIssues?: (issues: GithubIssue[]) => void;
    setBranch: (branch: string) => void;
    repo: RepositoryInfo;
    nodeId: string;
}>();

// --- Composables ---
const { getIconForFile } = useFileIcons();
const graphEvents = useGraphEvents();

// --- Local State ---
const selectedFiles = ref<FileTreeNode[]>(props.files);
const selectedIssues = ref<GithubIssue[]>(props.issues || []);

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

const providerBgClass = computed(() => {
    return props.repo.provider === 'gitlab' ? 'bg-gitlab/80' : 'bg-github/80';
});

// --- Core Logic Functions ---
const fetchRepoTree = async () => {
    if (!props.repo) return;

    const initialBranch = props.branch || props.repo.default_branch || 'main';

    graphEvents.emit('open-github-file-select', {
        repoContent: {
            repo: props.repo,
            selectedFiles: selectedFiles.value,
            selectedIssues: selectedIssues.value,
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

watch(
    () => selectedIssues.value,
    (newSelectedIssues) => {
        if (props.setIssues) {
            props.setIssues(newSelectedIssues);
        }
    },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on(
        'close-github-file-select',
        ({ selectedFilePaths, selectedIssues: newSelectedIssues, nodeId, branch }) => {
            if (nodeId === props.nodeId) {
                selectedFiles.value = selectedFilePaths;
                if (newSelectedIssues) {
                    selectedIssues.value = newSelectedIssues;
                }
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
            class="group nodrag bg-stone-gray/5 text-stone-gray/50 hover:text-stone-gray relative
                flex h-full w-full cursor-pointer flex-col items-center justify-center gap-2
                overflow-hidden rounded-xl p-1 duration-300 ease-in-out"
            :class="{
                'border-stone-gray/20 hover:border-stone-gray/30 border-2 border-dashed':
                    selectedFiles.length === 0 && selectedIssues.length === 0,
            }"
            @click.prevent="fetchRepoTree"
        >
            <div
                class="absolute inset-0 opacity-0 transition-opacity duration-300 ease-in-out
                    group-hover:opacity-100"
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
                v-if="selectedFiles.length === 0 && selectedIssues.length === 0"
                class="relative z-10 flex flex-col items-center gap-2 text-center"
            >
                <UiIcon
                    name="Fa6SolidPlus"
                    class="text-stone-gray/50 group-hover:text-stone-gray h-5 w-5 transition-colors"
                />
                <div class="flex flex-col">
                    <span class="font-semibold">Select Context</span>
                    <span class="text-xs">Files, Issues or PRs</span>
                </div>
            </div>

            <div v-else class="relative z-10 flex flex-col items-center gap-2 text-center">
                <div
                    class="border-soft-silk/10 flex w-fit items-center gap-1 rounded-lg border
                        p-1.5"
                    :class="providerBgClass"
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
                    <UiIcon
                        v-if="selectedIssues.length > 0"
                        name="MdiSourcePull"
                        class="h-5 w-5 text-white/80"
                    />
                </div>
                <div class="flex flex-col">
                    <span class="font-semibold">
                        {{ selectedFiles.length }} file(s), {{ selectedIssues.length }} issue(s)
                    </span>
                    <span class="text-xs group-hover:underline">Click to edit</span>
                </div>
            </div>
        </button>
    </div>
</template>

<style scoped></style>
