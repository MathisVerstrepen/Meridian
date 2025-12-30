<script lang="ts" setup>
import { z } from 'zod';

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const errorMessage = ref<string | null>(null);
const showPassword = ref<boolean>(false);

useHead({
    title: 'Meridian - Register',
});

const { fetch: fetchUserSession } = useUserSession();

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

    try {
        await $fetch('/api/auth/register', {
            method: 'POST',
            body: {
                username: username.value.trim(),
                email: email.value.trim(),
                password: password.value.trim(),
            },
        });

        // Hydrate session and redirect
        await fetchUserSession();
        await navigateTo('/');
    } catch (error: unknown) {
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
    <div
        class="bg-obsidian relative flex h-screen w-screen items-center justify-center
            overflow-hidden"
    >
        <!-- Background Image -->
        <picture>
            <source srcset="/assets/img/login_bg.webp" type="image/webp" />
            <img
                src="/assets/img/login_bg.png"
                alt="Background Image"
                class="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover
                    brightness-75"
            />
        </picture>

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
                    <div class="flex flex-col space-y-1.5">
                        <label
                            for="username"
                            class="text-stone-gray text-xs font-medium tracking-wider uppercase"
                            >Username</label
                        >
                        <input
                            id="username"
                            v-model="username"
                            type="text"
                            placeholder="Choose a username"
                            autocomplete="username"
                            autofocus
                            class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50
                                w-full rounded-xl border border-white/5 bg-[#222222] px-4 py-3
                                text-sm transition-all duration-200 focus:border-transparent
                                focus:ring-2 focus:outline-none"
                        />
                    </div>

                    <!-- Email -->
                    <div class="flex flex-col space-y-1.5">
                        <label
                            for="email"
                            class="text-stone-gray text-xs font-medium tracking-wider uppercase"
                            >Email</label
                        >
                        <input
                            id="email"
                            v-model="email"
                            type="email"
                            placeholder="Enter your email"
                            autocomplete="email"
                            class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50
                                w-full rounded-xl border border-white/5 bg-[#222222] px-4 py-3
                                text-sm transition-all duration-200 focus:border-transparent
                                focus:ring-2 focus:outline-none"
                        />
                    </div>

                    <!-- Password -->
                    <div class="flex flex-col space-y-1.5">
                        <label
                            for="password"
                            class="text-stone-gray text-xs font-medium tracking-wider uppercase"
                            >Password</label
                        >
                        <div class="relative">
                            <input
                                id="password"
                                v-model="password"
                                :type="showPassword ? 'text' : 'password'"
                                placeholder="Min 8 characters"
                                autocomplete="new-password"
                                class="text-soft-silk placeholder-stone-gray/30
                                    focus:ring-ember-glow/50 w-full rounded-xl border border-white/5
                                    bg-[#222222] px-4 py-3 text-sm transition-all duration-200
                                    focus:border-transparent focus:ring-2 focus:outline-none"
                            />
                            <button
                                type="button"
                                class="text-stone-gray hover:text-soft-silk absolute inset-y-0
                                    right-0 flex items-center pr-3 transition-colors"
                                @click="showPassword = !showPassword"
                            >
                                <UiIcon
                                    :name="
                                        showPassword
                                            ? 'MaterialSymbolsVisibilityOffOutline'
                                            : 'MaterialSymbolsVisibilityOutline'
                                    "
                                    class="h-5 w-5"
                                />
                            </button>
                        </div>
                    </div>

                    <!-- Confirm Password -->
                    <div class="flex flex-col space-y-1.5">
                        <label
                            for="confirm-password"
                            class="text-stone-gray text-xs font-medium tracking-wider uppercase"
                            >Confirm Password</label
                        >
                        <input
                            id="confirm-password"
                            v-model="confirmPassword"
                            :type="showPassword ? 'text' : 'password'"
                            placeholder="Confirm your password"
                            autocomplete="new-password"
                            class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50
                                w-full rounded-xl border border-white/5 bg-[#222222] px-4 py-3
                                text-sm transition-all duration-200 focus:border-transparent
                                focus:ring-2 focus:outline-none"
                        />
                    </div>

                    <!-- Error Message -->
                    <p
                        v-if="errorMessage"
                        class="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2
                            text-center text-sm text-red-400"
                    >
                        {{ errorMessage }}
                    </p>

                    <!-- Submit Button -->
                    <button
                        type="submit"
                        class="bg-soft-silk text-obsidian hover:bg-soft-silk/80 mt-2 flex w-full
                            items-center justify-center rounded-full py-3.5 text-sm font-bold
                            transition-all duration-200 hover:cursor-pointer focus:ring-2
                            focus:ring-white/50 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]
                            focus:outline-none"
                    >
                        Create Account
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
    </div>
</template>

<style scoped></style>
