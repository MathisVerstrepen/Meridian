<script lang="ts" setup>
import type { AdminMediaGenerationUsage, AdminUsageDashboardResponse } from '@/types/admin';

const DASHBOARD_WINDOW_OPTIONS = [
    { days: 7, label: '7d' },
    { days: 30, label: '30d' },
    { days: 90, label: '90d' },
    { days: 365, label: '1y' },
] as const;

const isInitialLoading = ref(true);
const isDashboardLoading = ref(false);
const dashboard = ref<AdminUsageDashboardResponse | null>(null);
const dashboardActiveDays = ref<(typeof DASHBOARD_WINDOW_OPTIONS)[number]['days']>(30);
const dashboardLastUpdated = ref<Date | null>(null);

const { error: showToastError } = useToast();
const { apiFetch } = useAPI();
const { formatFileSize } = useFormatters();

const dashboardWindowLabel = computed(
    () => `${dashboard.value?.active_days ?? dashboardActiveDays.value} days`,
);
const totalMediaJobs = computed(
    () => (dashboard.value?.image_generation.total ?? 0) + (dashboard.value?.video_generation.total ?? 0),
);
const recentMediaJobs = computed(
    () =>
        (dashboard.value?.image_generation.recent_total ?? 0) +
        (dashboard.value?.video_generation.recent_total ?? 0),
);
const activeMediaJobs = computed(
    () =>
        (dashboard.value ? getMediaActiveCount(dashboard.value.image_generation) : 0) +
        (dashboard.value ? getMediaActiveCount(dashboard.value.video_generation) : 0),
);
const failedMediaJobs = computed(
    () => (dashboard.value?.image_generation.failed ?? 0) + (dashboard.value?.video_generation.failed ?? 0),
);
const completedMediaJobs = computed(
    () =>
        (dashboard.value?.image_generation.completed ?? 0) +
        (dashboard.value?.video_generation.completed ?? 0),
);
const dashboardLastUpdatedLabel = computed(() => {
    if (!dashboardLastUpdated.value) return 'Not refreshed yet';
    return dashboardLastUpdated.value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
});

const activeUserPercentage = computed(() =>
    getUsagePercentage(dashboard.value?.users.active ?? 0, dashboard.value?.users.total ?? 0),
);

type MediaStatusBreakdown = {
    label: string;
    count: number;
    color: string;
    bgClass: string;
    textClass: string;
};

const getMediaBreakdown = (usage: AdminMediaGenerationUsage): MediaStatusBreakdown[] => [
    {
        label: 'Completed',
        count: usage.completed,
        color: 'bg-green-400',
        bgClass: 'bg-green-500/10',
        textClass: 'text-green-400',
    },
    {
        label: 'Active',
        count: getMediaActiveCount(usage),
        color: 'bg-ember-glow',
        bgClass: 'bg-ember-glow/10',
        textClass: 'text-ember-glow',
    },
    {
        label: 'Failed',
        count: usage.failed,
        color: 'bg-red-400',
        bgClass: 'bg-red-500/10',
        textClass: 'text-red-400',
    },
    {
        label: 'Cancelled',
        count: usage.cancelled,
        color: 'bg-stone-gray/40',
        bgClass: 'bg-stone-gray/10',
        textClass: 'text-stone-gray/60',
    },
];

const getUsagePercentage = (used: number, total: number) => {
    if (total <= 0) return 0;
    return Math.min(Math.round((used / total) * 100), 100);
};

const formatCount = (value: number) => new Intl.NumberFormat().format(value);

const formatPercentage = (value: number, total: number) => {
    if (total <= 0) return '0%';
    return `${Math.round((value / total) * 100)}%`;
};

const formatDashboardValue = (value: number | undefined) => {
    if (isDashboardLoading.value && !dashboard.value) return '...';
    return formatCount(value ?? 0);
};

const getMediaActiveCount = (usage: AdminMediaGenerationUsage) =>
    usage.pending + usage.processing + usage.retrying;

const getMediaCompletionRate = (usage: AdminMediaGenerationUsage) =>
    formatPercentage(usage.completed, usage.total);

const fetchDashboard = async () => {
    isDashboardLoading.value = true;
    try {
        dashboard.value = await apiFetch<AdminUsageDashboardResponse>(
            `/api/admin/usage-dashboard?active_days=${dashboardActiveDays.value}`,
        );
        dashboardLastUpdated.value = new Date();
    } catch (err) {
        showToastError('Failed to fetch usage dashboard');
        console.error(err);
    } finally {
        isDashboardLoading.value = false;
        isInitialLoading.value = false;
    }
};

const selectDashboardWindow = (days: (typeof DASHBOARD_WINDOW_OPTIONS)[number]['days']) => {
    dashboardActiveDays.value = days;
    void fetchDashboard();
};

onMounted(() => {
    fetchDashboard();
});
</script>

<template>
    <div class="flex flex-col gap-5">
        <!-- Hero header -->
        <section
            class="from-stone-gray/10 via-stone-gray/5 border-stone-gray/10 rounded-2xl border
                bg-linear-to-br to-transparent p-4 sm:p-5"
        >
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                    <div class="text-stone-gray/60 text-xs font-semibold tracking-[0.2em] uppercase">
                        Admin Analytics
                    </div>
                    <h4 class="text-soft-silk mt-1 text-xl font-semibold">Usage Dashboard</h4>
                    <p class="text-stone-gray/60 mt-1 max-w-2xl text-sm">
                        Activity is estimated from graph updates, media jobs, and tool calls over the
                        selected window.
                    </p>
                </div>

                <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <div
                        class="border-stone-gray/10 bg-obsidian/50 flex rounded-xl border p-1"
                        aria-label="Dashboard time window"
                    >
                        <button
                            v-for="opt in DASHBOARD_WINDOW_OPTIONS"
                            :key="opt.days"
                            type="button"
                            class="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
                            :class="
                                dashboardActiveDays === opt.days
                                    ? 'bg-ember-glow/15 text-ember-glow'
                                    : 'text-stone-gray/70 hover:text-soft-silk'
                            "
                            @click="selectDashboardWindow(opt.days)"
                        >
                            {{ opt.label }}
                        </button>
                    </div>

                    <button
                        type="button"
                        class="border-stone-gray/15 bg-stone-gray/5 text-soft-silk hover:bg-stone-gray/10
                            flex items-center justify-center gap-2 rounded-xl border px-3 py-2 text-xs
                            font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                        :disabled="isDashboardLoading"
                        @click="fetchDashboard"
                    >
                        <UiIcon
                            name="MaterialSymbolsRestartAltRounded"
                            class="h-4 w-4"
                            :class="{ 'animate-spin': isDashboardLoading }"
                        />
                        Refresh
                    </button>
                </div>
            </div>

            <div class="text-stone-gray/55 mt-4 flex flex-wrap items-center gap-2 text-xs">
                <span class="border-stone-gray/10 rounded-full border px-2.5 py-1">
                    Window: last {{ dashboardWindowLabel }}
                </span>
                <span class="border-stone-gray/10 rounded-full border px-2.5 py-1">
                    Last updated: {{ dashboardLastUpdatedLabel }}
                </span>
                <span v-if="isDashboardLoading" class="text-ember-glow rounded-full px-2.5 py-1">
                    Refreshing metrics...
                </span>
            </div>
        </section>

        <!-- KPI Cards -->
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <!-- Users KPI -->
            <article
                class="border-stone-gray/10 bg-stone-gray/5 relative overflow-hidden rounded-2xl border
                    p-4 shadow-lg shadow-black/5"
            >
                <div
                    class="bg-ember-glow/5 absolute top-0 right-0 h-24 w-24 rounded-full blur-2xl"
                ></div>
                <div class="relative flex items-start justify-between gap-3">
                    <div>
                        <p class="text-stone-gray/60 text-xs font-semibold uppercase tracking-wide">
                            Users
                        </p>
                        <div class="text-soft-silk mt-2 text-3xl font-bold">
                            {{ formatDashboardValue(dashboard?.users.total) }}
                        </div>
                        <div class="mt-1.5 flex items-center gap-2 text-xs">
                            <span class="text-green-400 flex items-center gap-0.5 font-medium">
                                <UiIcon name="MdiArrowUp" class="h-3 w-3" />
                                {{ activeUserPercentage }}%
                            </span>
                            <span class="text-stone-gray/50">active</span>
                        </div>
                    </div>
                    <div class="bg-ember-glow/10 rounded-xl p-2.5">
                        <UiIcon name="MaterialSymbolsGroupRounded" class="text-ember-glow h-5 w-5" />
                    </div>
                </div>
                <div class="relative mt-4 grid grid-cols-2 gap-2 text-xs">
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Active</span>
                        <div class="text-green-400 mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.users.active) }}
                        </div>
                    </div>
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">New</span>
                        <div class="text-soft-silk mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.users.new_users) }}
                        </div>
                    </div>
                </div>
            </article>

            <!-- Graphs KPI -->
            <article
                class="border-stone-gray/10 bg-stone-gray/5 relative overflow-hidden rounded-2xl border p-4"
            >
                <div
                    class="absolute top-0 right-0 h-24 w-24 rounded-full bg-sky-400/5 blur-2xl"
                ></div>
                <div class="relative flex items-start justify-between gap-3">
                    <div>
                        <p class="text-stone-gray/60 text-xs font-semibold uppercase tracking-wide">
                            Graphs
                        </p>
                        <div class="text-soft-silk mt-2 text-3xl font-bold">
                            {{ formatDashboardValue(dashboard?.graphs.total) }}
                        </div>
                        <p class="text-stone-gray/50 mt-1.5 text-xs">
                            {{ formatDashboardValue(dashboard?.graphs.temporary) }} temporary
                        </p>
                    </div>
                    <div class="rounded-xl bg-sky-400/10 p-2.5">
                        <UiIcon name="MaterialSymbolsAccountTreeRounded" class="h-5 w-5 text-sky-400" />
                    </div>
                </div>
                <div class="relative mt-4 grid grid-cols-2 gap-2 text-xs">
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Updated</span>
                        <div class="text-soft-silk mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.graphs.active) }}
                        </div>
                    </div>
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Created</span>
                        <div class="text-soft-silk mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.graphs.created) }}
                        </div>
                    </div>
                </div>
            </article>

            <!-- Storage KPI -->
            <article
                class="border-stone-gray/10 bg-stone-gray/5 relative overflow-hidden rounded-2xl border p-4"
            >
                <div
                    class="absolute top-0 right-0 h-24 w-24 rounded-full bg-violet-400/5 blur-2xl"
                ></div>
                <div class="relative flex items-start justify-between gap-3">
                    <div>
                        <p class="text-stone-gray/60 text-xs font-semibold uppercase tracking-wide">
                            Storage
                        </p>
                        <div class="text-soft-silk mt-2 text-3xl font-bold">
                            {{ formatFileSize(dashboard?.storage.used_bytes ?? 0) }}
                        </div>
                        <p class="text-stone-gray/50 mt-1.5 text-xs">across all users</p>
                    </div>
                    <div class="rounded-xl bg-violet-400/10 p-2.5">
                        <UiIcon name="MdiDatabaseOutline" class="h-5 w-5 text-violet-300" />
                    </div>
                </div>
                <div class="relative mt-4 grid grid-cols-2 gap-2 text-xs">
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Users w/ files</span>
                        <div class="text-soft-silk mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.storage.users_with_storage) }}
                        </div>
                    </div>
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Pinned graphs</span>
                        <div class="text-soft-silk mt-0.5 font-semibold">
                            {{ formatDashboardValue(dashboard?.graphs.pinned) }}
                        </div>
                    </div>
                </div>
            </article>

            <!-- Media KPI -->
            <article
                class="border-stone-gray/10 bg-stone-gray/5 relative overflow-hidden rounded-2xl border p-4"
            >
                <div
                    class="absolute top-0 right-0 h-24 w-24 rounded-full bg-golden-ochre/5 blur-2xl"
                ></div>
                <div class="relative flex items-start justify-between gap-3">
                    <div>
                        <p class="text-stone-gray/60 text-xs font-semibold uppercase tracking-wide">
                            Media
                        </p>
                        <div class="text-soft-silk mt-2 text-3xl font-bold">
                            {{ formatDashboardValue(totalMediaJobs) }}
                        </div>
                        <p class="text-stone-gray/50 mt-1.5 text-xs">
                            {{ formatDashboardValue(recentMediaJobs) }} in window
                        </p>
                    </div>
                    <div class="bg-golden-ochre/10 rounded-xl p-2.5">
                        <UiIcon
                            name="MaterialSymbolsAutoAwesomeRounded"
                            class="text-golden-ochre h-5 w-5"
                        />
                    </div>
                </div>
                <div class="relative mt-4 grid grid-cols-3 gap-2 text-xs">
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Active</span>
                        <div class="text-ember-glow mt-0.5 font-semibold">
                            {{ formatDashboardValue(activeMediaJobs) }}
                        </div>
                    </div>
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Failed</span>
                        <div class="mt-0.5 font-semibold text-red-400">
                            {{ formatDashboardValue(failedMediaJobs) }}
                        </div>
                    </div>
                    <div class="bg-black/20 rounded-lg p-2">
                        <span class="text-stone-gray/55">Done</span>
                        <div class="text-green-400 mt-0.5 font-semibold">
                            {{ formatDashboardValue(completedMediaJobs) }}
                        </div>
                    </div>
                </div>
            </article>
        </div>

        <!-- Skeleton state on initial load -->
        <div
            v-if="isInitialLoading"
            class="border-stone-gray/10 grid gap-4 rounded-2xl border bg-stone-gray/5 p-4 xl:grid-cols-2"
        >
            <div
                v-for="i in 4"
                :key="i"
                class="bg-stone-gray/10 h-48 animate-pulse rounded-xl"
            ></div>
        </div>

        <template v-else>
            <!-- Account Health & Graph Footprint -->
            <div class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                <section
                    class="border-stone-gray/10 bg-stone-gray/5 rounded-2xl border p-4 sm:p-5"
                >
                    <div class="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                        <div>
                            <h4 class="text-soft-silk text-sm font-semibold">Account Health</h4>
                            <p class="text-stone-gray/55 text-xs">
                                Verification, plans, and admin-risk signals.
                            </p>
                        </div>
                        <span
                            class="bg-ember-glow/10 text-ember-glow rounded-full px-2.5 py-1 text-xs font-medium"
                        >
                            {{ activeUserPercentage }}% active
                        </span>
                    </div>

                    <div class="space-y-5">
                        <div>
                            <div class="mb-2 flex items-center justify-between text-xs">
                                <span class="text-stone-gray/70">Verified accounts</span>
                                <span class="text-soft-silk font-semibold">
                                    {{ formatDashboardValue(dashboard?.users.verified) }} /
                                    {{ formatDashboardValue(dashboard?.users.total) }}
                                </span>
                            </div>
                            <div class="bg-stone-gray/15 h-2.5 overflow-hidden rounded-full">
                                <div
                                    class="h-full rounded-full bg-green-400 transition-all duration-500"
                                    :style="{
                                        width: `${getUsagePercentage(
                                            dashboard?.users.verified ?? 0,
                                            dashboard?.users.total ?? 0,
                                        )}%`,
                                    }"
                                ></div>
                            </div>
                        </div>

                        <div>
                            <div class="mb-2 flex items-center justify-between text-xs">
                                <span class="text-stone-gray/70">Plan split</span>
                                <span class="text-soft-silk font-semibold">
                                    {{ formatDashboardValue(dashboard?.users.premium_plan) }} premium
                                </span>
                            </div>
                            <div class="bg-stone-gray/15 flex h-2.5 overflow-hidden rounded-full">
                                <div
                                    class="bg-ember-glow h-full transition-all duration-500"
                                    :style="{
                                        width: `${getUsagePercentage(
                                            dashboard?.users.premium_plan ?? 0,
                                            dashboard?.users.total ?? 0,
                                        )}%`,
                                    }"
                                ></div>
                                <div
                                    class="bg-stone-gray/40 h-full transition-all duration-500"
                                    :style="{
                                        width: `${getUsagePercentage(
                                            dashboard?.users.free_plan ?? 0,
                                            dashboard?.users.total ?? 0,
                                        )}%`,
                                    }"
                                ></div>
                            </div>
                        </div>

                        <div class="grid gap-2 sm:grid-cols-4">
                            <div class="bg-black/20 rounded-xl border border-stone-gray/10 p-3">
                                <span class="text-stone-gray/55 text-xs">Premium</span>
                                <div class="text-soft-silk mt-1 text-lg font-semibold">
                                    {{ formatDashboardValue(dashboard?.users.premium_plan) }}
                                </div>
                            </div>
                            <div class="bg-black/20 rounded-xl border border-stone-gray/10 p-3">
                                <span class="text-stone-gray/55 text-xs">Free</span>
                                <div class="text-soft-silk mt-1 text-lg font-semibold">
                                    {{ formatDashboardValue(dashboard?.users.free_plan) }}
                                </div>
                            </div>
                            <div class="bg-black/20 rounded-xl border border-stone-gray/10 p-3">
                                <span class="text-stone-gray/55 text-xs">Admins</span>
                                <div class="text-ember-glow mt-1 text-lg font-semibold">
                                    {{ formatDashboardValue(dashboard?.users.admins) }}
                                </div>
                            </div>
                            <div
                                class="rounded-xl border border-red-500/10 bg-red-500/5 p-3"
                            >
                                <span class="text-stone-gray/55 text-xs">Suspended</span>
                                <div class="mt-1 text-lg font-semibold text-red-400">
                                    {{ formatDashboardValue(dashboard?.users.suspended) }}
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section
                    class="border-stone-gray/10 bg-stone-gray/5 rounded-2xl border p-4 sm:p-5"
                >
                    <div class="mb-5">
                        <h4 class="text-soft-silk text-sm font-semibold">Graph & File Footprint</h4>
                        <p class="text-stone-gray/55 text-xs">
                            Canvas inventory and storage adoption.
                        </p>
                    </div>

                    <div class="grid gap-2 sm:grid-cols-2">
                        <div class="bg-black/20 rounded-xl p-3">
                            <span class="text-stone-gray/55 text-xs">Saved graphs</span>
                            <div class="text-soft-silk mt-1 text-xl font-semibold">
                                {{ formatDashboardValue(dashboard?.graphs.total) }}
                            </div>
                            <p class="text-stone-gray/50 mt-1 text-xs">
                                {{ formatDashboardValue(dashboard?.graphs.pinned) }} pinned
                            </p>
                        </div>
                        <div class="bg-black/20 rounded-xl p-3">
                            <span class="text-stone-gray/55 text-xs">Temporary graphs</span>
                            <div class="text-soft-silk mt-1 text-xl font-semibold">
                                {{ formatDashboardValue(dashboard?.graphs.temporary) }}
                            </div>
                            <p class="text-stone-gray/50 mt-1 text-xs">Scratch canvases tracked</p>
                        </div>
                        <div class="bg-black/20 rounded-xl p-3">
                            <span class="text-stone-gray/55 text-xs">Active graphs</span>
                            <div class="text-soft-silk mt-1 text-xl font-semibold">
                                {{ formatDashboardValue(dashboard?.graphs.active) }}
                            </div>
                            <p class="text-stone-gray/50 mt-1 text-xs">
                                Updated in {{ dashboardWindowLabel }}
                            </p>
                        </div>
                        <div class="bg-black/20 rounded-xl p-3">
                            <span class="text-stone-gray/55 text-xs">Storage users</span>
                            <div class="text-soft-silk mt-1 text-xl font-semibold">
                                {{ formatDashboardValue(dashboard?.storage.users_with_storage) }}
                            </div>
                            <p class="text-stone-gray/50 mt-1 text-xs">
                                {{ formatFileSize(dashboard?.storage.used_bytes ?? 0) }} total
                            </p>
                        </div>
                    </div>
                </section>
            </div>

            <!-- Metered Usage & Media Health -->
            <div class="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
                <section
                    class="border-stone-gray/10 bg-stone-gray/5 rounded-2xl border p-4 sm:p-5"
                >
                    <div class="mb-5">
                        <h4 class="text-soft-silk text-sm font-semibold">Metered Usage</h4>
                        <p class="text-stone-gray/55 text-xs">
                            Current query counters across all user billing windows.
                        </p>
                    </div>
                    <div class="space-y-3">
                        <div
                            class="rounded-xl border border-ember-glow/15 bg-ember-glow/5 p-4"
                        >
                            <div class="flex items-center justify-between gap-3">
                                <div class="flex items-center gap-2">
                                    <UiIcon
                                        name="MdiMagnify"
                                        class="text-ember-glow h-4 w-4"
                                    />
                                    <span class="text-stone-gray/70 text-xs font-medium">
                                        Web searches
                                    </span>
                                </div>
                                <span class="text-stone-gray/55 text-xs">
                                    {{ formatDashboardValue(dashboard?.query_usage.users_with_web_search_usage) }}
                                    users
                                </span>
                            </div>
                            <div class="text-soft-silk mt-2 text-2xl font-bold">
                                {{ formatDashboardValue(dashboard?.query_usage.web_search_used) }}
                            </div>
                        </div>
                        <div
                            class="rounded-xl border border-golden-ochre/15 bg-golden-ochre/5 p-4"
                        >
                            <div class="flex items-center justify-between gap-3">
                                <div class="flex items-center gap-2">
                                    <UiIcon
                                        name="MdiLinkVariant"
                                        class="text-golden-ochre h-4 w-4"
                                    />
                                    <span class="text-stone-gray/70 text-xs font-medium">
                                        Link extractions
                                    </span>
                                </div>
                                <span class="text-stone-gray/55 text-xs">
                                    {{ formatDashboardValue(dashboard?.query_usage.users_with_link_extraction_usage) }}
                                    users
                                </span>
                            </div>
                            <div class="text-soft-silk mt-2 text-2xl font-bold">
                                {{ formatDashboardValue(dashboard?.query_usage.link_extraction_used) }}
                            </div>
                        </div>
                    </div>
                </section>

                <section
                    class="border-stone-gray/10 bg-stone-gray/5 rounded-2xl border p-4 sm:p-5"
                >
                    <div class="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                        <div>
                            <h4 class="text-soft-silk text-sm font-semibold">
                                Media Generation Health
                            </h4>
                            <p class="text-stone-gray/55 text-xs">
                                Image and video jobs by status and recent volume.
                            </p>
                        </div>
                        <div class="text-stone-gray/55 flex items-center gap-3 text-xs">
                            <span>{{ formatDashboardValue(recentMediaJobs) }} recent</span>
                            <span class="text-stone-gray/30">|</span>
                            <span class="text-red-400">
                                {{ formatDashboardValue(failedMediaJobs) }} failed
                            </span>
                        </div>
                    </div>

                    <div v-if="dashboard" class="grid gap-3 lg:grid-cols-2">
                        <div
                            v-for="media in [
                                { type: 'Images', usage: dashboard.image_generation, icon: 'MaterialSymbolsImageRounded' },
                                { type: 'Videos', usage: dashboard.video_generation, icon: 'MaterialSymbolsVideoCameraBackRounded' },
                            ]"
                            :key="media.type"
                            class="bg-black/20 rounded-xl border border-stone-gray/10 p-4"
                        >
                            <div class="mb-4 flex items-center justify-between gap-3">
                                <div class="flex items-center gap-2">
                                    <UiIcon
                                        :name="media.icon"
                                        class="text-stone-gray/60 h-4 w-4"
                                    />
                                    <div>
                                        <h5 class="text-soft-silk text-sm font-semibold">
                                            {{ media.type }}
                                        </h5>
                                        <p class="text-stone-gray/55 text-xs">
                                            {{ formatCount(media.usage.total) }} lifetime
                                        </p>
                                    </div>
                                </div>
                                <span
                                    class="bg-green-500/10 text-green-400 rounded-full px-2.5 py-1 text-xs font-medium"
                                >
                                    {{ getMediaCompletionRate(media.usage) }}
                                </span>
                            </div>

                            <div
                                class="bg-stone-gray/15 flex h-2.5 overflow-hidden rounded-full"
                            >
                                <div
                                    v-for="(seg, idx) in getMediaBreakdown(media.usage)"
                                    :key="seg.label"
                                    :class="seg.color"
                                    class="h-full transition-all duration-500"
                                    :style="{
                                        width: `${getUsagePercentage(
                                            seg.count,
                                            media.usage.total,
                                        )}%`,
                                    }"
                                >
                                    <span v-if="idx === 0" class="block h-full w-full"></span>
                                </div>
                            </div>

                            <div class="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                                <div
                                    v-for="seg in getMediaBreakdown(media.usage)"
                                    :key="seg.label"
                                    class="flex items-center gap-1.5"
                                >
                                    <span :class="seg.color" class="h-2 w-2 rounded-full"></span>
                                    <span class="text-stone-gray/60">{{ seg.label }}</span>
                                    <span :class="seg.textClass" class="ml-auto font-medium">
                                        {{ formatCount(seg.count) }}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else class="grid gap-3 lg:grid-cols-2">
                        <div class="bg-stone-gray/10 h-48 animate-pulse rounded-xl"></div>
                        <div class="bg-stone-gray/10 h-48 animate-pulse rounded-xl"></div>
                    </div>
                </section>
            </div>
        </template>
    </div>
</template>
