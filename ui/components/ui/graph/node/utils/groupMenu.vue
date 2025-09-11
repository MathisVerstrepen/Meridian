<script lang="ts" setup>
defineProps<{
    position: { x: number; y: number };
}>();

const emit = defineEmits(['create-group']);
</script>

<template>
    <div
        class="bg-soft-silk/10 text-soft-silk/80 border-stone-gray/10 hover:bg-soft-silk/20 hover:text-soft-silk
            absolute z-50 cursor-pointer rounded-md border p-1 shadow-lg backdrop-blur-lg transition-colors
            duration-200"
        :style="{ left: `${position.x}px`, top: `${position.y}px` }"
    >
        <button
            class="hover:bg-soft-black flex w-full items-center gap-2 rounded px-3 py-1 text-left text-sm
                transition-colors"
            @click="emit('create-group')"
        >
            <UiIcon class="h-4 w-4" name="MaterialSymbolsLightStackGroupRounded" />
            Create Group
        </button>
    </div>
</template>
