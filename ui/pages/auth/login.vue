<script lang="ts" setup>
const { loggedIn } = useUserSession();
</script>

<template>
    <div
        v-if="!loggedIn"
        class="bg-obsidian flex h-screen w-screen flex-col items-center justify-center space-y-4"
    >
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
</template>

<style scoped></style>
