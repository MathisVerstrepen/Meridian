<script setup lang="ts">
interface Props {
    name: string;
}

const props = defineProps<Props>();

const svgImports = import.meta.glob('~/assets/icons/**/*.svg', {
    query: '?raw',
    import: 'default',
    eager: true,
});

const svgContent = ref<string | null>(null);

const loadSvg = () => {
    const path = `/assets/icons/${props.name}.svg`;

    if (svgImports[path]) {
        svgContent.value = svgImports[path] as string;
    } else {
        console.warn(
            `[IconComponent] Icon "${props.name}" not found at path "${path}". Available icons:`,
            Object.keys(svgImports),
        );
        svgContent.value = null;
    }
};

watchEffect(loadSvg);

const svgAttrs = computed(() => ({
    'aria-hidden': 'true',
    role: 'img',
    focusable: 'false',
}));
</script>

<template>
    <span
        v-if="svgContent"
        v-html="svgContent"
        :class="$attrs.class"
        :style="$attrs.style"
        v-bind="svgAttrs"
        class="icon-wrapper inline-block"
    ></span>
    <span v-else class="inline-block text-red-500" title="Icon not found">⚠️</span>
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
