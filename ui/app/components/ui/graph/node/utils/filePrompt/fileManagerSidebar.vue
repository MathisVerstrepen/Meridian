<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import type { StorageUsageBreakdownItem } from '@/types/user';

defineProps<{
    activeTab: ViewTab;
    isUserUploadsTab: boolean;
    pinnedFolders: FileManagerFolderShortcut[];
    recentFolders: FileManagerFolderShortcut[];
}>();

const emit = defineEmits<{
    (e: 'switchTab', tab: ViewTab): void;
    (e: 'navigateFolder', shortcut: FileManagerFolderShortcut): void;
    (e: 'togglePin', shortcut: FileManagerFolderShortcut): void;
}>();

const usageStore = useUsageStore();
const { storageUsage } = storeToRefs(usageStore);
const { formatFileSize } = useFormatters();

type StorageBreakdownMeta = {
    label: string;
    description: string;
    barClass: string;
};

const STORAGE_BREAKDOWN_META: Record<string, StorageBreakdownMeta> = {
    external_cache: {
        label: 'Google Drive cache',
        description: 'Temporary external files downloaded for previews and requests.',
        barClass: 'bg-blue-400',
    },
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
const isStorageNearFull = computed(() => storagePercentage.value >= 85 && !isStorageFull.value);
const storageBreakdown = computed(() => {
    const totalUsed = storageUsage.value.used_bytes;

    return storageUsage.value.breakdown
        .map((item: StorageUsageBreakdownItem) => {
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
</script>

<template>
    <div class="border-stone-gray/15 flex w-52 shrink-0 flex-col gap-3 border-r pr-4">
        <!-- Tab buttons -->
        <div class="flex flex-col gap-1">
            <button
                class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium
                    transition-all duration-200"
                :class="
                    activeTab === 'uploads'
                        ? 'bg-ember-glow/10 text-ember-glow ring-ember-glow/20 ring-1'
                        : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
                "
                @click="emit('switchTab', 'uploads')"
            >
                <UiIcon name="MdiFolderOutline" class="h-5 w-5 shrink-0" />
                <span>My Files</span>
            </button>
            <button
                class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium
                    transition-all duration-200"
                :class="
                    activeTab === 'generated'
                        ? 'bg-ember-glow/10 text-ember-glow ring-ember-glow/20 ring-1'
                        : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
                "
                @click="emit('switchTab', 'generated')"
            >
                <UiIcon name="MynauiSparklesSolid" class="h-5 w-5 shrink-0" />
                <span>Generated</span>
            </button>
            <button
                class="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium
                    transition-all duration-200"
                :class="
                    activeTab === 'google_drive'
                        ? 'bg-ember-glow/10 text-ember-glow ring-ember-glow/20 ring-1'
                        : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
                "
                @click="emit('switchTab', 'google_drive')"
            >
                <UiIcon name="CiGoogle" class="h-5 w-5 shrink-0" />
                <span>Google Drive</span>
            </button>
        </div>

        <div v-if="isUserUploadsTab" class="mt-1 flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
            <!-- Pinned folders -->
            <div v-if="pinnedFolders.length > 0" class="flex min-h-0 flex-col gap-1">
                <div class="flex items-center gap-1.5 px-3 mb-1">
                    <UiIcon name="MajesticonsPin" class="text-stone-gray/40 h-3 w-3" />
                    <p class="text-stone-gray/50 text-[11px] font-semibold uppercase tracking-wider">Pinned</p>
                </div>
                <div
                    v-for="shortcut in pinnedFolders"
                    :key="shortcut.folder.id"
                    class="group hover:bg-stone-gray/8 flex w-full items-center gap-2 rounded-lg px-3
                        py-1.5 text-sm text-stone-gray transition-all duration-200 hover:text-soft-silk"
                    :title="shortcut.folder.path || shortcut.folder.name"
                >
                    <button
                        class="flex min-w-0 flex-1 items-center gap-2 text-left"
                        @click="emit('navigateFolder', shortcut)"
                    >
                        <UiIcon name="MdiFolderOutline" class="h-4 w-4 shrink-0 text-stone-gray/70" />
                        <span class="truncate">
                            {{ shortcut.folder.name === '/' ? 'Root' : shortcut.folder.name }}
                        </span>
                    </button>
                    <button
                        class="text-stone-gray/40 hover:text-red-400 ml-auto rounded p-1 opacity-0
                            transition-all group-hover:opacity-100 flex items-center justify-center"
                        title="Unpin folder"
                        @click="emit('togglePin', shortcut)"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>

            <!-- Recent folders -->
            <div v-if="recentFolders.length > 0" class="flex min-h-0 flex-col gap-1 overflow-hidden">
                <div class="flex items-center gap-1.5 px-3 mb-1">
                    <UiIcon name="MaterialSymbolsHistory" class="text-stone-gray/40 h-3 w-3" />
                    <p class="text-stone-gray/50 text-[11px] font-semibold uppercase tracking-wider">Recent</p>
                </div>
                <button
                    v-for="shortcut in recentFolders"
                    :key="shortcut.folder.id"
                    class="hover:bg-stone-gray/8 flex w-full items-center gap-2 rounded-lg px-3 py-1.5
                        text-left text-sm text-stone-gray transition-all duration-200 hover:text-soft-silk"
                    :title="shortcut.folder.path || shortcut.folder.name"
                    @click="emit('navigateFolder', shortcut)"
                >
                    <UiIcon name="MaterialSymbolsHistory" class="h-4 w-4 shrink-0 text-stone-gray/50" />
                    <span class="truncate">
                        {{ shortcut.folder.name === '/' ? 'Root' : shortcut.folder.name }}
                    </span>
                </button>
            </div>
        </div>

        <!-- Storage indicator -->
        <div v-if="storageUsage" class="group relative mt-auto flex flex-col gap-2 px-3 pb-2">
            <div class="flex items-center justify-between text-xs font-medium">
                <span class="text-stone-gray/80">Storage</span>
                <span
                    :class="
                        isStorageFull
                            ? 'text-red-400'
                            : isStorageNearFull
                              ? 'text-golden-ochre'
                              : 'text-soft-silk'
                    "
                >
                    {{ storagePercentage }}%
                </span>
            </div>
            <div class="bg-stone-gray/10 h-2 w-full overflow-hidden rounded-full">
                <div
                    class="flex h-full overflow-hidden rounded-full transition-all duration-300 ease-out"
                    :style="{ width: `${storagePercentage}%` }"
                >
                    <template v-if="storageBreakdown.length > 0">
                        <div
                            v-for="item in storageBreakdown"
                            :key="item.category"
                            class="h-full transition-all duration-300 ease-out"
                            :class="item.barClass"
                            :style="{ width: `${item.percentage}%` }"
                        />
                    </template>
                    <div
                        v-else
                        class="h-full w-full transition-colors"
                        :class="isStorageFull ? 'bg-red-500' : isStorageNearFull ? 'bg-golden-ochre' : 'bg-ember-glow'"
                    />
                </div>
            </div>

            <!-- Breakdown tooltip -->
            <div
                class="pointer-events-none invisible absolute bottom-0 left-full z-50 ml-3 w-72
                    translate-x-1 rounded-xl border border-stone-gray/20 bg-obsidian p-4 opacity-0
                    shadow-2xl shadow-black/30 transition-all duration-150 ease-out group-hover:visible
                    group-hover:pointer-events-auto group-hover:translate-x-0 group-hover:opacity-100"
            >
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <p class="text-soft-silk text-sm font-semibold">Storage breakdown</p>
                        <p class="text-stone-gray/70 mt-0.5 text-xs">{{ storageUsed }} / {{ storageTotal }} used</p>
                    </div>
                    <p
                        class="text-sm font-semibold"
                        :class="isStorageFull ? 'text-red-400' : 'text-soft-silk'"
                    >
                        {{ storagePercentage }}%
                    </p>
                </div>

                <div class="mt-3 flex flex-col gap-2.5">
                    <div
                        v-for="item in storageBreakdown"
                        :key="item.category"
                        class="flex items-start justify-between gap-3"
                    >
                        <div class="min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="item.barClass" />
                                <p class="text-soft-silk truncate text-xs font-medium">{{ item.label }}</p>
                            </div>
                            <p class="text-stone-gray/60 mt-0.5 line-clamp-2 text-[11px]">
                                {{ item.description }}
                            </p>
                        </div>
                        <div class="shrink-0 text-right">
                            <p class="text-soft-silk text-xs font-medium">{{ item.formattedUsed }}</p>
                            <p class="text-stone-gray/60 text-[11px]">
                                {{ item.file_count }} {{ item.file_count === 1 ? 'file' : 'files' }}
                            </p>
                        </div>
                    </div>

                    <p v-if="storageBreakdown.length === 0" class="text-stone-gray/70 text-xs">
                        No stored files yet.
                    </p>
                </div>
            </div>
        </div>
    </div>
</template>
