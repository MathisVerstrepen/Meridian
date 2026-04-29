<script lang="ts" setup>
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import {
    imagePlaygroundActualDimensions,
    imagePlaygroundFormatBytes,
    imagePlaygroundFormatDate,
    imagePlaygroundImageUrl,
    imagePlaygroundStyleLabel,
} from '@/utils/imagePlayground';

defineProps<{
    image: GeneratedImageGalleryItem | null;
    modelDisplayName: (modelId?: string | null) => string;
}>();

const emit = defineEmits<{
    (e: 'close'): void;
    (e: 'copy', text?: string | null): void;
    (e: 'reuse', image: GeneratedImageGalleryItem): void;
    (e: 'delete', image: GeneratedImageGalleryItem): void;
}>();
</script>

<template>
    <Transition name="modal">
        <div
            v-if="image"
            class="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md"
            @click="emit('close')"
        >
            <div
                class="bg-anthracite/95 border-stone-gray/15 grid max-h-[94vh] w-full max-w-6xl
                    grid-cols-1 overflow-hidden rounded-3xl border
                    shadow-[0_30px_120px_-20px_rgba(0,0,0,0.8)] lg:grid-cols-[1fr_360px]"
                @click.stop
            >
                <div class="relative flex min-h-0 items-center justify-center overflow-hidden bg-black p-4 lg:p-6">
                    <div
                        class="pointer-events-none absolute inset-0 bg-radial-[500px_300px_at_50%_50%]
                            from-ember-glow/12 to-transparent"
                        aria-hidden="true"
                    />
                    <img
                        :src="imagePlaygroundImageUrl(image.id)"
                        :alt="image.name"
                        class="relative max-h-[86vh] max-w-full rounded-2xl object-contain
                            shadow-[0_20px_60px_-10px_rgba(0,0,0,0.9)]"
                    />
                    <button
                        type="button"
                        class="border-soft-silk/20 bg-obsidian/60 text-soft-silk/80 hover:text-soft-silk
                            hover:border-soft-silk/40 absolute top-4 right-4 flex h-9 w-9 items-center
                            justify-center rounded-full border backdrop-blur transition lg:hidden"
                        @click="emit('close')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    </button>
                </div>
                <aside class="custom_scroll flex flex-col overflow-y-auto">
                    <div class="border-stone-gray/12 flex items-start justify-between gap-3 border-b px-5 pt-5 pb-4">
                        <div>
                            <p class="text-stone-gray/60 mb-1 font-mono text-[9px] tracking-[0.3em] uppercase">
                                Plate
                            </p>
                            <h3 class="font-outfit text-soft-silk text-xl leading-tight font-bold">
                                Generation details
                            </h3>
                            <p class="text-stone-gray/65 mt-1 font-mono text-[10px]">
                                {{ imagePlaygroundFormatDate(image.created_at) }}
                            </p>
                        </div>
                        <button
                            type="button"
                            class="border-stone-gray/20 text-stone-gray hover:text-soft-silk
                                hover:border-stone-gray/45 hidden h-8 w-8 items-center justify-center
                                rounded-full border transition lg:flex"
                            aria-label="Close"
                            @click="emit('close')"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                        </button>
                    </div>

                    <div class="space-y-5 px-5 pt-5 pb-5 text-sm">
                        <div>
                            <div class="mb-2 flex items-center justify-between">
                                <p class="text-stone-gray/60 font-mono text-[9px] tracking-[0.3em] uppercase">
                                    Directive
                                </p>
                                <button
                                    v-if="image.prompt"
                                    type="button"
                                    class="text-stone-gray hover:text-ember-glow flex items-center gap-1
                                        text-[10px] tracking-widest uppercase transition"
                                    @click="emit('copy', image.prompt)"
                                >
                                    <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="h-3 w-3" />
                                    Copy
                                </button>
                            </div>
                            <p
                                class="text-soft-silk/90 border-stone-gray/10 bg-obsidian/40 rounded-xl
                                    border p-3 leading-relaxed whitespace-pre-wrap"
                            >
                                {{ image.prompt || 'No prompt metadata.' }}
                            </p>
                        </div>

                        <div>
                            <p class="text-stone-gray/60 mb-2 font-mono text-[9px] tracking-[0.3em] uppercase">
                                Details
                            </p>
                            <dl
                                class="border-stone-gray/10 bg-obsidian/35 divide-stone-gray/10 overflow-hidden
                                    rounded-xl border text-xs"
                            >
                                <div class="flex items-start justify-between gap-4 px-3 py-2">
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Model</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ modelDisplayName(image.model) }}
                                    </dd>
                                </div>
                                <div
                                    v-if="image.resolution"
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Resolution</dt>
                                    <dd class="text-soft-silk text-right font-semibold">{{ image.resolution }}</dd>
                                </div>
                                <div
                                    v-if="image.actual_aspect_ratio"
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Actual ratio</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ image.actual_aspect_ratio }}
                                    </dd>
                                </div>
                                <div
                                    v-if="imagePlaygroundActualDimensions(image)"
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Dimensions</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ imagePlaygroundActualDimensions(image) }}
                                    </dd>
                                </div>
                                <div
                                    v-if="image.aspect_ratio"
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Requested ratio</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ image.aspect_ratio }}
                                    </dd>
                                </div>
                                <div
                                    v-if="image.style_preset"
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Style</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ imagePlaygroundStyleLabel(image.style_preset) }}
                                    </dd>
                                </div>
                                <div
                                    class="border-stone-gray/10 flex items-start justify-between gap-4
                                        border-t px-3 py-2"
                                >
                                    <dt class="text-stone-gray/65 shrink-0 font-mono uppercase">Size</dt>
                                    <dd class="text-soft-silk text-right font-semibold">
                                        {{ imagePlaygroundFormatBytes(image.size) }}
                                    </dd>
                                </div>
                            </dl>
                        </div>

                        <div v-if="image.source_image_ids.length">
                            <p class="text-stone-gray/60 mb-2 font-mono text-[9px] tracking-[0.3em] uppercase">
                                References
                            </p>
                            <div class="grid grid-cols-4 gap-2">
                                <a
                                    v-for="referenceId in image.source_image_ids"
                                    :key="referenceId"
                                    :href="imagePlaygroundImageUrl(referenceId)"
                                    target="_blank"
                                    rel="noreferrer"
                                    class="border-stone-gray/15 bg-obsidian/50 hover:border-ember-glow/45
                                        group/reference aspect-square overflow-hidden rounded-xl border transition"
                                    :title="`Open reference ${referenceId}`"
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
                        </div>
                    </div>

                    <div class="border-stone-gray/12 bg-obsidian/30 mt-auto grid gap-1.5 border-t p-4">
                        <button
                            type="button"
                            class="text-obsidian group relative isolate w-full overflow-hidden rounded-2xl
                                px-4 py-3.5"
                            @click="emit('reuse', image)"
                        >
                            <span
                                class="absolute inset-0 z-0 bg-linear-to-r from-[#f76e3a]
                                    via-ember-glow to-[#c44a1c] transition duration-300
                                    group-hover:scale-[1.02] group-hover:brightness-110"
                            />
                            <span
                                class="pointer-events-none absolute inset-0 z-0 bg-radial-[120px_60px_at_30%_0%]
                                    from-white/35 to-transparent opacity-70"
                            />
                            <span class="relative z-10 flex items-center justify-center gap-2">
                                <UiIcon
                                    name="MaterialSymbolsControlPointDuplicateOutlineRounded"
                                    class="h-4 w-4"
                                />
                                <span class="font-outfit text-sm font-bold tracking-tight">Reuse settings</span>
                            </span>
                        </button>
                        <div class="grid grid-cols-2 gap-1.5">
                            <a
                                :href="imagePlaygroundImageUrl(image.id)"
                                :download="image.name"
                                class="border-stone-gray/20 hover:border-ember-glow/45 text-soft-silk/85
                                    hover:text-soft-silk flex items-center justify-center gap-1.5 rounded-xl
                                    border py-2.5 text-xs font-semibold tracking-wide uppercase transition"
                            >
                                <UiIcon name="UilDownloadAlt" class="h-3.5 w-3.5" />
                                Download
                            </a>
                            <button
                                type="button"
                                class="flex items-center justify-center gap-1.5 rounded-xl border
                                    border-red-400/25 bg-red-500/8 py-2.5 text-xs font-semibold
                                    tracking-wide text-red-200/85 uppercase transition hover:border-red-400/55
                                    hover:bg-red-500/15 hover:text-red-100"
                                @click="emit('delete', image)"
                            >
                                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-3.5 w-3.5" />
                                Delete
                            </button>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    </Transition>
</template>
