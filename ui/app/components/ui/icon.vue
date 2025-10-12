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

watchEffect(loadSvg);
</script>

<template>
    <span
        v-if="svgContent"
        aria-hidden="true"
        role="img"
        focusable="false"
        class="icon-wrapper inline-block align-middle"
        v-html="svgContent" 
    />
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
