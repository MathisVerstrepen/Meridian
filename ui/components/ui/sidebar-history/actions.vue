<script lang="ts" setup>
import { Menu, MenuButton, MenuItems, MenuItem } from '@headlessui/vue';

defineProps({
    graph: {
        type: Object,
        required: true,
    },
    currentGraphId: {
        type: String,
    },
    renameGraph: {
        type: Function as PropType<(graphId: string) => Promise<void>>,
        required: true,
    },
    deleteGraph: {
        type: Function as PropType<(graphId: string) => Promise<void>>,
        required: true,
    },
});
</script>

<template>
    <Menu as="div" class="relative h-full flex-shrink-0 text-left">
        <MenuButton
            @click.stop
            class="flex h-full w-6 items-center justify-center rounded-lg transition-colors duration-200 ease-in-out"
            :class="{
                'text-soft-silk hover:bg-stone-gray/20 hover:text-white':
                    graph.id === currentGraphId,
                'text-obsidian hover:bg-obsidian/20 hover:text-black': graph.id !== currentGraphId,
            }"
        >
            <Icon name="fa6-solid:ellipsis-vertical" class="h-5 w-5" aria-hidden="true" />
        </MenuButton>

        <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 scale-95"
            enter-to-class="transform opacity-100 scale-100"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 scale-100"
            leave-to-class="transform opacity-0 scale-95"
        >
            <MenuItems
                class="bg-stone-gray ring-anthracite/50 absolute right-0 z-20 mt-2 w-48 origin-top-right rounded-md p-1
                    shadow-lg ring-2 focus:outline-none"
            >
                <MenuItem>
                    <button
                        @click.stop="() => renameGraph(graph.id)"
                        class="hover:bg-obsidian/25 text-obsidian flex w-full items-center rounded-md px-4 py-2 text-sm font-bold
                            transition-colors duration-200 ease-in-out"
                    >
                        <Icon
                            name="material-symbols:edit-rounded"
                            class="text-obsidian mr-2"
                            style="height: 1rem; width: 1rem"
                            aria-hidden="true"
                        />
                        Rename
                    </button>
                </MenuItem>
                <MenuItem>
                    <button
                        @click.stop="() => deleteGraph(graph.id)"
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                    >
                        <Icon
                            name="material-symbols:delete-rounded"
                            class="text-terracotta-clay mr-2"
                            style="height: 1rem; width: 1rem"
                            aria-hidden="true"
                        />
                        Delete
                    </button>
                </MenuItem>
            </MenuItems>
        </transition>
    </Menu>
</template>

<style scoped></style>
