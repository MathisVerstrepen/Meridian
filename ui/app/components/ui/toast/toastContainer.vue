<script setup lang="ts">
const toastsStore = useToastsStore();
</script>

<template>
    <div
        aria-live="assertive"
        class="pointer-events-none fixed inset-0 right-4 bottom-4 z-50 flex flex-col-reverse items-end
            justify-start gap-3 p-4"
    >
        <TransitionGroup tag="div" class="flex w-full max-w-sm flex-col gap-3" name="toast">
            <UiToastNotification
                v-for="toast in toastsStore.toasts"
                :key="toast.id"
                :toast="toast"
                class="pointer-events-auto"
            />
        </TransitionGroup>
    </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
    transition: all 0.5s cubic-bezier(0.55, 0, 0.1, 1);
}
.toast-enter-from,
.toast-leave-to {
    opacity: 0;
    transform: scale(0.8) translateY(20px);
}

.toast-move {
    transition: transform 0.4s ease;
}
</style>
