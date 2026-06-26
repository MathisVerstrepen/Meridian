<script lang="ts" setup>
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import {
    imagePlaygroundActualDimensions,
    imagePlaygroundDownloadName,
    imagePlaygroundDownloadUrl,
    imagePlaygroundDisplayAspectRatio,
    imagePlaygroundFormatBytes,
    imagePlaygroundFormatDate,
    imagePlaygroundGenerationElapsedTime,
    imagePlaygroundImageUrl,
    imagePlaygroundStyleLabel,
} from '@/utils/imagePlayground';

const props = withDefaults(
    defineProps<{
        image: GeneratedImageGalleryItem | null;
        modelDisplayName: (modelId?: string | null) => string;
        modelIconName?: (modelId?: string | null) => string;
        canGoPrevious?: boolean;
        canGoNext?: boolean;
        position?: number | null;
        total?: number | null;
    }>(),
    {
        modelIconName: () => 'MaterialSymbolsElectricBoltRounded',
        canGoPrevious: false,
        canGoNext: false,
        position: null,
        total: null,
    },
);

const { getFileBlob } = useAPI();

const emit = defineEmits<{
    (e: 'close'): void;
    (e: 'copy', text?: string | null): void;
    (e: 'reuse', image: GeneratedImageGalleryItem): void;
    (e: 'delete', image: GeneratedImageGalleryItem): void;
    (e: 'previous'): void;
    (e: 'next'): void;
}>();

const hasNavigation = computed(() => props.canGoPrevious || props.canGoNext);
const showCounter = computed(
    () =>
        Number.isFinite(props.position) &&
        Number.isFinite(props.total) &&
        (props.total ?? 0) > 0 &&
        (props.position ?? 0) > 0,
);
const hasPrompt = computed(() => Boolean(props.image?.prompt));

const showDetails = ref(false);
const toggleDetails = () => {
    showDetails.value = !showDetails.value;
};

const handleKeydown = (event: KeyboardEvent) => {
    if (!props.image) return;

    if (event.key === 'Escape') {
        event.preventDefault();
        emit('close');
        return;
    }

    if (event.key.toLowerCase() === 'i' && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        toggleDetails();
        return;
    }

    if (event.key === 'ArrowLeft' && props.canGoPrevious) {
        event.preventDefault();
        emit('previous');
        return;
    }

    if (event.key === 'ArrowRight' && props.canGoNext) {
        event.preventDefault();
        emit('next');
    }
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleKeydown);
});

const openReferenceInNewTab = async (referenceId: string) => {
    const tab = window.open('about:blank', '_blank');
    if (tab) {
        tab.opener = null;
    }
    try {
        const blob = await getFileBlob(referenceId);
        const url = URL.createObjectURL(blob);
        if (tab) {
            tab.location.href = url;
        } else {
            window.open(url, '_blank', 'noopener,noreferrer');
        }
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
        console.error('Reference image open failed:', error);
        tab?.close();
        window.open(imagePlaygroundImageUrl(referenceId), '_blank', 'noopener,noreferrer');
    }
};

const chipBtn =
    'flex items-center justify-center rounded-full border border-soft-silk/15 bg-obsidian/55 text-soft-silk/85 backdrop-blur-md transition hover:scale-105 hover:border-ember-glow/55 hover:text-ember-glow';
const tooltip =
    'pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-soft-silk/12 bg-obsidian/95 px-2 py-1 font-mono text-[9px] tracking-[0.18em] text-soft-silk/85 opacity-0 shadow-lg transition group-hover:opacity-100';
</script>

<template>
    <Transition name="modal">
        <div
            v-if="image"
            class="fixed inset-0 z-50 flex items-center justify-center overflow-hidden bg-black/90 p-4
                backdrop-blur-md transition-[padding] duration-300 ease-out"
            :class="{ 'lg:pr-[400px]': showDetails }"
            @click="emit('close')"
        >
            <div
                class="pointer-events-none absolute inset-0 bg-radial-[720px_420px_at_50%_42%] from-ember-glow/10
                    via-transparent to-transparent"
                aria-hidden="true"
            />

            <template v-if="hasNavigation && !showDetails">
                <button
                    v-if="canGoPrevious"
                    type="button"
                    :class="[chipBtn, 'absolute top-1/2 left-3 z-40 h-12 w-12 -translate-y-1/2 md:left-5']"
                    aria-label="Previous image"
                    @click.stop="emit('previous')"
                >
                    <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6 rotate-90" />
                </button>
                <button
                    v-if="canGoNext"
                    type="button"
                    :class="[chipBtn, 'absolute top-1/2 right-3 z-40 h-12 w-12 -translate-y-1/2 md:right-5']"
                    aria-label="Next image"
                    @click.stop="emit('next')"
                >
                    <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6 -rotate-90" />
                </button>
            </template>

            <img
                :src="imagePlaygroundImageUrl(image.id)"
                :alt="image.name"
                class="relative z-10 max-h-[88vh] max-w-full rounded-2xl object-contain
                    shadow-[0_30px_90px_-20px_rgba(0,0,0,0.95)]"
                @click.stop
            />

            <div
                class="absolute inset-x-3 top-3 z-40 flex items-center justify-between gap-3 md:inset-x-5 md:top-5"
                @click.stop
            >
                <div class="flex min-w-0 items-center gap-2">
                    <span
                        class="flex min-w-0 items-center gap-2 rounded-full border border-soft-silk/12 bg-obsidian/55
                            px-3 py-1.5 backdrop-blur-md"
                    >
                        <UiIcon :name="modelIconName(image.model)" class="h-3.5 w-3.5 shrink-0 text-soft-silk/85" />
                        <span
                            class="truncate font-mono text-[10px] tracking-[0.16em] text-soft-silk/85 uppercase"
                        >
                            {{ modelDisplayName(image.model) }}
                        </span>
                    </span>
                    <span
                        v-if="showCounter"
                        class="rounded-full border border-soft-silk/12 bg-obsidian/55 px-2.5 py-1.5 font-mono
                            text-[10px] tracking-[0.18em] text-stone-gray backdrop-blur-md"
                    >
                        {{ String(position).padStart(2, '0') }} / {{ total }}
                    </span>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                    <button
                        type="button"
                        :class="[chipBtn, 'h-10 w-10', showDetails ? 'border-ember-glow/60 text-ember-glow' : '']"
                        :aria-pressed="showDetails"
                        aria-label="Toggle details"
                        @click.stop="toggleDetails"
                    >
                        <UiIcon name="MaterialSymbolsInfoRounded" class="h-4 w-4" />
                    </button>
                    <button
                        type="button"
                        :class="[chipBtn, 'h-10 w-10']"
                        aria-label="Close"
                        @click.stop="emit('close')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    </button>
                </div>
            </div>

            <div
                class="absolute bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5 rounded-full
                    border border-soft-silk/12 bg-obsidian/65 p-1.5 shadow-[0_18px_50px_-22px_rgba(0,0,0,0.95)]
                    backdrop-blur-md md:bottom-5"
                @click.stop
            >
                <div class="group relative">
                    <button
                        type="button"
                        :class="
                            hasPrompt
                                ? chipBtn
                                : 'flex h-11 w-11 cursor-not-allowed items-center justify-center rounded-full border border-soft-silk/10 bg-obsidian/30 text-soft-silk/30'
                        "
                        class="h-11 w-11"
                        :disabled="!hasPrompt"
                        aria-label="Copy prompt"
                        @click.stop="emit('copy', image.prompt)"
                    >
                        <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="h-4 w-4" />
                    </button>
                    <span :class="tooltip">Copy prompt</span>
                </div>

                <div class="group relative">
                    <a
                        :href="imagePlaygroundDownloadUrl(image.id)"
                        :download="imagePlaygroundDownloadName(image)"
                        :class="[chipBtn, 'h-11 w-11']"
                        aria-label="Download"
                    >
                        <UiIcon name="MaterialSymbolsDownloadRounded" class="h-4 w-4" />
                    </a>
                    <span :class="tooltip">Download</span>
                </div>

                <div class="group relative">
                    <button
                        type="button"
                        class="text-obsidian flex h-12 w-12 items-center justify-center rounded-full
                            bg-linear-to-r from-[#f76e3a] via-ember-glow to-[#c44a1c] shadow-[0_0_28px_-8px_rgba(235,94,40,0.85)]
                            transition hover:scale-105 hover:brightness-110"
                        aria-label="Reuse settings"
                        @click.stop="emit('reuse', image)"
                    >
                        <UiIcon name="MaterialSymbolsControlPointDuplicateOutlineRounded" class="h-5 w-5" />
                    </button>
                    <span :class="tooltip">Reuse settings</span>
                </div>

                <div class="group relative">
                    <button
                        type="button"
                        class="flex h-11 w-11 items-center justify-center rounded-full border border-red-400/30
                            bg-red-500/12 text-red-200/85 transition hover:scale-105 hover:border-red-400/60
                            hover:bg-red-500/20 hover:text-red-100"
                        aria-label="Delete"
                        @click.stop="emit('delete', image)"
                    >
                        <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                    </button>
                    <span :class="tooltip">Delete</span>
                </div>
            </div>

            <aside
                class="custom_scroll absolute top-[4.75rem] right-3 bottom-[5.25rem] z-30 flex w-[88%] max-w-[360px]
                    flex-col overflow-hidden rounded-3xl border border-soft-silk/12 bg-anthracite/90
                    shadow-[0_30px_90px_-25px_rgba(0,0,0,0.85)] backdrop-blur-xl transition-all duration-300 ease-out
                    md:right-5"
                :class="
                    showDetails
                        ? 'translate-x-0 opacity-100'
                        : 'pointer-events-none translate-x-[115%] opacity-0'
                "
                @click.stop
            >
                <header
                    class="border-stone-gray/12 flex shrink-0 items-center justify-between gap-3 border-b px-5 pt-4
                        pb-4"
                >
                    <div class="min-w-0">
                        <p class="text-stone-gray/60 mb-1 font-mono text-[9px] tracking-[0.3em] uppercase">
                            Generation
                        </p>
                        <h3 class="font-outfit text-soft-silk truncate text-lg leading-tight font-bold">
                            Details
                        </h3>
                        <p
                            class="text-stone-gray/70 mt-0.5 flex items-center gap-1.5 font-mono text-[10px]"
                        >
                            <UiIcon name="MdiCalendarMonth" class="h-3 w-3" />
                            {{ imagePlaygroundFormatDate(image.created_at) }}
                        </p>
                    </div>
                    <button
                        type="button"
                        :class="[chipBtn, 'h-8 w-8']"
                        aria-label="Hide details"
                        @click.stop="toggleDetails"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-3.5 w-3.5" />
                    </button>
                </header>

                <div class="custom_scroll min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5 text-sm">
                    <section>
                        <div class="mb-2 flex items-center justify-between gap-2">
                            <p class="text-stone-gray/60 font-mono text-[9px] tracking-[0.3em] uppercase">
                                Directive
                            </p>
                            <button
                                v-if="hasPrompt"
                                type="button"
                                class="text-stone-gray hover:text-ember-glow flex items-center gap-1 text-[10px]
                                    tracking-widest uppercase transition"
                                @click.stop="emit('copy', image.prompt)"
                            >
                                <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="h-3 w-3" />
                                Copy
                            </button>
                        </div>
                        <p
                            class="custom_scroll text-soft-silk/90 border-stone-gray/10 bg-obsidian/40 max-h-44
                                overflow-y-auto rounded-2xl border p-3 leading-relaxed whitespace-pre-wrap"
                        >
                            {{ image.prompt || 'No prompt metadata.' }}
                        </p>
                    </section>

                    <section>
                        <p class="text-stone-gray/60 mb-2 font-mono text-[9px] tracking-[0.3em] uppercase">
                            Details
                        </p>
                        <dl
                            class="border-stone-gray/10 bg-obsidian/35 divide-stone-gray/10 overflow-hidden rounded-2xl
                                border text-xs"
                        >
                            <div class="flex items-start justify-between gap-4 px-3 py-2">
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Model</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ modelDisplayName(image.model) }}
                                </dd>
                            </div>
                            <div
                                v-if="image.resolution"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Resolution</dt>
                                <dd class="text-soft-silk text-right font-semibold">{{ image.resolution }}</dd>
                            </div>
                            <div
                                v-if="image.actual_aspect_ratio || (image.actual_width && image.actual_height)"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Actual ratio</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ imagePlaygroundDisplayAspectRatio(image) }}
                                </dd>
                            </div>
                            <div
                                v-if="imagePlaygroundActualDimensions(image)"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Dimensions</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ imagePlaygroundActualDimensions(image) }}
                                </dd>
                            </div>
                            <div
                                v-if="image.aspect_ratio"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Requested ratio</dt>
                                <dd class="text-soft-silk text-right font-semibold">{{ image.aspect_ratio }}</dd>
                            </div>
                            <div
                                v-if="image.style_preset"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Style</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ imagePlaygroundStyleLabel(image.style_preset) }}
                                </dd>
                            </div>
                            <div
                                v-if="imagePlaygroundGenerationElapsedTime(image)"
                                class="border-stone-gray/10 flex items-start justify-between gap-4 border-t px-3 py-2"
                            >
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Elapsed time</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ imagePlaygroundGenerationElapsedTime(image) }}
                                </dd>
                            </div>
                            <div class="flex items-start justify-between gap-4 px-3 py-2">
                                <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Size</dt>
                                <dd class="text-soft-silk text-right font-semibold">
                                    {{ imagePlaygroundFormatBytes(image.size) }}
                                </dd>
                            </div>
                        </dl>
                    </section>

                    <section v-if="image.source_image_ids.length">
                        <p
                            class="text-stone-gray/60 mb-2 flex items-center gap-1.5 font-mono text-[9px]
                                tracking-[0.3em] uppercase"
                        >
                            <UiIcon name="MdiImageMultipleOutline" class="h-3 w-3" />
                            References · {{ image.source_image_ids.length }}
                        </p>
                        <div class="grid grid-cols-3 gap-2">
                            <a
                                v-for="referenceId in image.source_image_ids"
                                :key="referenceId"
                                :href="imagePlaygroundImageUrl(referenceId)"
                                target="_blank"
                                rel="noreferrer"
                                class="border-stone-gray/15 bg-obsidian/50 hover:border-ember-glow/45
                                    group/reference aspect-square overflow-hidden rounded-xl border transition"
                                :title="`Open reference ${referenceId}`"
                                @click.prevent="openReferenceInNewTab(referenceId)"
                            >
                                <img
                                    :src="imagePlaygroundImageUrl(referenceId, true)"
                                    alt="Reference image used for this generation"
                                    loading="lazy"
                                    class="h-full w-full object-cover transition duration-300
                                        group-hover/reference:scale-105"
                                />
                            </a>
                        </div>
                    </section>
                </div>
            </aside>
        </div>
    </Transition>
</template>
