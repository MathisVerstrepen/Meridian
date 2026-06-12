<script lang="ts" setup>
type MediaPlaygroundMode = 'image-generation' | 'image-edit' | 'video-generation';

const mode = defineModel<MediaPlaygroundMode>('mode', { required: true });

const playgroundStore = useImagePlaygroundStore();
const { activeJobs } = storeToRefs(playgroundStore);

const modeOptions: { label: string; value: MediaPlaygroundMode }[] = [
    { label: 'Image generation', value: 'image-generation' },
    { label: 'Image edit', value: 'image-edit' },
    { label: 'Video generation', value: 'video-generation' },
];

const liveJobCount = computed(
    () =>
        activeJobs.value.filter((job) => {
            if (job.status === 'completed' || job.status === 'failed') return false;
            if (mode.value === 'video-generation') return job.media_type === 'video';
            return job.media_type !== 'video';
        }).length,
);
</script>

<template>
    <header class="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div class="flex flex-wrap items-end gap-6 lg:gap-10">
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
                    Media playground
                </h1>
            </div>
        </div>

        <div class="flex flex-wrap items-center justify-end gap-3">
            <div
                class="border-stone-gray/12 bg-soft-silk/5 flex rounded-full border p-1
                    shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                aria-label="Media playground mode"
            >
                <button
                    v-for="option in modeOptions"
                    :key="option.value"
                    type="button"
                    class="rounded-full px-3.5 py-1.5 text-[11px] font-semibold tracking-[0.16em]
                        uppercase transition"
                    :class="
                        mode === option.value
                            ? 'bg-ember-glow text-obsidian shadow-[0_0_24px_-10px_rgba(235,94,40,0.9)]'
                            : 'text-stone-gray hover:text-soft-silk hover:bg-soft-silk/7'
                    "
                    @click="mode = option.value"
                >
                    {{ option.label }}
                </button>
            </div>

            <Transition name="status">
                <div
                    v-if="['image-generation', 'video-generation'].includes(mode) && liveJobCount > 0"
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
                        {{ mode === 'video-generation' ? 'Rendering' : 'Creating' }} × {{ liveJobCount }}
                    </span>
                </div>
            </Transition>
        </div>
    </header>
</template>
