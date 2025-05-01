<script lang="ts" setup>
const { getOpenRouterModels } = useAPI();

const modelStore = useModelStore();
const { models } = storeToRefs(modelStore);

const route = useRoute();

const layout = computed(() => {
    return route.path.includes('/graph/') ? 'canvas' : false;
});

provideHeadlessUseId(() => useId());

const { data } = await useAsyncData('users', () => getOpenRouterModels());

onMounted(() => {
    models.value = data.value?.data || [];
});
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout :name="layout">
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
