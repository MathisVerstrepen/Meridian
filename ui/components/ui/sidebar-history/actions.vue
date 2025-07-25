<script lang="ts" setup>
defineProps({
    graph: {
        type: Object,
        required: true,
    },
    currentGraphId: {
        type: String,
    },
});

const emit = defineEmits<{
    (e: 'rename', graphId: string): void;
    (e: 'delete', graphId: string, graphName: string): void;
    (e: 'download', graphId: string): void;
}>();
</script>

<template>
    <HeadlessMenu as="div" class="relative h-full shrink-0 text-left">
        <HeadlessMenuButton
            @click.stop
            class="flex h-full w-6 items-center justify-center rounded-lg transition-colors duration-200 ease-in-out"
            :class="{
                'text-stone-gray hover:bg-stone-gray/20 hover:text-white':
                    graph.id === currentGraphId,
                [`dark:text-obsidian dark:hover:bg-obsidian/20 text-stone-gray hover:bg-stone-gray/20
                hover:text-soft-silk dark:hover:text-black`]: graph.id !== currentGraphId,
            }"
        >
            <UiIcon name="Fa6SolidEllipsisVertical" class="h-5 w-5" aria-hidden="true" />
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
                class="dark:bg-stone-gray bg-anthracite dark:ring-anthracite/50 ring-stone-gray/10 absolute right-0 z-20
                    mt-2 w-48 origin-top-right rounded-md p-1 shadow-lg ring-2 backdrop-blur-3xl focus:outline-none"
            >
                <HeadlessMenuItem>
                    <button
                        @click.stop="emit('rename', graph.id)"
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                    >
                        <UiIcon
                            name="MaterialSymbolsEditRounded"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Rename
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        @click.stop="emit('download', graph.id)"
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                    >
                        <UiIcon
                            name="UilDownloadAlt"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Download
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        @click.stop="emit('delete', graph.id, graph.name)"
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full items-center rounded-md px-4 py-2
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
