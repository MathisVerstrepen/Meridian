<script lang="ts" setup>
const { loggedIn } = useUserSession();
</script>

<template>
    <div v-if="!loggedIn" class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <a
            v-if="!loggedIn"
            href="/api/auth/github"
            class="bg-obsidian/50 hover:bg-obsidian/70 text-stone-gray flex h-10 items-center justify-center
                rounded-lg border-2 border-stone-gray/20 px-4 py-2 transition-colors duration-200 ease-in-out
                focus:outline-none"
        >
            <UiIcon name="MdiGithub" class="h-5 w-5 mr-2" />
            Login with GitHub
        </a>
    </div>
</template>

<style scoped></style>