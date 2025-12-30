<script lang="ts" setup>
const isOauthDisabled = ref<boolean>(useRuntimeConfig().public.isOauthDisabled);
const username = ref('');
const password = ref('');
const errorMessage = ref<string | null>(null);
const rememberMe = ref<boolean>(false);
const showPassword = ref<boolean>(false);

useHead({
    title: 'Meridian - Login',
});

const { fetch: fetchUserSession } = useUserSession();

const loginWithPassword = async () => {
    errorMessage.value = null;
    try {
        await $fetch('/api/auth/login', {
            method: 'POST',
            body: {
                username: username.value.trim(),
                password: password.value.trim(),
                rememberMe: rememberMe.value,
            },
        });

        await fetchUserSession();
        await navigateTo('/');
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { message?: string } };
        console.error('Error logging in:', err.response?.status);
        if (err.response?.status === 429) {
            errorMessage.value = 'Too many login attempts. Please try again later.';
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
                <div class="mb-10">
                    <div class="mb-6 flex items-center space-x-2">
                        <UiIcon name="logo" class="text-ember-glow h-8 w-8" />
                        <span class="font-outfit text-soft-silk text-2xl font-bold tracking-tight"
                            >Meridian</span
                        >
                    </div>
                    <h1 class="text-soft-silk text-3xl font-bold">Welcome back</h1>
                    <p class="text-stone-gray mt-2 text-sm">
                        Please enter your details to sign in.
                    </p>
                </div>

                <!-- Form -->
                <form class="flex flex-col space-y-5" @submit.prevent="loginWithPassword">
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
                            placeholder="Enter your username"
                            autocomplete="username"
                            autofocus
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
                                placeholder="••••••••"
                                autocomplete="current-password"
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

                    <!-- Actions -->
                    <div class="flex items-center justify-between">
                        <UiSettingsUtilsCheckbox
                            label="Remember for 30 days"
                            :model-value="rememberMe"
                            :style="'dark'"
                            @update:model-value="(val: boolean) => (rememberMe = val)"
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
                        Sign in
                    </button>
                </form>

                <!-- Divider -->
                <div class="relative my-8 flex items-center">
                    <div class="w-full border-t border-white/10"></div>
                    <div class="relative flex shrink-0 justify-center text-xs uppercase">
                        <span class="text-stone-gray/50 px-2">Or continue with</span>
                    </div>
                    <div class="w-full border-t border-white/10"></div>
                </div>

                <!-- Social Login -->
                <div class="grid grid-cols-2 gap-3">
                    <component
                        :is="isOauthDisabled ? 'div' : 'a'"
                        :href="isOauthDisabled ? undefined : '/api/auth/github'"
                        class="bg-anthracite/50 hover:bg-anthracite text-soft-silk flex items-center
                            justify-center gap-2 rounded-xl border border-white/5 py-2.5 text-sm
                            font-medium transition-colors duration-200"
                        :class="
                            isOauthDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                        "
                    >
                        <UiIcon name="MdiGithub" class="h-5 w-5" />
                        <span>GitHub</span>
                    </component>

                    <component
                        :is="isOauthDisabled ? 'div' : 'a'"
                        :href="isOauthDisabled ? undefined : '/api/auth/google'"
                        class="bg-anthracite/50 hover:bg-anthracite text-soft-silk flex items-center
                            justify-center gap-2 rounded-xl border border-white/5 py-2.5 text-sm
                            font-medium transition-colors duration-200"
                        :class="
                            isOauthDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                        "
                    >
                        <UiIcon name="CiGoogle" class="h-5 w-5" />
                        <span>Google</span>
                    </component>
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
