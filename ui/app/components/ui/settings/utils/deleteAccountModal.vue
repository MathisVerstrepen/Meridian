<script lang="ts" setup>
const emit = defineEmits<{
    (e: 'close' | 'confirm'): void;
}>();

const confirmationInput = ref('');

const isDeleteEnabled = computed(() => confirmationInput.value === 'DELETE');

const handleConfirm = () => {
    if (isDeleteEnabled.value) {
        emit('confirm');
    }
};
</script>

<template>
    <Teleport to="body">
        <div
            class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60
                backdrop-blur-sm"
            @click.self="emit('close')"
        >
            <div
                class="bg-obsidian border-stone-gray/20 w-full max-w-md rounded-xl border p-6
                    shadow-2xl"
            >
                <div class="mb-4 flex items-center gap-3 text-red-400">
                    <UiIcon name="UilExclamationTriangle" class="h-8 w-8" />
                    <h3 class="text-xl font-bold">Delete Account</h3>
                </div>
                <p class="text-stone-gray mb-4 text-sm leading-relaxed">
                    Are you sure you want to delete your account? This action is
                    <span class="text-soft-silk font-bold">irreversible</span> and will permanently
                    delete all your data, including graphs, files, and settings.
                </p>

                <div class="mb-6">
                    <label class="text-stone-gray/80 mb-2 block text-xs">
                        Type <span class="font-bold text-red-400">DELETE</span> to confirm
                    </label>
                    <input
                        v-model="confirmationInput"
                        type="text"
                        class="border-stone-gray/20 bg-anthracite/20 text-soft-silk w-full
                            rounded-lg border-2 p-2 text-sm transition-colors duration-200
                            outline-none focus:border-2 focus:border-red-500/50"
                        placeholder="DELETE"
                        @keydown.enter.prevent="handleConfirm"
                    />
                </div>

                <div class="flex justify-end gap-3">
                    <button
                        class="text-stone-gray hover:text-soft-silk rounded-lg px-4 py-2 text-sm
                            transition-colors"
                        @click="emit('close')"
                    >
                        Cancel
                    </button>
                    <button
                        class="rounded-lg border px-4 py-2 text-sm font-bold transition-all
                            duration-200"
                        :class="[
                            isDeleteEnabled
                                ? `cursor-pointer border-red-500/20 bg-red-500/10 text-red-400
                                    hover:bg-red-500/20`
                                : `bg-stone-gray/5 text-stone-gray/40 border-stone-gray/10
                                    cursor-not-allowed`,
                        ]"
                        :disabled="!isDeleteEnabled"
                        @click="handleConfirm"
                    >
                        Delete Account
                    </button>
                </div>
            </div>
        </div>
    </Teleport>
</template>
