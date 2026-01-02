<script lang="ts" setup>
import { storeToRefs } from 'pinia';

defineProps<{
    activeTab: ViewTab;
}>();

const emit = defineEmits<{
    (e: 'switchTab', tab: ViewTab): void;
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
