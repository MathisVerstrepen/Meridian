<script lang="ts" setup>
interface ImageGenState {
    prompt: string;
    isGenerating: boolean;
    imageUrl?: string;
}

defineProps<{
    activeImageGenerations: ImageGenState[];
}>();
</script>

<template>
    <div v-if="activeImageGenerations.length > 0" class="mb-4 space-y-3">
        <div
            v-for="(gen, index) in activeImageGenerations"
            :key="index"
            class="image-gen-loader border-soft-silk/10 bg-obsidian flex flex-col overflow-hidden
                rounded-xl border"
        >
            <div class="bg-obsidian relative flex h-48 items-center justify-center overflow-hidden">
                <div class="shimmer-overlay animate-shimmer absolute inset-0"></div>
                <div class="relative z-10 flex flex-col items-center gap-4">
                    <div
                        class="flex size-16 animate-pulse items-center justify-center rounded-full"
                    >
                        <UiIcon
                            name="MaterialSymbolsWbSunnyOutlineRounded"
                            class="h-8 w-8 animate-spin"
                        />
                    </div>
                    <div class="text-soft-silk/80 flex items-center gap-0.5 text-sm font-medium">
                        Generating image...
                    </div>
                </div>
            </div>
            <div class="border-soft-silk/10 border-t p-3 px-4">
                <div
                    class="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider
                        uppercase"
                >
                    <UiIcon name="IconoirFlash" class="h-4 w-4" />
                    <span>Prompt</span>
                </div>
                <p class="m-0 line-clamp-3 text-[13px] leading-normal text-white/80">
                    {{ gen.prompt }}
                </p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.shimmer-overlay {
    background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(255, 255, 255, 0.03) 20%,
        rgba(255, 255, 255, 0.06) 50%,
        rgba(255, 255, 255, 0.03) 80%,
        transparent 100%
    );
    animation: shimmer 2s infinite;
}

@keyframes shimmer {
    0% {
        transform: translateX(-100%);
    }
    100% {
        transform: translateX(100%);
    }
}
</style>
