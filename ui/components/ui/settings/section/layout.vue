<script lang="ts" setup></script>

<template>
    <div class="flex h-full w-full flex-col gap-8 px-10 py-1">
        <header>
            <h1 class="text-stone-gray text-3xl font-bold">
                <slot name="header"></slot>
            </h1>
        </header>
        <main>
            <slot></slot>
        </main>
    </div>
</template>

<style scoped></style>
