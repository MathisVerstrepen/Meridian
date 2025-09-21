<script lang="ts" setup>
import type { Graph } from '@/types/graph';

defineProps({
    graph: {
        type: Object as PropType<Graph>,
        required: true,
    },
    currentGraphId: {
        type: String,
        default: '',
    },
});

const emit = defineEmits<{
    (e: 'rename' | 'download' | 'pin', graphId: string): void;
    (e: 'delete', graphId: string, graphName: string): void;
}>();
</script>

<template>
    <HeadlessMenu as="div" class="relative h-full shrink-0 text-left">
        <HeadlessMenuButton
            class="flex h-full w-6 items-center justify-center rounded-lg transition-colors duration-200 ease-in-out"
            :class="{
                'text-stone-gray hover:bg-stone-gray/20 hover:text-white':
                    graph.id === currentGraphId,
                [`dark:text-obsidian dark:hover:bg-obsidian/20 text-stone-gray hover:bg-stone-gray/20
                hover:text-soft-silk dark:hover:text-black`]: graph.id !== currentGraphId,
            }"
            @click.stop
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
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                        title="Rename Graph"
                        @click.stop="emit('rename', graph.id)"
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
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                        :title="graph.pinned ? 'Unpin Graph' : 'Pin Graph'"
                        @click.stop="emit('pin', graph.id)"
                    >
                        <UiIcon
                            name="MajesticonsPin"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        {{ graph.pinned ? 'Unpin' : 'Pin' }}
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                        title="Download Graph"
                        @click.stop="emit('download', graph.id)"
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
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full items-center rounded-md px-4 py-2
                            text-sm font-bold transition-colors duration-200 ease-in-out"
                        title="Delete Graph"
                        @click.stop="emit('delete', graph.id, graph.name)"
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
