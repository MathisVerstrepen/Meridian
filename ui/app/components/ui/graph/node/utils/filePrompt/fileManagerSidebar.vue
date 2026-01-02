<script lang="ts" setup>
defineProps<{
    activeTab: ViewTab;
}>();

const emit = defineEmits<{
    (e: 'switchTab', tab: ViewTab): void;
}>();
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
    </div>
</template>
