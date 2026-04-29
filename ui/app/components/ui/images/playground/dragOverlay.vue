<template>
    <Transition name="dragveil">
        <div
            v-if="visible"
            class="border-ember-glow/70 bg-ember-glow/8 pointer-events-none absolute inset-3
                z-40 flex items-center justify-center rounded-3xl border-2 border-dashed
                backdrop-blur-sm"
        >
            <div class="text-center">
                <UiIcon name="MdiCloudUploadOutline" class="text-ember-glow mx-auto h-14 w-14" />
                <p class="font-outfit text-soft-silk mt-3 text-2xl font-bold">
                    Drop to load references
                </p>
                <p class="text-stone-gray mt-1 text-xs tracking-[0.3em] uppercase">
                    Drag · Paste · Upload
                </p>
            </div>
        </div>
    </Transition>
</template>

<script lang="ts" setup>
defineProps<{
    visible: boolean;
}>();
</script>
