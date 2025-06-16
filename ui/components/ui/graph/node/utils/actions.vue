<script lang="ts" setup>
const emit = defineEmits(['update:deleteNode']);
</script>

<template>
    <HeadlessMenu as="div" class="relative h-full shrink-0 text-left">
        <HeadlessMenuButton
            @click.stop
            class="flex h-full w-6 items-center justify-center rounded-lg transition-colors duration-200 ease-in-out"
        >
            <UiIcon name="Fa6SolidEllipsisVertical" class="text-soft-silk h-5 w-5" aria-hidden="true" />
        </HeadlessMenuButton>

        <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 scale-95"
            enter-to-class="transform opacity-100 scale-100"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 scale-100"
            leave-to-class="transform opacity-0 scale-95"
        >
            <HeadlessMenuItems
                class="bg-stone-gray ring-anthracite/50 absolute right-0 z-20 mt-2 w-48 origin-top-right rounded-xl p-1
                    shadow-lg ring-2 focus:outline-none"
            >
                <HeadlessMenuItem>
                    <button
                        @click.stop="emit('update:deleteNode')"
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full items-center rounded-lg px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                    >
                        <UiIcon
                            name="MaterialSymbolsDeleteRounded"
                            class="text-terracotta-clay mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Delete
                    </button>
                </HeadlessMenuItem>
            </HeadlessMenuItems>
        </transition>
    </HeadlessMenu>
</template>

<style scoped></style>
