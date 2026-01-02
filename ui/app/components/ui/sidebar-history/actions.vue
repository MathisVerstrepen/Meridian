<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';
import type { Workspace } from '@/composables/useAPI';

const props = defineProps({
    graph: {
        type: Object as PropType<Graph>,
        required: true,
    },
    currentGraphId: {
        type: String,
        default: '',
    },
    folders: {
        type: Array as PropType<Folder[]>,
        default: () => [],
    },
    workspaces: {
        type: Array as PropType<Workspace[]>,
        default: () => [],
    },
});

const emit = defineEmits<{
    (e: 'rename' | 'download' | 'pin', graphId: string): void;
    (e: 'delete', graphId: string, graphName: string): void;
    (e: 'move', graphId: string, folderId: string | null, workspaceId: string | null): void;
    (e: 'regenerateTitle', graphId: string, strategy: 'first' | 'all'): void;
}>();

const moveItems = computed(() => {
    const items = [];

    // Option to remove from folder
    if (props.graph.folder_id) {
        items.push({
            label: 'Remove from Folder',
            action: () => emit('move', props.graph.id, null, null),
            icon: 'MdiFolderRemoveOutline',
        });
    }

    // Folders in current workspace
    if (props.folders.length > 0) {
        items.push({
            label: 'Folders',
            isHeader: true,
        });
        props.folders.forEach((folder) => {
            if (props.graph.folder_id !== folder.id) {
                items.push({
                    label: folder.name,
                    action: () => emit('move', props.graph.id, folder.id, null),
                });
            }
        });
    }

    // Workspaces
    if (props.workspaces && props.workspaces.length > 1) {
        // Divider
        if (items.length > 0) {
            items.push({ label: 'Workspaces', isHeader: true });
        }

        props.workspaces.forEach((ws) => {
            if (props.graph.workspace_id !== ws.id) {
                items.push({
                    label: ws.name,
                    action: () => emit('move', props.graph.id, null, ws.id),
                    icon: 'MdiBriefcaseOutline',
                });
            }
        });
    }

    return items;
});

const regenerateTitleItems = [
    {
        label: 'First Node',
        action: () => emit('regenerateTitle', props.graph.id, 'first'),
        icon: 'MaterialSymbolsFirstPageRounded',
    },
    {
        label: 'All Nodes',
        action: () => emit('regenerateTitle', props.graph.id, 'all'),
        icon: 'MaterialSymbolsSelectAllRounded',
    },
];

const openUpwards = ref(false);

const calculatePosition = (event: MouseEvent) => {
    const button = event.currentTarget as HTMLElement;
    const rect = button.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    openUpwards.value = spaceBelow < 300;
};
</script>

<template>
    <HeadlessMenu as="div" class="relative h-full shrink-0 text-left">
        <HeadlessMenuButton
            class="flex h-full w-6 items-center justify-center rounded-lg py-1 transition-colors
                duration-200 ease-in-out"
            :class="{
                'text-stone-gray hover:bg-stone-gray/20 hover:text-white':
                    graph.id === currentGraphId,
                [`dark:text-obsidian dark:hover:bg-obsidian/20 text-stone-gray
                hover:bg-stone-gray/20 hover:text-soft-silk dark:hover:text-black`]:
                    graph.id !== currentGraphId,
            }"
            @click.stop="calculatePosition"
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
                class="dark:bg-stone-gray bg-anthracite dark:ring-anthracite/50 ring-stone-gray/10
                    absolute right-0 z-20 w-48 overflow-visible rounded-md p-1 shadow-lg ring-2
                    backdrop-blur-3xl focus:outline-none"
                :class="[
                    openUpwards ? 'bottom-full mb-2 origin-bottom-right' : 'mt-2 origin-top-right',
                ]"
            >
                <!-- Move to Folder/Workspace Submenu -->
                <UiSidebarHistorySubmenu
                    title="Move to..."
                    icon="MdiFolderOutline"
                    :items="moveItems"
                />

                <!-- Regenerate Title Submenu -->
                <UiSidebarHistorySubmenu
                    title="Regenerate Title"
                    icon="MaterialSymbolsRefreshRounded"
                    :items="regenerateTitleItems"
                />

                <div class="mx-2 my-1 border-t border-white/10 dark:border-black/10"></div>

                <HeadlessMenuItem>
                    <button
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full
                            items-center rounded-md px-4 py-2 text-sm font-bold transition-colors
                            duration-200 ease-in-out"
                        title="Rename Graph"
                        @click.stop="emit('rename', graph.id)"
                    >
                        <UiIcon
                            name="MdiRename"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        Rename
                    </button>
                </HeadlessMenuItem>

                <HeadlessMenuItem>
                    <button
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full
                            items-center rounded-md px-4 py-2 text-sm font-bold transition-colors
                            duration-200 ease-in-out"
                        :title="graph.pinned ? 'Unpin Graph' : 'Pin Graph'"
                        @click.stop="emit('pin', graph.id)"
                    >
                        <UiIcon
                            v-if="!graph.pinned"
                            name="MajesticonsPin"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        <UiIcon
                            v-else
                            name="MajesticonsUnpin"
                            class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4"
                            aria-hidden="true"
                        />
                        {{ graph.pinned ? 'Unpin' : 'Pin' }}
                    </button>
                </HeadlessMenuItem>
                <HeadlessMenuItem>
                    <button
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full
                            items-center rounded-md px-4 py-2 text-sm font-bold transition-colors
                            duration-200 ease-in-out"
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
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex w-full
                            items-center rounded-md px-4 py-2 text-sm font-bold transition-colors
                            duration-200 ease-in-out"
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
