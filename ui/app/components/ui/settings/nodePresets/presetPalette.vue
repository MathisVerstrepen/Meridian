<script setup lang="ts">
import { MAX_PRESET_NODES } from '@/types/nodePresets';

defineProps<{
    nodeCount: number;
    freePlan: boolean;
}>();

const emit = defineEmits<{ add: [blockId: string] }>();
const { blockDefinitions } = useBlocks();
const blocks = computed(() => Object.values(blockDefinitions.value).flat());

const scroller = ref<HTMLElement | null>(null);
const canScrollLeft = ref(false);
const canScrollRight = ref(false);
const prefersReducedMotion = ref(false);
let resizeObserver: ResizeObserver | null = null;
let reducedMotionQuery: MediaQueryList | null = null;

const updateScrollState = () => {
    const element = scroller.value;
    if (!element) return;
    canScrollLeft.value = element.scrollLeft > 1;
    canScrollRight.value = element.scrollLeft + element.clientWidth < element.scrollWidth - 1;
};

const scrollBlocks = (direction: -1 | 1) => {
    const element = scroller.value;
    if (!element) return;
    element.scrollBy({
        left: direction * Math.max(element.clientWidth * 0.75, 120),
        behavior: prefersReducedMotion.value ? 'auto' : 'smooth',
    });
};

const updateReducedMotion = () => {
    prefersReducedMotion.value = reducedMotionQuery?.matches ?? false;
};

watch(
    () => blocks.value.map((block) => block.id).join('|'),
    async () => {
        await nextTick();
        updateScrollState();
    },
);

onMounted(async () => {
    reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    updateReducedMotion();
    reducedMotionQuery.addEventListener('change', updateReducedMotion);
    window.addEventListener('resize', updateScrollState);
    if (!isRuntimeUndefined(ResizeObserver) && scroller.value) {
        resizeObserver = new ResizeObserver(updateScrollState);
        resizeObserver.observe(scroller.value);
    }
    await nextTick();
    updateScrollState();
});

onBeforeUnmount(() => {
    resizeObserver?.disconnect();
    reducedMotionQuery?.removeEventListener('change', updateReducedMotion);
    window.removeEventListener('resize', updateScrollState);
});
</script>

<template>
    <aside
        aria-label="Blocks palette"
        class="border-soft-silk/10 bg-obsidian/85 shadow-obsidian/60 absolute right-3 bottom-3 left-3 z-20 min-w-0 rounded-2xl border p-2 shadow-2xl backdrop-blur-xl"
    >
        <div class="mb-1.5 flex items-center gap-2 px-1">
            <span class="bg-ember-glow/15 text-ember-glow flex h-6 w-6 items-center justify-center rounded-md">
                <UiIcon name="MaterialSymbolsDashboardCustomizeOutlineRounded" class="h-3.5 w-3.5" />
            </span>
            <h2 class="text-soft-silk text-xs font-bold">Blocks</h2>
            <span class="bg-stone-gray/10 text-stone-gray/75 ml-auto shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold">
                {{ nodeCount }}/{{ MAX_PRESET_NODES }}
            </span>
        </div>
        <div class="flex min-w-0 items-center gap-1">
            <button
                type="button"
                aria-label="Scroll blocks left"
                title="Scroll blocks left"
                :disabled="!canScrollLeft"
                :class="[
                    'focus-visible:ring-ember-glow/70 flex h-10 w-8 shrink-0 items-center justify-center rounded-lg border outline-none transition-colors focus-visible:ring-2 disabled:cursor-default',
                    canScrollLeft
                        ? 'border-ember-glow/35 bg-anthracite text-soft-silk hover:border-ember-glow/60'
                        : 'border-stone-gray/10 text-stone-gray/25 bg-transparent',
                ]"
                @click="scrollBlocks(-1)"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-4 w-4 rotate-90" />
            </button>

            <div
                ref="scroller"
                data-testid="block-palette-scroller"
                class="hide-scrollbar flex min-w-0 flex-1 gap-1.5 overflow-x-auto pb-0.5"
                role="toolbar"
                aria-label="Add block"
                @scroll.passive="updateScrollState"
            >
                <button
                    v-for="block in blocks"
                    :key="block.id"
                    type="button"
                    :aria-label="block.name"
                    :title="block.nodeType === 'github' && freePlan ? 'GitHub blocks require Premium' : block.desc"
                    class="border-stone-gray/15 bg-anthracite/65 hover:border-stone-gray/40 hover:bg-anthracite focus-visible:ring-ember-glow/70 group flex min-h-10 w-32 shrink-0 items-center gap-2 rounded-lg border px-2 py-1.5 text-left transition-colors outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-45"
                    :disabled="nodeCount >= MAX_PRESET_NODES || (block.nodeType === 'github' && freePlan)"
                    @click="emit('add', block.id)"
                >
                    <span class="bg-obsidian/55 flex h-7 w-7 shrink-0 items-center justify-center rounded-md">
                        <UiIcon :name="block.icon" class="h-4 w-4" :style="{ color: block.color }" />
                    </span>
                    <span class="text-soft-silk min-w-0 flex-1 truncate text-xs font-semibold">{{ block.name }}</span>
                    <UiIcon
                        v-if="block.nodeType === 'github' && freePlan"
                        name="MaterialSymbolsLockOutline"
                        class="text-stone-gray/70 h-3.5 w-3.5 shrink-0"
                    />
                </button>
            </div>

            <button
                type="button"
                aria-label="Scroll blocks right"
                title="Scroll blocks right"
                :disabled="!canScrollRight"
                :class="[
                    'focus-visible:ring-ember-glow/70 flex h-10 w-8 shrink-0 items-center justify-center rounded-lg border outline-none transition-colors focus-visible:ring-2 disabled:cursor-default',
                    canScrollRight
                        ? 'border-ember-glow/35 bg-anthracite text-soft-silk hover:border-ember-glow/60'
                        : 'border-stone-gray/10 text-stone-gray/25 bg-transparent',
                ]"
                @click="scrollBlocks(1)"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-4 w-4 -rotate-90" />
            </button>
        </div>
        <p v-if="nodeCount >= MAX_PRESET_NODES" class="px-1 pt-2 text-[11px] text-amber-400" role="status">
            Node limit reached. Remove a block before adding another.
        </p>
    </aside>
</template>
