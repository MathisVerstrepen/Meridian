<script lang="ts" setup>
// --- Stores ---
const usageStore = useUsageStore();

// --- State from Stores ---
const { webSearchUsage, linkExtractionUsage, storageUsage, isLoading } = storeToRefs(usageStore);

// --- Methods from Stores ---
const { getUsagePercentage, fetchUsage } = usageStore;

// --- Composables ---
const { formatFileSize } = useFormatters();

type StorageBreakdownMeta = {
    label: string;
    description: string;
    barClass: string;
};

type StorageBreakdownItem = {
    category: string;
    used_bytes: number;
    file_count: number;
};

const STORAGE_BREAKDOWN_META: Record<string, StorageBreakdownMeta> = {
    generated_images: {
        label: 'Generated images',
        description: 'Images created by generation tools.',
        barClass: 'bg-fuchsia-400',
    },
    generated_videos: {
        label: 'Generated videos',
        description: 'Videos created by generation tools.',
        barClass: 'bg-sky-400',
    },
    artifacts: {
        label: 'Artefacts',
        description: 'Files saved from code execution and visualisation tools.',
        barClass: 'bg-violet-400',
    },
    videos: {
        label: 'Videos',
        description: 'Uploaded video files.',
        barClass: 'bg-cyan-400',
    },
    images: {
        label: 'Images',
        description: 'Uploaded image files.',
        barClass: 'bg-emerald-400',
    },
    documents: {
        label: 'Documents',
        description: 'Text files, PDFs, and office documents.',
        barClass: 'bg-amber-300',
    },
    uploads: {
        label: 'Other uploads',
        description: 'Uploaded files that do not match another category.',
        barClass: 'bg-stone-gray',
    },
    other: {
        label: 'Other',
        description: 'Storage that could not be classified.',
        barClass: 'bg-stone-gray/70',
    },
};

const storageUsed = computed(() => formatFileSize(storageUsage.value.used_bytes));
const storageTotal = computed(() => formatFileSize(storageUsage.value.limit_bytes));
const storagePercentage = computed(() => {
    if (storageUsage.value.limit_bytes === 0) return 100;
    return Math.min(Math.round(storageUsage.value.percentage), 100);
});
const isStorageFull = computed(
    () => storageUsage.value.limit_bytes === 0 || storageUsage.value.used_bytes >= storageUsage.value.limit_bytes,
);
const storageBreakdown = computed(() => {
    const totalUsed = storageUsage.value.used_bytes;

    return storageUsage.value.breakdown
        .map((item: StorageBreakdownItem) => {
            const meta = STORAGE_BREAKDOWN_META[item.category] ?? STORAGE_BREAKDOWN_META.other;
            const percentage = totalUsed === 0 ? 0 : Math.min((item.used_bytes / totalUsed) * 100, 100);

            return {
                ...item,
                ...meta,
                percentage,
                formattedUsed: formatFileSize(item.used_bytes),
            };
        })
        .sort((a, b) => b.used_bytes - a.used_bytes);
});

onMounted(() => {
    fetchUsage();
});
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Web Search Query Usage -->
        <div class="py-6">
            <UiSettingsUtilsQueryUsage
                :billing-period-end="webSearchUsage.billing_period_end"
                :query-used="webSearchUsage.used"
                :query-total="webSearchUsage.total"
                :usage-percentage="getUsagePercentage(webSearchUsage.used, webSearchUsage.total)"
                :is-loading="isLoading"
                query-name="web search"
            />
        </div>

        <!-- Setting: Link Extraction Query Usage -->
        <div class="py-6">
            <UiSettingsUtilsQueryUsage
                :billing-period-end="linkExtractionUsage.billing_period_end"
                :query-used="linkExtractionUsage.used"
                :query-total="linkExtractionUsage.total"
                :usage-percentage="getUsagePercentage(
                    linkExtractionUsage.used,
                    linkExtractionUsage.total,
                )"
                :is-loading="isLoading"
                query-name="link extraction"
            />
        </div>

        <!-- Setting: Storage Usage -->
        <div class="py-6">
            <div class="w-full">
                <h3 class="text-soft-silk font-semibold">Storage</h3>
                <div class="flex items-center justify-between">
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        File uploads and generated images stored in your account.
                    </p>
                    <p v-if="!isLoading" class="text-stone-gray/80 mt-1 text-sm">
                        {{ storageUsed }} / {{ storageTotal }} used
                    </p>
                </div>
            </div>
            <div v-if="!isLoading" class="mt-4">
                <div class="bg-anthracite/20 h-4 w-full overflow-hidden rounded-full">
                    <div
                        class="flex h-4 overflow-hidden rounded-full transition-all duration-500 ease-out"
                        :style="{ width: `${storagePercentage}%` }"
                    >
                        <template v-if="storageBreakdown.length > 0">
                            <div
                                v-for="item in storageBreakdown"
                                :key="item.category"
                                class="h-full transition-all duration-500 ease-out"
                                :class="item.barClass"
                                :style="{ width: `${item.percentage}%` }"
                            ></div>
                        </template>
                        <div
                            v-else
                            class="h-full w-full"
                            :class="isStorageFull ? 'bg-red-500' : 'bg-ember-glow'"
                        ></div>
                    </div>
                </div>
                <p
                    class="mt-2 h-4 text-right text-sm"
                    :class="isStorageFull ? 'font-bold text-red-400' : 'text-stone-gray/80'"
                >
                    <span v-if="isStorageFull">Storage full: </span>
                    {{ storagePercentage }}% used
                </p>

                <div class="mt-6">
                    <div class="flex items-center justify-between">
                        <h4 class="text-soft-silk text-sm font-semibold">Storage breakdown</h4>
                        <p class="text-stone-gray/70 text-xs">{{ storageBreakdown.length }} categories</p>
                    </div>

                    <div v-if="storageBreakdown.length > 0" class="mt-3 grid gap-3 sm:grid-cols-2">
                        <div
                            v-for="item in storageBreakdown"
                            :key="item.category"
                            class="border-stone-gray/10 bg-anthracite/10 rounded-xl border p-3"
                        >
                            <div class="flex items-start justify-between gap-4">
                                <div class="min-w-0">
                                    <div class="flex items-center gap-2">
                                        <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="item.barClass"></span>
                                        <p class="text-soft-silk truncate text-sm font-medium">{{ item.label }}</p>
                                    </div>
                                    <p class="text-stone-gray/70 mt-0.5 text-xs">{{ item.description }}</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-soft-silk text-sm font-medium">{{ item.formattedUsed }}</p>
                                    <p class="text-stone-gray/70 text-xs">
                                        {{ item.file_count }} {{ item.file_count === 1 ? 'file' : 'files' }}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <p v-else class="text-stone-gray/70 mt-3 text-sm">No stored files yet.</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
