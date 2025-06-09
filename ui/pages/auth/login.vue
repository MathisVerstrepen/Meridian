<script lang="ts" setup>
const { loggedIn } = useUserSession();
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
            <span class="text-stone-gray font-outfit mb-8 w-full text-center text-4xl font-bold">
                Meridian <span class="text-terracotta-clay">AI</span>
            </span>
        </h1>

        <div
            class="bg-obsidian/50 z-10 flex flex-col space-y-4 rounded-lg p-8 shadow-lg backdrop-blur-md"
        >
            <h2 class="mb-12 text-center">
                <span class="text-stone-gray/80 font-bold">Please login to continue</span>
            </h2>

            <a
                v-if="!loggedIn"
                href="/api/auth/github"
                class="bg-obsidian/50 hover:bg-obsidian/70 text-stone-gray border-stone-gray/20 flex h-10 items-center
                    justify-center rounded-lg border-2 px-4 py-2 transition-colors duration-200 ease-in-out
                    focus:outline-none"
            >
                <UiIcon name="MdiGithub" class="mr-2 h-5 w-5" />
                Login with GitHub
            </a>

            <a
                v-if="!loggedIn"
                href="/api/auth/google"
                class="bg-obsidian/50 hover:bg-obsidian/70 text-stone-gray border-stone-gray/20 flex h-10 items-center
                    justify-center rounded-lg border-2 px-4 py-2 transition-colors duration-200 ease-in-out
                    focus:outline-none"
            >
                <UiIcon name="CiGoogle" class="mr-2 h-5 w-5" />
                Login with Google
            </a>
        </div>
    </div>
</template>

<style scoped></style>
