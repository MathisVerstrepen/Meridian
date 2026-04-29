<script lang="ts" setup>
const playgroundStore = useImagePlaygroundStore();
const { activeJobs, isLoadingGallery } = storeToRefs(playgroundStore);
const { loadGallery } = playgroundStore;

const liveJobCount = computed(
    () =>
        activeJobs.value.filter((job) => job.status !== 'completed' && job.status !== 'failed')
            .length,
);
</script>

<template>
    <header class="mb-4 flex items-center justify-between">
        <div class="flex items-end gap-10">
            <NuxtLink
                to="/"
                class="text-stone-gray hover:text-soft-silk group mb-1 flex items-center gap-2
                    text-xs tracking-[0.3em] uppercase transition"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-4 w-4 rotate-90" />
                Home
            </NuxtLink>
            <div>
                <h1 class="font-outfit text-soft-silk text-3xl leading-none font-bold tracking-tight">
                    Image playground
                </h1>
            </div>
        </div>
        <div class="flex items-center gap-3">
            <Transition name="status">
                <div
                    v-if="liveJobCount > 0"
                    class="border-ember-glow/35 bg-ember-glow/10 text-ember-glow flex items-center
                        gap-2.5 rounded-full border px-3.5 py-1.5"
                >
                    <span class="relative flex h-2 w-2 drop-shadow-[0_0_6px_rgba(235,94,40,0.65)]">
                        <span
                            class="bg-ember-glow absolute inline-flex h-full w-full animate-ping
                                rounded-full opacity-75"
                        />
                        <span class="bg-ember-glow relative inline-flex h-2 w-2 rounded-full" />
                    </span>
                    <span class="text-[11px] font-semibold tracking-[0.2em] uppercase">
                        Creating × {{ liveJobCount }}
                    </span>
                </div>
            </Transition>
            <button
                type="button"
                :disabled="isLoadingGallery"
                class="border-stone-gray/15 bg-anthracite/40 text-stone-gray hover:text-soft-silk
                    hover:border-stone-gray/35 inline-flex h-9 w-9 items-center justify-center
                    rounded-full border backdrop-blur transition disabled:opacity-40"
                title="Refresh gallery"
                @click="loadGallery"
            >
                <UiIcon
                    name="MaterialSymbolsRefreshRounded"
                    class="h-4 w-4"
                    :class="{ 'animate-spin': isLoadingGallery }"
                />
            </button>
        </div>
    </header>
</template>
