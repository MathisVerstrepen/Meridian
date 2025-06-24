<script lang="ts" setup>
// --- Props ---
const props = defineProps<{
    uploads: Record<string, { status: 'uploading' | 'complete' | 'error' }>;
}>();

// --- Constants for styling ---
const COLORS = {
    UPLOADING: 'color-mix(in oklab, var(--color-stone-gray), 75% transparent)',
    COMPLETE: 'var(--color-terracotta-clay)',
    ERROR: 'rgb(220 38 38)',
    BACKGROUND: 'transparent',
};

// --- Computed ---
const gradientStyle = computed(() => {
    const uploadKeys = Object.keys(props.uploads);
    const total = uploadKeys.length;
    if (total === 0) return { backgroundImage: 'none' };

    const segmentAngle = 360 / total;
    let gradientParts: string[] = [];
    let currentAngle = 0;

    uploadKeys.forEach((key, index) => {
        const upload = props.uploads[key];
        const color =
            upload.status === 'complete'
                ? COLORS.COMPLETE
                : upload.status === 'error'
                  ? COLORS.ERROR
                  : COLORS.UPLOADING;

        const startAngle = currentAngle;
        const endAngle = currentAngle + segmentAngle;

        gradientParts.push(`${color} ${startAngle}deg ${endAngle}deg`);
        currentAngle = endAngle;
    });

    // Fallback for rounding errors to ensure the circle is complete
    if (total > 0 && currentAngle < 360) {
        const lastPart = gradientParts.pop()?.split(' ');
        if (lastPart) {
            lastPart[lastPart.length - 1] = '360deg';
            gradientParts.push(lastPart.join(' '));
        }
    }

    return {
        backgroundImage: `conic-gradient(${gradientParts.join(', ')})`,
    };
});
</script>

<template>
    <div class="progress-ring h-8 w-8 rounded-[50%]" :style="gradientStyle"></div>
</template>

<style scoped>
.progress-ring {
    mask: radial-gradient(transparent 50%, black 51%);
    -webkit-mask: radial-gradient(transparent 50%, black 51%);
}
</style>
