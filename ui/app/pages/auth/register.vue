<script lang="ts" setup>
import { z } from 'zod';

definePageMeta({
    layout: 'auth',
});

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const errorMessage = ref<string | null>(null);
const isLoading = ref<boolean>(false);

useHead({
    title: 'Meridian - Register',
});

// Validation Schema
const registerSchema = z
    .object({
        username: z
            .string()
            .min(3, 'Username must be at least 3 characters')
            .max(50, 'Username must be less than 50 characters')
            .regex(
                /^[a-zA-Z0-9_-]+$/,
                'Username can only contain alphanumeric characters, underscores, or dashes',
            ),
        email: z.string().email('Invalid email address'),
        password: z.string().min(8, 'Password must be at least 8 characters'),
        confirmPassword: z.string(),
    })
    .refine((data) => data.password === data.confirmPassword, {
        message: "Passwords don't match",
        path: ['confirmPassword'],
    });

const register = async () => {
    errorMessage.value = null;

    // Client-side validation
    const validationResult = registerSchema.safeParse({
        username: username.value,
        email: email.value,
        password: password.value,
        confirmPassword: confirmPassword.value,
    });

    if (!validationResult.success) {
        errorMessage.value = validationResult.error.errors[0].message;
        return;
    }

    isLoading.value = true;

    try {
        await $fetch('/api/auth/register', {
            method: 'POST',
            body: {
                username: username.value.trim(),
                email: email.value.trim(),
                password: password.value.trim(),
            },
        });

        // Redirect to verification page
        await navigateTo(`/auth/verify?email=${encodeURIComponent(email.value.trim())}`);
    } catch (error: unknown) {
        isLoading.value = false;
        const err = error as { response?: { status?: number }; data?: { message?: string } };
        console.error('Error registering:', err.response?.status);
        if (err.response?.status === 429) {
            errorMessage.value = 'Too many attempts. Please try again later.';
        } else {
            errorMessage.value = err.data?.message || 'An unexpected error occurred.';
        }
    }
};
</script>

<template>
    <!-- Main Card Container -->
    <div
        class="z-10 flex h-full w-full max-w-[1200px] overflow-hidden shadow-2xl ring-1
            ring-white/10 md:h-[800px] md:rounded-[32px]"
    >
        <!-- Left Column: Interaction -->
        <div
            class="relative z-20 flex w-full flex-col justify-center bg-[#1A1A1A]/70 p-8
                backdrop-blur-2xl md:w-[45%] md:p-12 lg:p-16"
        >
            <!-- Logo & Header -->
            <div class="mb-8">
                <div class="mb-6 flex items-center space-x-2">
                    <UiIcon name="logo" class="text-ember-glow h-8 w-8" />
                    <span class="font-outfit text-soft-silk text-2xl font-bold tracking-tight"
                        >Meridian</span
                    >
                </div>
                <h1 class="text-soft-silk text-3xl font-bold">Create Account</h1>
                <p class="text-stone-gray mt-2 text-sm">Enter your details to get started.</p>
            </div>

            <!-- Form -->
            <form class="flex flex-col space-y-4" @submit.prevent="register">
                <!-- Username -->
                <UiAuthInput
                    id="username"
                    v-model="username"
                    label="Username"
                    placeholder="Choose a username"
                    autocomplete="username"
                    autofocus
                    :disabled="isLoading"
                />

                <!-- Email -->
                <UiAuthInput
                    id="email"
                    v-model="email"
                    label="Email"
                    type="email"
                    placeholder="Enter your email"
                    autocomplete="email"
                    :disabled="isLoading"
                />

                <!-- Password -->
                <UiAuthPasswordInput
                    id="password"
                    v-model="password"
                    label="Password"
                    placeholder="Min 8 characters"
                    autocomplete="new-password"
                    :disabled="isLoading"
                />

                <!-- Confirm Password -->
                <UiAuthPasswordInput
                    id="confirm-password"
                    v-model="confirmPassword"
                    label="Confirm Password"
                    placeholder="Confirm your password"
                    autocomplete="new-password"
                    :disabled="isLoading"
                />

                <!-- Error Message -->
                <p
                    v-if="errorMessage"
                    class="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-center
                        text-sm text-red-400"
                >
                    {{ errorMessage }}
                </p>

                <!-- Submit Button -->
                <button
                    type="submit"
                    :disabled="isLoading"
                    class="bg-soft-silk text-obsidian hover:bg-soft-silk/80 mt-2 flex w-full
                        items-center justify-center rounded-full py-3.5 text-sm font-bold
                        transition-all duration-200 hover:cursor-pointer focus:ring-2
                        focus:ring-white/50 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]
                        focus:outline-none disabled:cursor-not-allowed disabled:opacity-70"
                >
                    <template v-if="isLoading">
                        <UiIcon
                            name="MingcuteLoading3Fill"
                            class="text-obsidian mr-2 h-4 w-4 animate-spin"
                        />
                        Creating Account...
                    </template>
                    <span v-else>Create Account</span>
                </button>
            </form>

            <!-- Login Link -->
            <div class="mt-6 text-center text-sm">
                <span class="text-stone-gray">Already have an account? </span>
                <NuxtLink
                    to="/auth/login"
                    class="text-soft-silk hover:text-ember-glow font-medium transition-colors"
                >
                    Sign in
                </NuxtLink>
            </div>

            <!-- Footer -->
            <div class="text-stone-gray/30 mt-auto pt-6 text-center text-xs">
                Version {{ $nuxt.$config.public.version }}
            </div>
        </div>

        <!-- Right Column -->
        <div
            class="relative hidden w-[55%] flex-col items-center justify-center overflow-hidden
                md:flex"
        >
            <div class="absolute inset-0 bg-white/5 blur-2xl"></div>
        </div>
    </div>
</template>

<style scoped></style>
