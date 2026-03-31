<script lang="ts" setup>
defineProps<{
    graphId: string;
    isLoading: boolean;
    errorState: {
        title: string;
        description: string;
        statusCode: number | null;
        detail: string;
    };
}>();

defineEmits<{
    (e: 'retry'): void;
    (e: 'navigate-home'): void;
    (e: 'create-canvas'): void;
}>();
</script>

<template>
    <div class="flex h-full items-center justify-center px-6">
        <div
            class="border-stone-gray/10 bg-anthracite/80 w-full max-w-xl rounded-[2rem] border p-8
                shadow-2xl backdrop-blur-md"
        >
            <div
                class="bg-ember-glow/15 text-ember-glow mb-6 flex h-14 w-14 items-center
                    justify-center rounded-2xl"
            >
                <UiIcon name="MaterialSymbolsErrorCircleRounded" class="h-8 w-8" />
            </div>

            <div class="space-y-3">
                <div class="flex flex-wrap items-center gap-3">
                    <h1 class="text-soft-silk text-2xl font-semibold">
                        {{ errorState.title }}
                    </h1>
                    <span
                        v-if="errorState.statusCode"
                        class="border-stone-gray/15 bg-obsidian/60 text-stone-gray rounded-full
                            border px-3 py-1 text-xs font-semibold tracking-[0.16em] uppercase"
                    >
                        Error {{ errorState.statusCode }}
                    </span>
                </div>

                <p class="text-stone-gray text-sm leading-6">
                    {{ errorState.description }}
                </p>

                <div
                    class="border-stone-gray/10 bg-obsidian/55 text-stone-gray rounded-2xl border
                        px-4 py-3 text-sm"
                >
                    <p class="font-medium text-soft-silk">Requested canvas</p>
                    <p class="mt-1 break-all font-mono text-xs">
                        {{ graphId }}
                    </p>
                    <p
                        v-if="errorState.detail"
                        class="mt-3 border-stone-gray/10 border-t pt-3 text-xs"
                    >
                        {{ errorState.detail }}
                    </p>
                </div>
            </div>

            <div class="mt-8 flex flex-wrap gap-3">
                <button
                    class="bg-ember-glow text-soft-silk hover:bg-ember-glow/90 rounded-xl px-4
                        py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed
                        disabled:opacity-60"
                    :disabled="isLoading"
                    @click="$emit('retry')"
                >
                    <span class="flex items-center gap-2">
                        <UiIcon name="MaterialSymbolsRefreshRounded" class="h-4 w-4" />
                        Retry
                    </span>
                </button>

                <button
                    class="border-stone-gray/15 bg-obsidian/60 text-soft-silk hover:bg-obsidian/80
                        rounded-xl border px-4 py-2.5 text-sm font-semibold transition"
                    @click="$emit('navigate-home')"
                >
                    Back to Home
                </button>

                <button
                    class="border-stone-gray/15 bg-anthracite text-stone-gray hover:text-soft-silk
                        hover:border-stone-gray/30 rounded-xl border px-4 py-2.5 text-sm
                        font-semibold transition"
                    @click="$emit('create-canvas')"
                >
                    <span class="flex items-center gap-2">
                        <UiIcon name="Fa6SolidPlus" class="h-3.5 w-3.5" />
                        New Canvas
                    </span>
                </button>
            </div>
        </div>
    </div>
</template>
