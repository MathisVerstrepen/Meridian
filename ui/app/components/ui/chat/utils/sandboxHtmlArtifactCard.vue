<script setup lang="ts">
const emit = defineEmits<{
    sendPrompt: [text: string];
}>();

const props = withDefaults(
    defineProps<{
        fileId: string;
        title: string;
        filename?: string;
        embedUrl: string;
    }>(),
    {
        filename: '',
    },
);

const settingsStore = useSettingsStore();
const { appearanceSettings } = storeToRefs(settingsStore);

const previewFrameRef = ref<HTMLIFrameElement | null>(null);
const modalFrameRef = ref<HTMLIFrameElement | null>(null);
const isPreviewLoading = ref(true);
const isModalLoading = ref(true);
const isExpanded = ref(false);
const previewHeight = ref(500);

const HTML_ARTIFACT_CONFIG_TYPE = 'meridian:html-artifact:config';
const HTML_ARTIFACT_PROMPT_TYPE = 'meridian:html-artifact:prompt';

const collectThemeCssVars = (): string => {
    if (!import.meta.client) {
        return '';
    }

    const variableMap = new Map<string, string>();
    for (const target of [document.documentElement, document.body]) {
        const styles = getComputedStyle(target);
        for (let index = 0; index < styles.length; index += 1) {
            const property = styles.item(index);
            if (!property.startsWith('--')) {
                continue;
            }

            const value = styles.getPropertyValue(property).trim();
            if (value) {
                variableMap.set(property, value);
            }
        }
    }

    return Array.from(variableMap.entries())
        .map(([key, value]) => `${key}:${value};`)
        .join('');
};

const postThemeConfig = (frame: HTMLIFrameElement | null) => {
    frame?.contentWindow?.postMessage(
        {
            type: HTML_ARTIFACT_CONFIG_TYPE,
            themeCssVars: collectThemeCssVars(),
        },
        '*',
    );
};

const handlePreviewLoad = (event: Event) => {
    isPreviewLoading.value = false;
    postThemeConfig((event.currentTarget as HTMLIFrameElement | null) || previewFrameRef.value);
};

const handleModalLoad = (event: Event) => {
    isModalLoading.value = false;
    postThemeConfig((event.currentTarget as HTMLIFrameElement | null) || modalFrameRef.value);
};

const openExpandedPreview = () => {
    isExpanded.value = true;
    isModalLoading.value = true;
};

const closeExpandedPreview = () => {
    isExpanded.value = false;
};

const handleWindowMessage = (event: MessageEvent) => {
    const previewWindow = previewFrameRef.value?.contentWindow;
    const modalWindow = modalFrameRef.value?.contentWindow;
    if (event.source !== previewWindow && event.source !== modalWindow) {
        return;
    }

    const payload = event.data;
    if (!payload || payload.type !== HTML_ARTIFACT_PROMPT_TYPE || typeof payload.text !== 'string') {
        return;
    }

    const prompt = payload.text.trim().slice(0, 2000);
    if (prompt) {
        emit('sendPrompt', prompt);
    }
};

watch(
    () => [appearanceSettings.value.theme, appearanceSettings.value.accentColor],
    () => {
        postThemeConfig(previewFrameRef.value);
        postThemeConfig(modalFrameRef.value);
    },
    { immediate: true },
);

watch(
    () => props.fileId,
    () => {
        isPreviewLoading.value = true;
        isModalLoading.value = true;
    },
);

onMounted(() => {
    window.addEventListener('message', handleWindowMessage);
});

onBeforeUnmount(() => {
    window.removeEventListener('message', handleWindowMessage);
});
</script>

<template>
    <figure class="bg-obsidian border-soft-silk/10 my-4 overflow-hidden rounded-xl border">
        <div class="border-soft-silk/10 relative w-full border-b">
            <div
                class="relative flex max-h-[80vh] min-h-[300px] w-full resize-y justify-center
                    overflow-hidden"
                :style="{ height: `${previewHeight}px` }"
            >
                <iframe
                    ref="previewFrameRef"
                    :src="props.embedUrl"
                    :title="props.title"
                    class="hide-scrollbar block h-full w-full border-0 bg-transparent"
                    loading="lazy"
                    referrerpolicy="no-referrer"
                    sandbox="allow-scripts allow-downloads"
                    @load="handlePreviewLoad"
                />

                <div
                    v-if="isPreviewLoading"
                    class="bg-obsidian/70 absolute inset-0 flex items-center justify-center"
                >
                    <div
                        class="border-soft-silk/50 h-8 w-8 animate-spin rounded-full border-4
                            border-t-transparent"
                    />
                </div>
            </div>
        </div>

        <figcaption class="text-soft-silk/80 mt-0! flex flex-wrap items-center gap-3 px-4 py-3">
            <div class="flex min-w-0 flex-1 items-center gap-3">
                <span class="mt-px flex size-5 shrink-0 items-center justify-center rounded">
                    <UiIcon name="MaterialSymbolsBarChartRounded" class="h-4 w-4" />
                </span>
                <div class="min-w-0 flex-1">
                    <div class="truncate text-[13px] leading-normal">{{ props.title }}</div>
                    <div class="text-soft-silk/45 text-[11px]">
                        Responsive container • Resize vertically
                    </div>
                </div>
            </div>

            <div class="flex flex-wrap items-center gap-2">
                <button
                    class="border-stone-gray/15 bg-stone-gray/10 text-soft-silk
                        hover:bg-stone-gray/20 inline-flex cursor-pointer items-center gap-2
                        rounded-lg border px-3 py-2 text-sm transition-colors duration-200"
                    type="button"
                    @click="openExpandedPreview"
                >
                    <UiIcon name="MaterialSymbolsExpandContentRounded" class="h-4 w-4" />
                    <span>Expand</span>
                </button>

                <a
                    :href="props.embedUrl"
                    class="border-stone-gray/15 bg-stone-gray/10 text-soft-silk
                        hover:bg-stone-gray/20 inline-flex items-center gap-2 rounded-lg border px-3
                        py-2 text-sm transition-colors duration-200"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <UiIcon name="MaterialSymbolsOpenInNewRounded" class="h-4 w-4" />
                    <span>Open</span>
                </a>

                <UiChatUtilsSandboxArtifactDownload
                    compact
                    :file-id="props.fileId"
                    :filename="props.filename || props.title"
                    label="Download"
                />
            </div>
        </figcaption>
    </figure>

    <Teleport to="body">
        <div
            v-if="isExpanded"
            class="bg-obsidian/85 fixed inset-0 z-[9999] flex items-center justify-center p-4
                backdrop-blur-md"
            @click.self="closeExpandedPreview"
        >
            <div
                class="bg-anthracite border-stone-gray/15 text-soft-silk flex h-[92vh] w-[96vw]
                    max-w-7xl flex-col overflow-hidden rounded-2xl border shadow-2xl"
            >
                <div class="border-stone-gray/10 flex items-center gap-3 border-b px-4 py-3">
                    <div class="min-w-0 flex-1">
                        <div class="truncate text-sm font-semibold">{{ props.title }}</div>
                        <div class="text-stone-gray text-xs">Full-size interactive preview</div>
                    </div>

                    <a
                        :href="props.embedUrl"
                        class="border-stone-gray/15 bg-stone-gray/10 text-soft-silk
                            hover:bg-stone-gray/20 inline-flex items-center gap-2 rounded-lg border
                            px-3 py-2 text-sm transition-colors duration-200"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        <UiIcon name="MaterialSymbolsOpenInNewRounded" class="h-4 w-4" />
                        <span>Open</span>
                    </a>

                    <UiChatUtilsSandboxArtifactDownload
                        compact
                        :file-id="props.fileId"
                        :filename="props.filename || props.title"
                        label="Download"
                    />

                    <button
                        class="hover:bg-stone-gray/10 flex items-center justify-center rounded-full
                            p-2 transition-colors duration-200"
                        type="button"
                        @click="closeExpandedPreview"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                    </button>
                </div>

                <div class="relative min-h-0 flex-1 bg-[#f7f7f7] p-4">
                    <iframe
                        ref="modalFrameRef"
                        :src="props.embedUrl"
                        :title="props.title"
                        class="block h-full w-full rounded-xl border-0 bg-white"
                        loading="lazy"
                        referrerpolicy="no-referrer"
                        sandbox="allow-scripts allow-downloads"
                        scrolling="no"
                        @load="handleModalLoad"
                    />

                    <div
                        v-if="isModalLoading"
                        class="bg-obsidian/70 absolute inset-4 flex items-center justify-center
                            rounded-xl"
                    >
                        <div
                            class="border-soft-silk/50 h-8 w-8 animate-spin rounded-full border-4
                                border-t-transparent"
                        />
                    </div>
                </div>
            </div>
        </div>
    </Teleport>
</template>
