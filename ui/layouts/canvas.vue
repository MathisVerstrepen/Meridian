<script lang="ts" setup></script>

<template>
    <div class="relative flex h-full w-full items-center justify-center">
        <slot />

        <UiSidebarHistory />
        <UiGraphSidebarSelector />
    </div>
</template>

<style scoped></style>
