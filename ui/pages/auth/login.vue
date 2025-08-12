<script lang="ts" setup>
const isOAuthDisabled = ref<boolean>(useRuntimeConfig().public.isOAuthDisabled);
const username = ref('');
const password = ref('');
const errorMessage = ref<string | null>(null);
const rememberMe = ref<boolean>(false);

const { fetch: fetchUserSession } = useUserSession();

const loginWithPassword = async () => {
    errorMessage.value = null;
    try {
        const response = await $fetch('/api/auth/login', {
            method: 'POST',
            body: {
                username: username.value,
                password: password.value,
                rememberMe: rememberMe.value,
            },
        });

        if (response && response.token) {
            localStorage.setItem('access_token', response.token);

            await fetchUserSession();
            await navigateTo('/');
        } else {
            throw new Error('Login response did not include a token.');
        }
    } catch (error: any) {
        errorMessage.value = error.data?.message || 'An unexpected error occurred.';
    }
};
</script>

<template>
    <div class="relative flex h-screen w-screen flex-col items-center justify-center">
        <!-- Background dots -->
        <svg class="absolute top-0 left-0 z-0 h-full w-full">
            <pattern id="home-pattern" patternUnits="userSpaceOnUse" width="25" height="25">
                <circle cx="12.5" cy="12.5" r="1" fill="var(--color-stone-gray)" />
            </pattern>

            <rect width="100%" height="100%" :fill="`url(#home-pattern)`" />
        </svg>

        <!-- Background gradient over dots -->
        <div
            class="from-anthracite/100 to-anthracite/0 absolute top-0 left-0 z-10 h-full w-full"
            style="
                background: radial-gradient(
                    ellipse 100% 100% at 50% 50%,
                    var(--color-anthracite) 0%,
                    transparent 100%
                );
            "
        ></div>

        <!-- Main content -->
        <h1 class="relative z-20 flex flex-col items-center justify-center space-y-2 text-center">
            <span class="text-stone-gray/50 text-xl font-bold">Welcome to</span>
            <UiSidebarHistoryLogo />
        </h1>

        <div
            class="bg-obsidian/50 z-10 flex flex-col space-y-4 rounded-xl p-8 shadow-lg backdrop-blur-md"
        >
            <h2 class="mb-12 text-center">
                <span class="text-stone-gray/80 font-bold">Please login to continue</span>
            </h2>

            <component
                :is="isOAuthDisabled ? 'div' : 'a'"
                :href="isOAuthDisabled ? undefined : '/api/auth/github'"
                class="bg-obsidian/50 hover:bg-obsidian/70 text-stone-gray border-stone-gray/20 flex h-10 items-center
                    justify-center rounded-lg border-2 px-4 py-2 transition-colors duration-200 ease-in-out
                    focus:outline-none"
                :class="isOAuthDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
            >
                <UiIcon name="MdiGithub" class="mr-2 h-5 w-5" />
                Login with GitHub
            </component>

            <component
                :is="isOAuthDisabled ? 'div' : 'a'"
                :href="isOAuthDisabled ? undefined : '/api/auth/google'"
                class="bg-obsidian/50 hover:bg-obsidian/70 text-stone-gray border-stone-gray/20 flex h-10 items-center
                    justify-center rounded-lg border-2 px-4 py-2 transition-colors duration-200 ease-in-out
                    focus:outline-none"
                :class="isOAuthDisabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'"
            >
                <UiIcon name="CiGoogle" class="mr-2 h-5 w-5" />
                Login with Google
            </component>

            <span class="text-stone-gray/50 py-4 text-center text-sm font-bold">OR</span>

            <form class="flex flex-col space-y-4" @submit.prevent="loginWithPassword">
                <input
                    type="text"
                    v-model="username"
                    placeholder="Username"
                    autocomplete="username"
                    class="bg-obsidian/50 text-stone-gray border-stone-gray/20 focus:border-ember-glow h-10 rounded-lg border-2
                        px-4 transition-colors duration-200 focus:outline-none"
                />
                <input
                    type="password"
                    v-model="password"
                    placeholder="Password"
                    autocomplete="current-password"
                    class="bg-obsidian/50 text-stone-gray border-stone-gray/20 focus:border-ember-glow h-10 rounded-lg border-2
                        px-4 transition-colors duration-200 focus:outline-none"
                />

                <UiSettingsUtilsCheckbox
                    label="Remember me"
                    :state="rememberMe"
                    :setState="(value) => (rememberMe = value)"
                    :style="'dark'"
                />

                <!-- NEW: Error Message Display -->
                <p v-if="errorMessage" class="text-center text-sm text-red-400">
                    {{ errorMessage }}
                </p>

                <button
                    type="submit"
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 dark:text-soft-silk text-obsidian flex h-10 cursor-pointer
                        items-center justify-center rounded-lg px-4 py-2 text-sm font-bold transition-colors duration-200
                        ease-in-out focus:outline-none"
                >
                    <UiIcon name="MaterialSymbolsLoginRounded" class="mr-2 h-5 w-5" />
                    <span>Login</span>
                </button>
            </form>
        </div>
    </div>
</template>

<style scoped></style>
