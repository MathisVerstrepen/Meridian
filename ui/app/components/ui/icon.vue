<script setup lang="ts">
defineOptions({
    inheritAttrs: false,
});

interface Props {
    name: string;
}

const props = defineProps<Props>();
const attrs = useAttrs();

const svgImports = import.meta.glob(['~/assets/icons/**/*.svg', '!~/assets/icons/fileTree/**/*.svg'], {
    query: '?raw',
    import: 'default',
    eager: true,
});
const fileTreeIconImports = import.meta.glob('~/assets/icons/fileTree/**/*.svg', {
    query: '?raw',
    import: 'default',
});

const svgContent = ref<string | null>(null);
const isLoading = ref(false);
let loadRequestId = 0;

const loadSvg = async (name: string) => {
    const path = `/assets/icons/${name}.svg`;
    const requestId = ++loadRequestId;

    svgContent.value = null;
    isLoading.value = false;

    if (name.startsWith('fileTree/')) {
        const importedSvgUrl = fileTreeIconImports[path];

        if (!importedSvgUrl) {
            if (name) {
                console.warn(`[IconComponent] File tree icon "${name}" not found at path "${path}".`);
            }

            return;
        }

        isLoading.value = true;

        try {
            const resolvedSvgContent = await importedSvgUrl();

            if (requestId !== loadRequestId) {
                return;
            }

            if (typeof resolvedSvgContent === 'string') {
                svgContent.value = resolvedSvgContent;
            }
        } catch (error) {
            if (requestId !== loadRequestId) {
                return;
            }

            console.warn(`[IconComponent] Failed to load file tree icon "${name}" at path "${path}".`, error);
        } finally {
            if (requestId === loadRequestId) {
                isLoading.value = false;
            }
        }

        return;
    }

    const importedSvg = svgImports[path];

    if (typeof importedSvg === 'string') {
        svgContent.value = importedSvg;
    } else {
        if (props.name) {
            console.warn(
                `[IconComponent] Icon "${props.name}" not found at path "${path}". Available icons paths:`,
                Object.keys(svgImports),
            );
        }
        svgContent.value = null;
    }
};

watch(
    () => props.name,
    (name) => {
        void loadSvg(name);
    },
    { immediate: true },
);
</script>

<template>
    <span
        v-if="svgContent"
        v-bind="attrs"
        aria-hidden="true"
        role="img"
        focusable="false"
        class="icon-wrapper inline-block align-middle"
        v-html="svgContent"
    />
    <span
        v-else-if="isLoading"
        v-bind="attrs"
        aria-hidden="true"
        class="inline-block align-middle"
    />
    <span
        v-else
        v-bind="attrs"
        class="inline-block text-red-500"
        title="Icon not found"
    >
        ⚠️
    </span>
</template>

<style scoped>
.icon-wrapper :deep(svg) {
    width: 100%;
    height: 100%;
    fill: currentColor;
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>
