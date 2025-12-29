<script lang="ts" setup>
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller';
import type { GithubIssue, RepositoryInfo } from '@/types/github';

// --- Props ---
const props = defineProps<{
    repo: RepositoryInfo;
    initialSelectedIssues: GithubIssue[];
}>();

// --- Emits ---
const emit = defineEmits<{
    (e: 'update:selectedIssues', issues: GithubIssue[]): void;
    (e: 'close'): void;
}>();

// --- Composables ---
const { apiFetch } = useAPI();
const { error } = useToast();

// --- State ---
const issues = ref<GithubIssue[]>([]);
const selectedIssues = ref<Set<number>>(new Set(props.initialSelectedIssues.map((i) => i.id)));
const isLoading = ref(false);
const searchQuery = ref('');
const filterState = ref<'all' | 'open' | 'closed'>('open');
const filterType = ref<'all' | 'issue' | 'pr'>('all');

// --- Computed ---
const filteredIssues = computed(() => {
    return issues.value.filter((issue) => {
        // Search Filter
        const searchLower = searchQuery.value.toLowerCase();
        const matchesSearch =
            issue.title.toLowerCase().includes(searchLower) ||
            issue.number.toString().includes(searchLower) ||
            issue.user_login.toLowerCase().includes(searchLower);

        if (!matchesSearch) return false;

        // Type Filter
        if (filterType.value === 'issue' && issue.is_pull_request) return false;
        if (filterType.value === 'pr' && !issue.is_pull_request) return false;

        return true;
    });
});

const selectedIssuesList = computed(() => {
    return issues.value.filter((i) => selectedIssues.value.has(i.id));
});

// --- Methods ---
const fetchIssues = async () => {
    isLoading.value = true;
    try {
        const params = new URLSearchParams({
            repo_full_name: props.repo.full_name,
            state: filterState.value,
        });
        const data = await apiFetch<GithubIssue[]>(`/api/github/issues?${params.toString()}`);
        issues.value = data;

        // Ensure previously selected issues are in the list or preserve them
        const currentIds = new Set(data.map((i) => i.id));
        const missingSelected = props.initialSelectedIssues.filter((i) => !currentIds.has(i.id));
        if (missingSelected.length > 0) {
            issues.value = [...missingSelected, ...issues.value];
        }
    } catch (e) {
        console.error(e);
        error('Failed to fetch issues');
    } finally {
        isLoading.value = false;
    }
};

const toggleIssue = (issue: GithubIssue) => {
    if (selectedIssues.value.has(issue.id)) {
        selectedIssues.value.delete(issue.id);
    } else {
        selectedIssues.value.add(issue.id);
    }
    emit('update:selectedIssues', selectedIssuesList.value);
};

const confirmSelection = () => {
    emit('close');
};

// --- Watchers ---
watch(filterState, () => {
    fetchIssues();
});

// --- Lifecycle ---
onMounted(() => {
    fetchIssues();
});
</script>

<template>
    <div class="flex h-full w-full flex-col">
        <!-- Header -->
        <div class="border-stone-gray/20 mb-4 flex items-center justify-between border-b pb-4">
            <div class="flex items-center gap-2">
                <UiIcon name="MdiGithub" class="text-soft-silk h-6 w-6" />
                <h2 class="text-soft-silk text-xl font-bold">Select Issues & PRs</h2>
                <span class="text-stone-gray/40 ml-2 translate-y-0.5 text-sm">from</span>
                <span class="text-soft-silk/80 translate-y-0.5 text-sm">{{ repo.full_name }}</span>
            </div>
        </div>

        <!-- Controls -->
        <div class="mb-4 flex gap-2">
            <!-- Search -->
            <div class="group relative grow">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2"
                />
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search issues, PRs, authors..."
                    class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow
                        w-full rounded-lg border py-2 pl-10 transition-colors focus:outline-none"
                />
            </div>

            <!-- State Filter -->
            <div class="bg-obsidian border-stone-gray/20 flex rounded-lg border p-1">
                <button
                    v-for="state in ['open', 'closed', 'all'] as const"
                    :key="state"
                    class="rounded-md px-3 py-1 text-sm capitalize transition-colors"
                    :class="
                        filterState === state
                            ? 'bg-stone-gray/20 text-soft-silk'
                            : 'text-stone-gray/60 hover:text-soft-silk'
                    "
                    @click="filterState = state"
                >
                    {{ state }}
                </button>
            </div>

            <!-- Type Filter -->
            <div class="bg-obsidian border-stone-gray/20 flex rounded-lg border p-1">
                <button
                    v-for="type in ['all', 'issue', 'pr'] as const"
                    :key="type"
                    class="rounded-md px-3 py-1 text-sm uppercase transition-colors"
                    :class="
                        filterType === type
                            ? 'bg-stone-gray/20 text-soft-silk'
                            : 'text-stone-gray/60 hover:text-soft-silk'
                    "
                    @click="filterType = type"
                >
                    {{ type === 'pr' ? 'PR' : type }}
                </button>
            </div>
        </div>

        <!-- List -->
        <div
            class="bg-obsidian/50 border-stone-gray/20 flex-grow overflow-hidden rounded-lg border"
        >
            <div v-if="isLoading" class="flex h-full items-center justify-center gap-2">
                <UiIcon
                    name="MingcuteLoading3Fill"
                    class="text-stone-gray/50 h-6 w-6 animate-spin"
                />
                <span class="text-stone-gray/50">Loading issues...</span>
            </div>

            <div
                v-else-if="filteredIssues.length === 0"
                class="text-stone-gray/40 flex h-full items-center justify-center"
            >
                No issues found matching your filters.
            </div>

            <DynamicScroller
                v-else
                :items="filteredIssues"
                :min-item-size="80"
                class="dark-scrollbar h-full w-full px-2 py-2"
                key-field="id"
            >
                <template #default="{ item, index, active }">
                    <DynamicScrollerItem
                        :item="item"
                        :active="active"
                        :data-index="index"
                        class="pb-2"
                    >
                        <UiGraphNodeUtilsGithubIssuePrItem
                            :item="item"
                            :selected="selectedIssues.has(item.id)"
                            @toggle="toggleIssue(item)"
                        />
                    </DynamicScrollerItem>
                </template>
            </DynamicScroller>
        </div>

        <!-- Footer -->
        <div class="mt-4 flex justify-end gap-3">
            <button
                class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk cursor-pointer
                    rounded-lg px-4 py-2 transition-colors duration-200 ease-in-out"
                @click="$emit('close')"
            >
                Cancel
            </button>
            <button
                class="bg-ember-glow text-soft-silk cursor-pointer rounded-lg px-4 py-2
                    transition-colors duration-200 ease-in-out hover:brightness-90"
                @click="confirmSelection"
            >
                Confirm Selection ({{ selectedIssues.size }})
            </button>
        </div>
    </div>
</template>
