<script lang="ts" setup>
import type { GenerationHistoryEntry } from '@/types/graph';
import { TOOLS } from '@/constants/tools';

const props = withDefaults(
    defineProps<{
        graphId: string;
        nodeId?: string | null;
        buttonClass?: string;
        iconClass?: string;
        panelClass?: string;
        panelPosition?: 'above' | 'below';
        refreshChatOnRestore?: boolean;
    }>(),
    {
        nodeId: null,
        buttonClass: '',
        iconClass: 'h-5 w-5',
        panelClass: '',
        panelPosition: 'below',
        refreshChatOnRestore: false,
    },
);

const emit = defineEmits<{
    restored: [nodeData: Record<string, unknown> | unknown[]];
}>();

const { ensureGenerationHistory, restoreGenerationHistory } = useAPI();
const { replaceNodeData } = useGraphActions();
const chatStore = useChatStore();
const modelStore = useModelStore();
const canvasSaveStore = useCanvasSaveStore();
const settingsStore = useSettingsStore();
const { error } = useToast();
const { generationHistorySettings } = storeToRefs(settingsStore);

const isOpen = ref(false);
const isLoading = ref(false);
const loadError = ref<string | null>(null);
const entries = ref<GenerationHistoryEntry[]>([]);
const restoringId = ref<string | null>(null);
const triggerRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const panelStyle = ref<Record<string, string>>({});

const TELEPORTED_PANEL_WIDTH = 320;
const TELEPORTED_PANEL_FALLBACK_HEIGHT = 400;
const TELEPORTED_PANEL_OFFSET = 8;
const VIEWPORT_PADDING = 8;

let transformPaneObserver: MutationObserver | null = null;
let triggerResizeObserver: ResizeObserver | null = null;

const canLoad = computed(() => Boolean(props.graphId && props.nodeId));

const getTransformationPaneZoom = () => {
    const transformationPane = triggerRef.value?.closest('.vue-flow__transformationpane');

    if (!(transformationPane instanceof HTMLElement)) {
        return 1;
    }

    const transform = window.getComputedStyle(transformationPane).transform;

    if (!transform || transform === 'none') {
        return 1;
    }

    try {
        const matrix = new DOMMatrixReadOnly(transform);
        return Math.hypot(matrix.a, matrix.b) || 1;
    } catch {
        return 1;
    }
};

const updatePanelPosition = () => {
    if (!isOpen.value || !triggerRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    const zoom = getTransformationPaneZoom();
    const scaledPanelWidth = TELEPORTED_PANEL_WIDTH * zoom;
    const scaledPanelHeight =
        (panelRef.value?.offsetHeight ?? TELEPORTED_PANEL_FALLBACK_HEIGHT) * zoom;
    const scaledOffset = TELEPORTED_PANEL_OFFSET * zoom;
    const left = Math.min(
        Math.max(VIEWPORT_PADDING, triggerRect.right - scaledPanelWidth),
        window.innerWidth - scaledPanelWidth - VIEWPORT_PADDING,
    );
    const top =
        props.panelPosition === 'above'
            ? Math.max(VIEWPORT_PADDING, triggerRect.top - scaledPanelHeight - scaledOffset)
            : Math.min(
                  window.innerHeight - scaledPanelHeight - VIEWPORT_PADDING,
                  triggerRect.bottom + scaledOffset,
              );

    panelStyle.value = {
        left: `${left}px`,
        top: `${top}px`,
        width: `${TELEPORTED_PANEL_WIDTH}px`,
        transform: `scale(${zoom})`,
        transformOrigin: 'top left',
    };
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        closePopover();
    }
};

const clearPositionTracking = () => {
    transformPaneObserver?.disconnect();
    transformPaneObserver = null;

    triggerResizeObserver?.disconnect();
    triggerResizeObserver = null;

    window.removeEventListener('resize', updatePanelPosition);
    window.removeEventListener('scroll', updatePanelPosition, true);
    document.removeEventListener('pointerdown', handleOutsidePointerDown, true);
    document.removeEventListener('keydown', handleKeyDown, true);
};

const closePopover = () => {
    if (!isOpen.value) return;

    isOpen.value = false;
    clearPositionTracking();
};

const handleOutsidePointerDown = (event: PointerEvent) => {
    const target = event.target;

    if (!(target instanceof Node)) {
        return;
    }

    if (triggerRef.value?.contains(target) || panelRef.value?.contains(target)) {
        return;
    }

    closePopover();
};

const startPositionTracking = async () => {
    clearPositionTracking();
    await nextTick();
    updatePanelPosition();

    const transformationPane = triggerRef.value?.closest('.vue-flow__transformationpane');

    if (transformationPane instanceof HTMLElement) {
        transformPaneObserver = new MutationObserver(updatePanelPosition);
        transformPaneObserver.observe(transformationPane, {
            attributes: true,
            attributeFilter: ['style'],
        });
    }

    if (triggerRef.value) {
        triggerResizeObserver = new ResizeObserver(updatePanelPosition);
        triggerResizeObserver.observe(triggerRef.value);
    }

    window.addEventListener('resize', updatePanelPosition);
    window.addEventListener('scroll', updatePanelPosition, true);
    document.addEventListener('pointerdown', handleOutsidePointerDown, true);
    document.addEventListener('keydown', handleKeyDown, true);
};

const formatDate = (value: string) => {
    return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(value));
};

const formatRelativeTime = (value: string) => {
    const date = new Date(value);
    const diffMs = Date.now() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(date);
};

const formatModelLabel = (model: string | null) => {
    if (!model) return 'Unknown model';
    return model.split('/').pop() ?? model;
};

const getModelIcon = (model: string | null): string | null => {
    if (!model) return null;
    const found = modelStore.models.find((m) => m.id === model);
    return found?.icon ?? null;
};

const getToolIcon = (toolName: string): string => {
    const tool = TOOLS.find((t) => t.type === toolName);
    return tool?.icon ?? 'MdiWrenchOutline';
};

const getToolLabel = (toolName: string): string => {
    const tool = TOOLS.find((t) => t.type === toolName);
    return tool?.name ?? toolName;
};

const loadHistory = async () => {
    if (!canLoad.value || isLoading.value) return;

    isLoading.value = true;
    loadError.value = null;
    try {
        await canvasSaveStore.ensureGraphSaved();
        entries.value = await ensureGenerationHistory(props.graphId, props.nodeId as string);
    } catch (err) {
        console.error('Failed to load generation history:', err);
        loadError.value = 'Could not load history.';
    } finally {
        isLoading.value = false;
        await nextTick();
        updatePanelPosition();
    }
};

const toggleOpen = async () => {
    if (!canLoad.value) return;

    if (isOpen.value) {
        closePopover();
        return;
    }

    isOpen.value = true;
    await startPositionTracking();

    if (isOpen.value) {
        await loadHistory();
    }
};

const markEntryActive = (entryId: string) => {
    entries.value = entries.value.map((entry) => ({
        ...entry,
        is_active: entry.id === entryId,
    }));
};

const restoreEntry = async (entry: GenerationHistoryEntry) => {
    if (!canLoad.value || entry.is_active || restoringId.value) return;

    restoringId.value = entry.id;
    try {
        const restored = await restoreGenerationHistory(
            props.graphId,
            props.nodeId as string,
            entry.id,
        );
        replaceNodeData(props.graphId, props.nodeId as string, restored.node_data);
        emit('restored', restored.node_data);

        if (props.refreshChatOnRestore && chatStore.openChatId === props.nodeId) {
            await chatStore.refreshChat(props.graphId, props.nodeId as string);
        }

        if (generationHistorySettings.value.close_modal_on_restore) {
            closePopover();
        } else {
            markEntryActive(entry.id);
        }
    } catch (err) {
        console.error('Failed to restore generation history:', err);
        error('Could not restore this generation.', { title: 'History' });
    } finally {
        restoringId.value = null;
    }
};

onUnmounted(() => {
    clearPositionTracking();
});
</script>

<template>
    <div v-if="canLoad" class="nodrag relative" @click.stop @dblclick.stop>
        <button
            ref="triggerRef"
            type="button"
            title="Generation history"
            class="flex items-center justify-center rounded-lg p-1 transition-colors duration-200
                ease-in-out"
            :class="buttonClass"
            @click="toggleOpen"
        >
            <UiIcon name="MaterialSymbolsHistory" :class="iconClass" />
        </button>

        <Teleport to="body">
            <Transition
                enter-active-class="transition-opacity transition-transform duration-150 ease-out"
                enter-from-class="opacity-0 translate-y-1"
                enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition-opacity transition-transform duration-100 ease-in"
                leave-from-class="opacity-100 translate-y-0"
                leave-to-class="opacity-0 translate-y-1"
            >
                <div
                    v-if="isOpen"
                    ref="panelRef"
                    class="ui-generation-history-panel text-stone-gray fixed z-[10000] flex flex-col
                        overflow-hidden rounded-2xl border shadow-2xl"
                    :class="panelClass"
                    :style="panelStyle"
                    @click.stop
                    @dblclick.stop
                    @mousedown.stop
                    @pointerdown.stop
                    @wheel.stop
                >
                    <!-- Header -->
                    <header
                        class="border-stone-gray/10 flex items-center justify-between gap-2 border-b
                            px-3 py-2"
                    >
                        <div class="flex items-center gap-1.5">
                            <div
                                class="bg-olive-grove/15 text-olive-grove flex h-6 w-6 items-center
                                    justify-center rounded-md"
                            >
                                <UiIcon name="MaterialSymbolsHistory" class="h-3.5 w-3.5" />
                            </div>
                            <p class="text-soft-silk text-xs font-bold tracking-tight">History</p>
                            <span
                                v-if="!isLoading && !loadError"
                                class="bg-stone-gray/10 text-stone-gray/60 rounded-full px-1.5
                                    py-0.5 text-[9px] font-bold tabular-nums"
                            >
                                {{ entries.length }}
                            </span>
                        </div>
                        <button
                            type="button"
                            title="Refresh history"
                            class="hover:bg-anthracite/70 text-stone-gray/60 rounded-md p-1
                                transition-colors duration-150 disabled:opacity-40"
                            :disabled="isLoading"
                            @click="loadHistory"
                        >
                            <UiIcon
                                name="MaterialSymbolsRefreshRounded"
                                class="h-3.5 w-3.5"
                                :class="{ 'animate-spin': isLoading }"
                            />
                        </button>
                    </header>

                    <!-- Loading state -->
                    <div
                        v-if="isLoading"
                        class="flex flex-col items-center justify-center gap-2 px-6 py-8
                            select-none"
                    >
                        <UiIcon
                            name="MaterialSymbolsProgressActivity"
                            class="text-stone-gray/50 h-4 w-4 animate-spin"
                        />
                        <p class="text-stone-gray/50 text-[11px] font-medium">Loading history...</p>
                    </div>

                    <!-- Error state -->
                    <div
                        v-else-if="loadError"
                        class="flex flex-col items-center justify-center gap-2 px-6 py-8
                            text-center select-none"
                    >
                        <div
                            class="border-ember-glow/20 bg-ember-glow/10 text-ember-glow/70 flex h-9
                                w-9 items-center justify-center rounded-lg border"
                        >
                            <UiIcon name="MaterialSymbolsErrorCircleRounded" class="h-4 w-4" />
                        </div>
                        <p class="text-ember-glow/80 text-[11px] font-medium">{{ loadError }}</p>
                    </div>

                    <!-- Empty state -->
                    <div
                        v-else-if="entries.length === 0"
                        class="flex flex-col items-center justify-center gap-2.5 px-6 py-8
                            text-center select-none"
                    >
                        <div
                            class="border-stone-gray/15 bg-anthracite/50 relative flex h-10 w-10
                                items-center justify-center rounded-xl border"
                        >
                            <UiIcon name="MaterialSymbolsHistory" class="text-stone-gray/40 h-5 w-5" />
                            <span
                                aria-hidden="true"
                                class="bg-olive-grove/60 absolute -top-1 -right-1 h-1.5 w-1.5
                                    rounded-full"
                            />
                        </div>
                        <div class="flex flex-col gap-0.5">
                            <p class="text-soft-silk/90 text-xs font-semibold">No history yet</p>
                            <p class="text-stone-gray/60 text-[11px]">
                                Completed generations will appear here.
                            </p>
                        </div>
                    </div>

                    <!-- Entry list -->
                    <div
                        v-else
                        class="custom_scroll nowheel min-h-0 max-h-[20rem] space-y-0.5
                            overflow-y-auto p-1.5"
                        @wheel.stop
                    >
                        <button
                            v-for="entry in entries"
                            :key="entry.id"
                            type="button"
                            class="group/entry relative w-full overflow-hidden rounded-lg px-2.5 py-2
                                pl-3.5 text-left transition-all duration-150"
                            :class="
                                entry.is_active
                                    ? 'bg-olive-grove/12 ring-olive-grove/30 ring-1'
                                    : 'hover:bg-anthracite/60 ring-transparent ring-1'
                            "
                            :disabled="entry.is_active || restoringId !== null"
                            :title="
                                entry.is_active ? 'Currently active' : 'Click to restore this generation'
                            "
                            @click="restoreEntry(entry)"
                        >
                            <!-- Left accent rail -->
                            <span
                                aria-hidden="true"
                                class="absolute inset-y-1.5 left-0 w-[2.5px] rounded-full
                                    transition-colors duration-150"
                                :class="
                                    entry.is_active
                                        ? 'bg-olive-grove'
                                        : 'bg-transparent group-hover/entry:bg-stone-gray/30'
                                "
                            />

                            <!-- Top row: time + status -->
                            <div class="mb-1 flex items-center justify-between gap-2">
                                <span
                                    class="text-soft-silk/90 text-[11px] font-bold tabular-nums"
                                    :title="formatDate(entry.created_at)"
                                >
                                    {{ formatRelativeTime(entry.created_at) }}
                                </span>

                                <span
                                    v-if="entry.is_active"
                                    class="bg-olive-grove/20 text-olive-grove rounded-full px-1.5
                                        py-0.5 text-[8px] font-bold uppercase tracking-[0.1em]"
                                >
                                    Active
                                </span>
                                <span
                                    v-else-if="restoringId === entry.id"
                                    class="text-stone-gray/60 flex items-center gap-1 text-[10px]
                                        font-medium"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsProgressActivity"
                                        class="h-3 w-3 animate-spin"
                                    />
                                    Restoring
                                </span>
                                <UiIcon
                                    v-else
                                    name="MaterialSymbolsRestartAltRounded"
                                    class="text-stone-gray/0 group-hover/entry:text-stone-gray/60
                                        h-3 w-3 transition-colors duration-150"
                                />
                            </div>

                            <!-- Model + tools row -->
                            <div class="mb-1 flex flex-wrap items-center gap-x-1.5 gap-y-1">
                                <span class="flex min-w-0 items-center gap-1">
                                    <UiIcon
                                        v-if="getModelIcon(entry.model)"
                                        :name="`models/${getModelIcon(entry.model)}`"
                                        class="text-stone-gray/60 h-3.5 w-3.5 shrink-0"
                                    />
                                    <span
                                        class="text-stone-gray/80 truncate text-[11px] font-semibold"
                                    >
                                        {{ formatModelLabel(entry.model) }}
                                    </span>
                                </span>
                                <span
                                    v-if="entry.selected_tools.length"
                                    aria-hidden="true"
                                    class="text-stone-gray/20"
                                    >·</span
                                >
                                <div
                                    v-if="entry.selected_tools.length"
                                    class="flex items-center gap-1"
                                >
                                    <UiIcon
                                        v-for="tool in entry.selected_tools"
                                        :key="tool"
                                        :name="getToolIcon(tool)"
                                        class="text-stone-gray/50 h-3.5 w-3.5"
                                        :title="getToolLabel(tool)"
                                    />
                                </div>
                                <span
                                    v-else
                                    class="text-stone-gray/40 text-[10px] font-medium"
                                    >No tools</span
                                >
                            </div>

                            <!-- Preview text -->
                            <p
                                class="text-stone-gray/75 line-clamp-2 text-[11px] leading-snug
                                    break-words"
                            >
                                {{ entry.preview }}
                            </p>
                        </button>
                    </div>

                    <!-- Footer: keyboard hints -->
                    <footer
                        class="border-stone-gray/10 text-stone-gray/50 flex items-center gap-3
                            border-t px-3 py-1.5 text-[10px]"
                    >
                        <span class="flex items-center gap-1.5">
                            <kbd
                                class="border-stone-gray/20 bg-anthracite/60 text-soft-silk/80 inline-flex
                                    items-center justify-center rounded border px-1.5 py-0.5 pt-1
                                    font-mono text-[9px] leading-none font-bold"
                                >ESC</kbd
                            >
                            <span class="tracking-wide uppercase">close</span>
                        </span>
                        <span class="flex items-center gap-1.5">
                            <UiIcon name="MaterialSymbolsRestartAltRounded" class="h-3 w-3" />
                            <span class="tracking-wide uppercase">click to restore</span>
                        </span>
                    </footer>
                </div>
            </Transition>
        </Teleport>
    </div>
</template>

<style scoped>
.ui-generation-history-panel {
    background:
        radial-gradient(
            120% 80% at 0% 0%,
            color-mix(in oklab, var(--color-olive-grove) 7%, transparent) 0%,
            transparent 55%
        ),
        linear-gradient(
            180deg,
            color-mix(in oklab, var(--color-obsidian) 85%, transparent) 0%,
            color-mix(in oklab, var(--color-obsidian) 75%, transparent) 100%
        );
    border-color: color-mix(in oklab, var(--color-stone-gray) 18%, transparent);
    box-shadow:
        0 1px 0 0 color-mix(in oklab, var(--color-soft-silk) 6%, transparent) inset,
        0 0 0 1px color-mix(in oklab, var(--color-obsidian) 60%, transparent),
        0 30px 60px -20px rgba(0, 0, 0, 0.55),
        0 10px 20px -10px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    font-variant-numeric: tabular-nums;
}

.ui-generation-history-panel::before {
    content: '';
    position: absolute;
    inset: 0;
    pointer-events: none;
    background-image: radial-gradient(
        circle at 1px 1px,
        color-mix(in oklab, var(--color-soft-silk) 4%, transparent) 1px,
        transparent 0
    );
    background-size: 14px 14px;
    mix-blend-mode: overlay;
    opacity: 0.35;
}
</style>
