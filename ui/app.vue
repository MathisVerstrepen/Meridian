<script lang="ts" setup>
const route = useRoute();
const layout = computed(() => {
    return route.path.includes('/graph/') ? 'canvas' : false;
});
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout :name="layout">
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
