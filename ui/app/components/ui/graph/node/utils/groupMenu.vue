<script lang="ts" setup>
defineProps<{
    position: { x: number; y: number };
}>();

const emit = defineEmits(['create-group']);
</script>

<template>
    <div
        class="absolute z-50 flex items-center justify-center px-14 py-10"
        :style="{ left: `${position.x - 56}px`, top: `${position.y - 40}px` }"
        @contextmenu.prevent
    >
        <button
            class="hover:bg-soft-black bg-soft-silk/10 text-soft-silk/80 border-stone-gray/10 hover:bg-soft-silk/20
                hover:text-soft-silk flex h-10 w-36 cursor-pointer items-center justify-center gap-2 rounded-md
                border px-3 py-1 text-left text-sm shadow-lg backdrop-blur-lg transition-colors duration-200"
            @click="emit('create-group')"
        >
            <UiIcon class="h-4 w-4" name="MaterialSymbolsLightStackGroupRounded" />
            Create Group
        </button>
    </div>
</template>
