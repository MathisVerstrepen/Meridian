<script lang="ts" setup>
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import { imagePlaygroundAspectClass, imagePlaygroundImageUrl } from '@/utils/imagePlayground';

defineProps<{
    image: GeneratedImageGalleryItem;
    index: number;
    modelDisplayName: (modelId?: string | null) => string;
}>();

const emit = defineEmits<{
    (e: 'select', image: GeneratedImageGalleryItem): void;
    (e: 'reuse', image: GeneratedImageGalleryItem): void;
    (e: 'delete', image: GeneratedImageGalleryItem): void;
}>();
</script>

<template>
    <button
        type="button"
        class="archive-tile group bg-obsidian/60 border-stone-gray/12 relative flex h-full
            overflow-hidden rounded-2xl border text-left"
        :style="{ animationDelay: `${Math.min(index, 12) * 30}ms` }"
        @click="emit('select', image)"
    >
        <img
            :src="imagePlaygroundImageUrl(image.id, true)"
            alt=""
            aria-hidden="true"
            loading="lazy"
            class="absolute inset-0 h-full w-full scale-110 object-cover opacity-45 blur-xl transition
                duration-500 group-hover:scale-[1.15]"
        />
        <div class="absolute inset-0 bg-black/30" />

        <div class="relative flex h-full w-full items-center justify-center overflow-hidden">
            <div
                class="bg-obsidian/40 relative w-full overflow-hidden"
                :class="imagePlaygroundAspectClass(image)"
            >
                <img
                    :src="imagePlaygroundImageUrl(image.id, true)"
                    :alt="image.name"
                    loading="lazy"
                    class="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
                />
            </div>
        </div>

        <div
            class="pointer-events-none absolute inset-0 bg-linear-to-t from-black/85 via-black/20
                to-black/35 opacity-0 transition duration-300 group-hover:opacity-100"
        />

        <div
            class="pointer-events-auto absolute inset-x-0 bottom-0 flex items-end justify-between gap-2
                p-2.5 opacity-0 transition duration-300 group-hover:opacity-100"
        >
            <div class="min-w-0 flex-1">
                <p class="text-soft-silk line-clamp-2 text-[11px] leading-tight font-semibold">
                    {{ image.prompt || image.name }}
                </p>
                <p class="text-stone-gray/70 mt-1 truncate text-[9px] tracking-wider uppercase">
                    {{ modelDisplayName(image.model) }}
                </p>
            </div>
            <div class="flex shrink-0 gap-1">
                <span
                    class="quick-action"
                    role="button"
                    tabindex="0"
                    title="Reuse settings"
                    @click.stop="emit('reuse', image)"
                    @keydown.enter.stop.prevent="emit('reuse', image)"
                >
                    <UiIcon
                        name="MaterialSymbolsControlPointDuplicateOutlineRounded"
                        class="h-3.5 w-3.5"
                    />
                </span>
                <a
                    class="quick-action"
                    :href="imagePlaygroundImageUrl(image.id)"
                    :download="image.name"
                    title="Download"
                    @click.stop
                >
                    <UiIcon name="UilDownloadAlt" class="h-3.5 w-3.5" />
                </a>
                <span
                    class="quick-action quick-action-danger"
                    role="button"
                    tabindex="0"
                    title="Delete"
                    @click.stop="emit('delete', image)"
                    @keydown.enter.stop.prevent="emit('delete', image)"
                >
                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-3.5 w-3.5" />
                </span>
            </div>
        </div>

        <div
            class="absolute top-2 left-2 flex items-center gap-1.5 opacity-0 transition
                group-hover:opacity-100"
        >
            <span
                v-if="image.aspect_ratio"
                class="border-soft-silk/20 bg-obsidian/70 text-soft-silk/85 rounded-full border
                    px-1.5 pt-0.5 font-mono text-[10px] tracking-wider uppercase backdrop-blur"
            >
                {{ image.aspect_ratio }}
            </span>
            <span
                v-if="image.resolution"
                class="border-soft-silk/20 bg-obsidian/70 text-soft-silk/85 rounded-full border
                    px-1.5 pt-0.5 font-mono text-[10px] tracking-wider uppercase backdrop-blur"
            >
                {{ image.resolution }}
            </span>
        </div>
    </button>
</template>
