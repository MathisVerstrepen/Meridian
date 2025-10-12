<script lang="ts" setup>
defineProps<{
    routeGroupId: string;
    isLocked: boolean;
    isDefault: boolean;
}>();

const emit = defineEmits<{
    (e: 'rename' | 'delete' | 'duplicate' | 'default', routeGroupId: string): void;
}>();
</script>

<template>
    <HeadlessMenu as="div" class="relative h-full shrink-0 text-left">
        <HeadlessMenuButton
            class="text-soft-silk hover:bg-obsidian/20 mx-2 flex h-full w-6 items-center justify-center rounded-lg
                transition-colors duration-200 ease-in-out hover:text-white"
            @click.stop
        >
            <UiIcon
                name="Fa6SolidEllipsisVertical"
                class="text-obsidian h-4 w-4"
                aria-hidden="true"
            />
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
                class="dark:bg-stone-gray bg-anthracite ring-anthracite/50 absolute right-0 z-20 mt-2 w-48 origin-top-right
                    rounded-md p-1 shadow-lg ring-2 focus:outline-none"
            >
                <HeadlessMenuItem>
                    <button
                        v-if="routeGroupId"
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                            disabled:opacity-50"
                        :disabled="isLocked"
                        @click.stop="emit('rename', routeGroupId)"
                    >
                        <UiIcon
                            name="MaterialSymbolsEditRounded"
                            class="mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Rename
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        v-if="routeGroupId"
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                        @click.stop="emit('duplicate', routeGroupId)"
                    >
                        <UiIcon
                            name="MaterialSymbolsControlPointDuplicateOutlineRounded"
                            class="mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Duplicate
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        v-if="routeGroupId"
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                            disabled:opacity-50"
                        :disabled="isDefault"
                        @click.stop="emit('default', routeGroupId)"
                    >
                        <UiIcon
                            name="MaterialSymbolsCheckCircleOutlineRounded"
                            class="mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Set as Default
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        v-if="routeGroupId"
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                            disabled:opacity-50"
                        :disabled="isLocked"
                        @click.stop="emit('delete', routeGroupId)"
                    >
                        <UiIcon
                            name="MaterialSymbolsDeleteRounded"
                            class="mr-2 h-4 w-4"
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
