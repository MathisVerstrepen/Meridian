<script lang="ts" setup>
const { getOpenRouterModels } = useAPI();

const modelStore = useModelStore();
const { models } = storeToRefs(modelStore);

provideHeadlessUseId(() => useId());

const { data } = await useAsyncData('users', () => getOpenRouterModels());

onMounted(() => {
    models.value = data.value?.data || [];
});
</script>

<template>
    <div class="bg-obsidian flex h-screen w-screen items-center justify-center">
        <NuxtLayout>
            <NuxtPage />
        </NuxtLayout>
    </div>
</template>
