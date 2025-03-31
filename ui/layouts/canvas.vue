<script lang="ts" setup>
import { Background } from '@vue-flow/background';
</script>

<template>
    <div class="relative flex h-full w-full items-center justify-center">
        <client-only>
            <Background pattern-color="var(--color-stone-gray)" :gap="16" />
        </client-only>

        <slot />

        <UiSidebarHistory />
        <UiGraphSidebarSelector />
    </div>
</template>

<style scoped></style>
