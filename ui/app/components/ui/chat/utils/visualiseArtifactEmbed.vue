<script setup lang="ts">
const emit = defineEmits<{
    sendPrompt: [text: string];
}>();

const props = defineProps<{
    fileId: string;
    embedUrl: string;
    caption?: string;
}>();

const settingsStore = useSettingsStore();
const { appearanceSettings } = storeToRefs(settingsStore);

const iframeRef = ref<HTMLIFrameElement | null>(null);
const iframeHeight = ref(220);
const isLoading = ref(true);

const VISUALISE_CONFIG_TYPE = 'meridian:visualise-artifact:config';
const VISUALISE_PROMPT_TYPE = 'meridian:visualise-artifact:prompt';
const VISUALISE_HEIGHT_TYPE = 'meridian:visualise-artifact:height';

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

const postThemeConfig = () => {
    iframeRef.value?.contentWindow?.postMessage(
        {
            type: VISUALISE_CONFIG_TYPE,
            themeCssVars: collectThemeCssVars(),
        },
        '*',
    );
};

const handleFrameLoad = () => {
    isLoading.value = false;
    postThemeConfig();
};

const handleWindowMessage = (event: MessageEvent) => {
    if (event.source !== iframeRef.value?.contentWindow) {
        return;
    }

    const payload = event.data;
    if (!payload || typeof payload.type !== 'string') {
        return;
    }

    console.log('Received message from visualise artifact iframe', payload);

    if (payload.type === VISUALISE_HEIGHT_TYPE && typeof payload.height === 'number') {
        iframeHeight.value = Math.max(120, Math.ceil(payload.height));
        return;
    }

    if (payload.type === VISUALISE_PROMPT_TYPE && typeof payload.text === 'string') {
        const prompt = payload.text.trim().slice(0, 2000);
        if (prompt) {
            emit('sendPrompt', prompt);
        }
    }
};

watch(
    () => [appearanceSettings.value.theme, appearanceSettings.value.accentColor],
    () => {
        postThemeConfig();
    },
    { immediate: true },
);

watch(
    () => props.fileId,
    () => {
        isLoading.value = true;
        iframeHeight.value = 220;
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
    <div class="my-4">
        <div class="relative w-full" :style="{ height: `${iframeHeight}px` }">
            <iframe
                ref="iframeRef"
                :src="props.embedUrl"
                :title="props.caption || 'Interactive visual'"
                class="block h-full w-full border-0 bg-transparent rounded-xl"
                loading="lazy"
                referrerpolicy="no-referrer"
                sandbox="allow-scripts allow-downloads"
                allowtransparency="true"
                @load="handleFrameLoad"
            />

            <div
                v-if="isLoading"
                class="bg-obsidian/10 absolute inset-0 flex items-center justify-center"
            >
                <div
                    class="border-soft-silk/40 h-7 w-7 animate-spin rounded-full border-4
                        border-t-transparent"
                />
            </div>
        </div>
    </div>
</template>
