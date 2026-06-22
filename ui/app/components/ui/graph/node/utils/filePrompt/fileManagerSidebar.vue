<script lang="ts" setup>
import { storeToRefs } from 'pinia';

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
</script>

<template>
    <div class="border-stone-gray/20 flex w-48 shrink-0 flex-col gap-2 border-r pr-4">
        <button
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium
                transition-colors"
            :class="
                activeTab === 'uploads'
                    ? 'bg-ember-glow/10 text-ember-glow'
                    : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
            "
            @click="emit('switchTab', 'uploads')"
        >
            <UiIcon name="MdiFolderOutline" class="h-5 w-5" />
            <span>My Files</span>
        </button>
        <button
            class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium
                transition-colors"
            :class="
                activeTab === 'generated'
                    ? 'bg-ember-glow/10 text-ember-glow'
                    : 'text-stone-gray hover:bg-stone-gray/5 hover:text-soft-silk'
            "
            @click="emit('switchTab', 'generated')"
        >
            <UiIcon name="MynauiSparklesSolid" class="h-5 w-5" />
            <span>Generated</span>
        </button>

        <div v-if="isUserUploadsTab" class="mt-2 flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
            <div v-if="pinnedFolders.length > 0" class="flex min-h-0 flex-col gap-1">
                <p class="text-stone-gray/50 px-3 text-xs font-medium">Pinned</p>
                <div
                    v-for="shortcut in pinnedFolders"
                    :key="shortcut.folder.id"
                    class="group hover:bg-stone-gray/5 flex w-full items-center gap-2 rounded-lg px-3
                        py-1.5 text-sm text-stone-gray transition-colors hover:text-soft-silk"
                    :title="shortcut.folder.path || shortcut.folder.name"
                >
                    <button
                        class="flex min-w-0 flex-1 items-center gap-2 text-left"
                        @click="emit('navigateFolder', shortcut)"
                    >
                        <UiIcon name="MdiFolderOutline" class="h-4 w-4 shrink-0" />
                        <span class="truncate">
                            {{ shortcut.folder.name === '/' ? 'Root' : shortcut.folder.name }}
                        </span>
                    </button>
                    <button
                        class="ml-auto rounded p-0.5 opacity-0 transition-opacity group-hover:opacity-100"
                        title="Unpin folder"
                        @click="emit('togglePin', shortcut)"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>

            <div v-if="recentFolders.length > 0" class="flex min-h-0 flex-col gap-1 overflow-hidden">
                <p class="text-stone-gray/50 px-3 text-xs font-medium">Recent</p>
                <button
                    v-for="shortcut in recentFolders"
                    :key="shortcut.folder.id"
                    class="hover:bg-stone-gray/5 flex w-full items-center gap-2 rounded-lg px-3
                        py-1.5 text-left text-sm text-stone-gray transition-colors hover:text-soft-silk"
                    :title="shortcut.folder.path || shortcut.folder.name"
                    @click="emit('navigateFolder', shortcut)"
                >
                    <UiIcon name="MaterialSymbolsHistory" class="h-4 w-4 shrink-0" />
                    <span class="truncate">
                        {{ shortcut.folder.name === '/' ? 'Root' : shortcut.folder.name }}
                    </span>
                </button>
            </div>
        </div>

        <div v-if="storageUsage" class="mt-auto flex flex-col gap-2 px-3 pb-2">
            <div class="flex items-center justify-between text-xs font-medium">
                <span class="text-stone-gray/80">Storage</span>
                <span
                    :class="
                        storageUsage.percentage >= 90
                            ? 'text-red-400'
                            : storageUsage.percentage >= 75
                              ? 'text-ember-glow'
                              : 'text-soft-silk'
                    "
                >
                    {{ Math.min(Math.round(storageUsage.percentage), 100) }}%
                </span>
            </div>
            <div class="bg-stone-gray/10 h-1.5 w-full overflow-hidden rounded-full">
                <div
                    class="h-full rounded-full transition-all duration-300 ease-out"
                    :class="
                        storageUsage.percentage >= 90
                            ? 'bg-red-400'
                            : storageUsage.percentage >= 75
                              ? 'bg-ember-glow'
                              : 'bg-soft-silk'
                    "
                    :style="{ width: `${Math.min(storageUsage.percentage, 100)}%` }"
                />
            </div>
        </div>
    </div>
</template>
