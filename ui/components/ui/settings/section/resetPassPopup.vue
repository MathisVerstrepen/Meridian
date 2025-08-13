<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits(['closeFullscreen']);

const { apiFetch } = useAPI();

const oldPassword = ref('');
const newPassword = ref('');
const confirmPassword = ref('');

const showOldPassword = ref(false);
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);

const errorMessage = ref('');
const successMessage = ref('');
const isLoading = ref(false);

watch([newPassword, confirmPassword], () => {
    if (newPassword.value === confirmPassword.value) {
        errorMessage.value = '';
    }
});

const passwordsMatch = computed(() => {
    if (newPassword.value === '' && confirmPassword.value === '') {
        return true;
    }
    return newPassword.value === confirmPassword.value;
});

const isFormValid = computed(() => {
    return oldPassword.value.length > 0 && newPassword.value.length >= 8 && passwordsMatch.value;
});

const handleSubmit = async () => {
    if (!isFormValid.value) {
        if (newPassword.value.length > 0 && !passwordsMatch.value) {
            errorMessage.value = 'The new passwords do not match.';
        } else if (newPassword.value.length > 0 && newPassword.value.length < 8) {
            errorMessage.value = 'New password must be at least 8 characters long.';
        } else {
            errorMessage.value = 'Please fill out all fields correctly.';
        }
        return;
    }
    errorMessage.value = '';
    successMessage.value = '';

    try {
        isLoading.value = true;
        await apiFetch(
            '/api/auth/reset-password',
            {
                method: 'POST',
                body: {
                    oldPassword: oldPassword.value,
                    newPassword: newPassword.value,
                },
            },
            true,
        );
        isLoading.value = false;

        successMessage.value = 'Password updated successfully!';
    } catch (error: any) {
        isLoading.value = false;
        console.error('Error resetting password:', error);

        if (error.statusCode === 401) {
            errorMessage.value = 'Incorrect old password. Please try again.';
        } else {
            errorMessage.value = error.data?.message || 'An unexpected error occurred.';
        }
    }
};
</script>

<template>
    <span class="absolute top-0 right-0 bottom-0 left-0 z-50 bg-black/0 backdrop-blur"></span>

    <AnimatePresence>
        <motion.div
            id="reset-pass-popup"
            key="reset-pass-popup"
            :initial="{ opacity: 0, scale: 0.85 }"
            :animate="{ opacity: 1, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, scale: 0.85, transition: { duration: 0.15, ease: 'easeIn' } }"
            class="bg-obsidian/90 border-stone-gray/10 absolute top-1/2 left-1/2 z-50 mx-auto flex h-[500px] w-[400px]
                -translate-x-1/2 -translate-y-1/2 cursor-grab flex-col items-center justify-between overflow-hidden
                rounded-2xl border-2 px-12 py-8 shadow-lg backdrop-blur-md"
        >
            <button
                class="hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-4 right-4 z-50 flex h-10 w-10 items-center
                    justify-center justify-self-end rounded-full backdrop-blur-sm transition-colors duration-200
                    ease-in-out hover:cursor-pointer"
                @click="emit('closeFullscreen')"
                aria-label="Close Fullscreen"
                title="Close Fullscreen"
            >
                <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
            </button>

            <h2 class="text-soft-silk mb-6 text-2xl font-bold">Change Password</h2>

            <form @submit.prevent="handleSubmit" class="flex w-full grow flex-col">
                <!-- Old Password -->
                <div class="mb-4">
                    <label for="old-password" class="text-stone-gray mb-1 block text-sm font-medium"
                        >Old Password</label
                    >
                    <div class="relative">
                        <input
                            id="old-password"
                            v-model="oldPassword"
                            :type="showOldPassword ? 'text' : 'password'"
                            placeholder="Enter your current password"
                            autocomplete="current-password"
                            class="bg-obsidian/50 text-stone-gray border-stone-gray/20 focus:border-ember-glow block h-11 w-full
                                rounded-lg border-2 py-2 pr-10 pl-4 transition-colors duration-200 focus:outline-none"
                        />
                        <button
                            type="button"
                            @click="showOldPassword = !showOldPassword"
                            class="hover:bg-stone-gray/20 text-stone-gray absolute inset-y-0 right-0 flex items-center rounded-r-lg
                                px-3 transition-colors duration-200 ease-in-out focus:outline-none"
                            aria-label="Toggle old password visibility"
                        >
                            <UiIcon
                                :name="
                                    showOldPassword
                                        ? 'MaterialSymbolsVisibilityOffOutline'
                                        : 'MaterialSymbolsVisibilityOutline'
                                "
                                class="h-5 w-5"
                            />
                        </button>
                    </div>
                </div>

                <!-- New Password -->
                <div class="mb-4">
                    <label for="new-password" class="text-stone-gray mb-1 block text-sm font-medium"
                        >New Password</label
                    >
                    <div class="relative">
                        <input
                            id="new-password"
                            v-model="newPassword"
                            :type="showNewPassword ? 'text' : 'password'"
                            placeholder="Minimum 8 characters"
                            autocomplete="new-password"
                            class="bg-obsidian/50 text-stone-gray border-stone-gray/20 focus:border-ember-glow block h-11 w-full
                                rounded-lg border-2 py-2 pr-10 pl-4 transition-colors duration-200 focus:outline-none"
                        />
                        <button
                            type="button"
                            @click="showNewPassword = !showNewPassword"
                            class="hover:bg-stone-gray/20 text-stone-gray absolute inset-y-0 right-0 flex items-center rounded-r-lg
                                px-3 transition-colors duration-200 ease-in-out focus:outline-none"
                            aria-label="Toggle new password visibility"
                        >
                            <UiIcon
                                :name="
                                    showNewPassword
                                        ? 'MaterialSymbolsVisibilityOffOutline'
                                        : 'MaterialSymbolsVisibilityOutline'
                                "
                                class="h-5 w-5"
                            />
                        </button>
                    </div>
                </div>

                <!-- Confirm New Password -->
                <div class="mb-2">
                    <label
                        for="confirm-password"
                        class="text-stone-gray mb-1 block text-sm font-medium"
                        >Confirm New Password</label
                    >
                    <div class="relative">
                        <input
                            id="confirm-password"
                            v-model="confirmPassword"
                            :type="showConfirmPassword ? 'text' : 'password'"
                            placeholder="Repeat new password"
                            autocomplete="new-password"
                            class="bg-obsidian/50 text-stone-gray border-stone-gray/20 focus:border-ember-glow block h-11 w-full
                                rounded-lg border-2 py-2 pr-10 pl-4 transition-colors duration-200 focus:outline-none"
                            :class="{
                                'border-merlot-wine focus:border-merlot-wine':
                                    !passwordsMatch && confirmPassword.length > 0,
                            }"
                        />
                        <button
                            type="button"
                            @click="showConfirmPassword = !showConfirmPassword"
                            class="hover:bg-stone-gray/20 text-stone-gray absolute inset-y-0 right-0 flex items-center rounded-r-lg
                                px-3 transition-colors duration-200 ease-in-out focus:outline-none"
                            aria-label="Toggle confirm password visibility"
                        >
                            <UiIcon
                                :name="
                                    showConfirmPassword
                                        ? 'MaterialSymbolsVisibilityOffOutline'
                                        : 'MaterialSymbolsVisibilityOutline'
                                "
                                class="h-5 w-5"
                            />
                        </button>
                    </div>
                    <p
                        v-if="!passwordsMatch && confirmPassword.length > 0"
                        class="text-merlot-wine mt-1 h-4 text-xs"
                    >
                        Passwords do not match.
                    </p>
                    <p v-else class="mt-1 h-4 text-xs"></p>
                </div>

                <p
                    v-if="errorMessage"
                    class="text-merlot-wine -mb-1 text-center text-sm font-medium"
                >
                    {{ errorMessage }}
                </p>

                <p
                    v-if="successMessage"
                    class="text-olive-grove -mb-1 text-center text-sm font-medium"
                >
                    {{ successMessage }}
                </p>

                <div class="mt-auto pt-4">
                    <button
                        type="submit"
                        :disabled="!isFormValid || isLoading"
                        class="bg-ember-glow hover:bg-ember-glow/75 text-soft-silk focus:ring-offset-obsidian
                            disabled:bg-anthracite disabled:text-stone-gray/60 flex h-10 w-full cursor-pointer items-center
                            justify-center rounded-lg px-4 py-2 text-sm font-bold transition-all duration-200 ease-in-out
                            focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed"
                        :class="{ 'animate-pulse': isLoading }"
                    >
                        <span>{{ isLoading ? 'Updating...' : 'Update Password' }}</span>
                    </button>
                </div>
            </form>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
