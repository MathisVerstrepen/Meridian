<script lang="ts" setup>
defineProps<{
    modelValue: boolean;
}>();

const emit = defineEmits<{
    (e: 'close' | 'configure'): void;
}>();
</script>

<template>
    <Teleport to="body">
        <Transition
            enter-active-class="transition duration-300 ease-out"
            enter-from-class="opacity-0"
            enter-to-class="opacity-100"
            leave-active-class="transition duration-200 ease-in"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <div
                v-if="modelValue"
                class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4
                    backdrop-blur-sm"
                role="dialog"
                aria-modal="true"
            >
                <!-- Modal Card -->
                <Transition
                    enter-active-class="transition duration-400 ease-[cubic-bezier(0.16,1,0.3,1)]
                    delay-75"
                    enter-from-class="translate-y-4 scale-95 opacity-0"
                    enter-to-class="translate-y-0 scale-100 opacity-100"
                    leave-active-class="transition duration-200 ease-in"
                    leave-from-class="translate-y-0 scale-100 opacity-100"
                    leave-to-class="translate-y-4 scale-95 opacity-0"
                >
                    <div
                        v-if="modelValue"
                        class="bg-obsidian relative w-full max-w-md overflow-hidden rounded-[2rem]
                            border border-white/10 shadow-2xl ring-1 ring-white/5"
                    >
                        <!-- Background Effects -->
                        <div
                            class="bg-ember-glow/10 pointer-events-none absolute -top-24 -right-24
                                h-64 w-64 rounded-full blur-[80px]"
                        ></div>
                        <div
                            class="pointer-events-none absolute -bottom-24 -left-24 h-64 w-64
                                rounded-full bg-blue-500/5 blur-[80px]"
                        ></div>

                        <div class="relative flex flex-col items-center p-8 pt-10 text-center">
                            <!-- Hero Icon -->
                            <div class="relative mb-8">
                                <div
                                    class="bg-ember-glow/20 absolute inset-0 animate-pulse
                                        rounded-full blur-xl"
                                ></div>
                                <div
                                    class="relative flex h-20 w-20 items-center justify-center
                                        rounded-2xl border border-white/10 bg-gradient-to-br
                                        from-white/10 to-white/5
                                        shadow-[inset_0_1px_1px_rgba(255,255,255,0.1)]"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsKeyVerticalRounded"
                                        class="text-ember-glow h-10 w-10
                                            drop-shadow-[0_0_15px_rgba(235,94,40,0.6)]"
                                    />
                                </div>
                            </div>

                            <!-- Typography -->
                            <h2
                                class="font-outfit text-soft-silk mb-3 text-3xl font-bold
                                    tracking-tight"
                            >
                                Welcome to Meridian
                            </h2>
                            <p class="text-stone-gray/80 mb-8 leading-relaxed">
                                Connect your OpenRouter account to start generating content.
                            </p>

                            <!-- Alert Box -->
                            <div
                                class="border-ember-glow/20 bg-ember-glow/5 mb-8 flex w-full gap-3
                                    rounded-xl border p-4 text-left backdrop-blur-sm"
                            >
                                <div
                                    class="bg-ember-glow/10 flex h-10 w-10 shrink-0 items-center
                                        justify-center rounded-lg"
                                >
                                    <UiIcon
                                        name="UilExclamationTriangle"
                                        class="text-ember-glow h-5 w-5"
                                    />
                                </div>
                                <div>
                                    <p class="text-soft-silk text-sm font-bold">Action Required</p>
                                    <p class="text-stone-gray mt-0.5 text-xs">
                                        The application will not function without a valid API key
                                        configured in settings.
                                    </p>
                                </div>
                            </div>

                            <!-- Buttons -->
                            <div class="flex w-full flex-col gap-3">
                                <button
                                    class="bg-ember-glow shadow-ember-glow/20 hover:bg-ember-glow/90
                                        hover:shadow-ember-glow/40 group relative flex w-full
                                        items-center justify-center gap-2 overflow-hidden rounded-xl
                                        px-6 py-3.5 font-bold text-white shadow-lg transition-all
                                        duration-300 hover:scale-[1.02] active:scale-[0.98]"
                                    @click="emit('configure')"
                                >
                                    <span class="relative z-10">Configure API Key</span>
                                    <UiIcon
                                        name="MdiArrowUp"
                                        class="relative z-10 h-5 w-5 rotate-90 transition-transform
                                            duration-300 group-hover:translate-x-1"
                                    />

                                    <!-- Button Shine Effect -->
                                    <div
                                        class="absolute inset-0 z-0 -translate-x-full
                                            bg-gradient-to-r from-transparent via-white/20
                                            to-transparent
                                            group-hover:animate-[shimmer_1.5s_infinite]"
                                    ></div>
                                </button>

                                <button
                                    class="text-stone-gray hover:text-soft-silk w-full rounded-xl
                                        px-6 py-3 text-sm font-medium transition-colors duration-200
                                        hover:bg-white/5"
                                    @click="emit('close')"
                                >
                                    I'll do this later
                                </button>
                            </div>
                        </div>
                    </div>
                </Transition>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
@keyframes shimmer {
    100% {
        transform: translateX(100%);
    }
}
</style>
