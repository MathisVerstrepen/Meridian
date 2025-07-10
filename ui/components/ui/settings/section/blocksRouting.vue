<script lang="ts" setup>
import type { Route, RouteGroup } from '@/types/settings';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { blockRoutingSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { generateId } = useUniqueId();

const editingRouteGroupId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());

// --- Core Logic ---
const addNewRouteGroup = () => {
    const newRouteGroup: RouteGroup = {
        id: generateId(),
        name: 'New Route Group',
        isLocked: false,
        isDefault: false,
        routes: [],
    };

    blockRoutingSettings.value.routeGroups.push(newRouteGroup);
};

const updateRoute = (id: string, updatedRoute: Route) => {
    const routeGroup = blockRoutingSettings.value.routeGroups.find((group) =>
        group.routes.some((route) => route.id === id),
    );

    if (!routeGroup) return;

    const routeIndex = routeGroup.routes.findIndex((route) => route.id === id);
    if (routeIndex !== -1) {
        routeGroup.routes[routeIndex] = updatedRoute;
    }
};

const deleteRoute = (id: string) => {
    for (const group of blockRoutingSettings.value.routeGroups) {
        const routeIndex = group.routes.findIndex((route) => route.id === id);
        if (routeIndex !== -1) {
            group.routes.splice(routeIndex, 1);
            break;
        }
    }
};

const deleteGroup = (routeGroupId: string) => {
    const groupIndex = blockRoutingSettings.value.routeGroups.findIndex(
        (g) => g.id === routeGroupId,
    );
    if (groupIndex !== -1) {
        if (window.confirm('Are you sure you want to delete this route group?')) {
            blockRoutingSettings.value.routeGroups.splice(groupIndex, 1);
        }
    }
};

const duplicateGroup = (routeGroupId: string) => {
    const groupIndex = blockRoutingSettings.value.routeGroups.findIndex(
        (g) => g.id === routeGroupId,
    );
    if (groupIndex !== -1) {
        const groupToDuplicate = blockRoutingSettings.value.routeGroups[groupIndex];
        const duplicatedRoutes = groupToDuplicate.routes.map((route) => ({
            ...route,
            id: generateId(),
        }));
        const duplicatedGroup = {
            ...groupToDuplicate,
            id: generateId(),
            name: `${groupToDuplicate.name} (copy)`,
            routes: duplicatedRoutes,
            isLocked: false,
            isDefault: false,
        };
        blockRoutingSettings.value.routeGroups.splice(groupIndex + 1, 0, duplicatedGroup);
    }
};

const setDefaultGroup = (routeGroupId: string) => {
    blockRoutingSettings.value.routeGroups.forEach((group) => {
        group.isDefault = group.id === routeGroupId;
    });
};

const handleStartRename = async (routeGroupId: string) => {
    const routeGroupToEdit = blockRoutingSettings.value.routeGroups.find(
        (g) => g.id === routeGroupId,
    );
    if (routeGroupToEdit) {
        editingRouteGroupId.value = routeGroupId;
        editInputValue.value = routeGroupToEdit.name;

        await nextTick();

        const inputElement = inputRefs.value.get(routeGroupId);
        if (inputElement) {
            inputElement.focus();
            inputElement.select();
        }
    }
};

const confirmRename = async () => {
    if (!editingRouteGroupId.value) return;

    const routeGroupIdToUpdate = editingRouteGroupId.value;
    const newName = editInputValue.value.trim();

    editingRouteGroupId.value = null;

    const originalRouteGroup = blockRoutingSettings.value.routeGroups.find(
        (g) => g.id === routeGroupIdToUpdate,
    );

    if (!newName || !originalRouteGroup || newName === originalRouteGroup.name) {
        editInputValue.value = '';
        return;
    }

    const routeGroupIndex = blockRoutingSettings.value.routeGroups.findIndex(
        (g) => g.id === routeGroupIdToUpdate,
    );
    if (routeGroupIndex !== -1) {
        blockRoutingSettings.value.routeGroups[routeGroupIndex].name = newName;
    }

    editInputValue.value = '';
};

const cancelRename = () => {
    editingRouteGroupId.value = null;
    editInputValue.value = '';
};

const addNewRoute = (routeGroupId: string) => {
    const routeGroup = blockRoutingSettings.value.routeGroups.find(
        (group) => group.id === routeGroupId,
    );
    if (!routeGroup) return;

    const newRoute: Route = {
        id: generateId(),
        name: 'New Route',
        description: 'This is a new route.',
        modelId: 'openai/gpt-4o',
        icon: 'routes/StreamlineChatBubbleTypingOvalSolid',
        customPrompt: '',
        overrideGlobalPrompt: false,
    };

    routeGroup.routes.unshift(newRoute);
};
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <HeadlessTabGroup
            as="div"
            class="col-span-2 flex h-full w-full flex-col items-center gap-2"
        >
            <HeadlessTabList
                class="bg-obsidian/25 text-stone-gray flex w-fit rounded-2xl px-1 py-2"
            >
                <HeadlessTab
                    v-for="route in blockRoutingSettings.routeGroups"
                    :key="route.id"
                    class="bg-obsidian hover:bg-obsidian/75 ui-selected:bg-stone-gray ui-selected:text-obsidian
                        ui-selected:pr-0 relative mx-1 flex cursor-pointer items-center justify-between rounded-xl px-6 py-2
                        font-bold focus:outline-none"
                >
                    <template #default="{ selected }">
                        <!-- Lock Icon -->
                        <UiIcon
                            v-if="route.isLocked"
                            name="MaterialSymbolsLockOutline"
                            class="h-4 w-4 -translate-x-2"
                        ></UiIcon>

                        <!-- Rename Input -->
                        <input
                            :ref="
                                (el) => {
                                    if (el) inputRefs.set(route.id, el as any);
                                }
                            "
                            v-if="editingRouteGroupId === route.id"
                            v-model="editInputValue"
                            type="text"
                            class="w-fit rounded font-bold outline-none"
                            @click.stop
                            @keydown.enter.prevent="confirmRename"
                            @keydown.esc.prevent="cancelRename"
                            @blur="confirmRename"
                        />

                        <!-- Display Route Name -->
                        <span v-else class="truncate font-bold" :title="route.name">
                            {{ route.name }}
                        </span>

                        <!-- Three Dots Menu -->
                        <UiSettingsUtilsRoutingGroupAction
                            v-if="selected"
                            :route-group-id="route.id"
                            :isLocked="route.isLocked"
                            :isDefault="route.isDefault"
                            @rename="handleStartRename"
                            @duplicate="duplicateGroup"
                            @default="setDefaultGroup"
                            @delete="deleteGroup"
                        ></UiSettingsUtilsRoutingGroupAction>

                        <!-- IsDefault dot -->
                        <span
                            v-if="route.isDefault"
                            class="bg-terracotta-clay absolute -top-0.5 -left-0.5 h-3 w-3 rounded-full"
                        >
                        </span>
                    </template>
                </HeadlessTab>

                <!-- Add New Route Group Button -->
                <button
                    class="bg-obsidian hover:bg-obsidian/75 ui-selected:bg-stone-gray mx-1 flex cursor-pointer items-center
                        justify-center rounded-xl px-3 py-2 font-bold focus:outline-none"
                    @click="addNewRouteGroup"
                >
                    <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5"></UiIcon>
                </button>
            </HeadlessTabList>

            <HeadlessTabPanels class="bg-obsidian/25 w-full grow overflow-y-auto rounded-3xl">
                <HeadlessTabPanel
                    v-for="route in blockRoutingSettings.routeGroups"
                    :key="route.id"
                    class="flex w-full items-center justify-center p-4"
                >
                    <div class="flex min-h-0 grow flex-col items-center gap-4">
                        <div class="relative w-full">
                            <h2 class="text-stone-gray text-center text-lg font-bold">
                                Route group - {{ route.name }}
                            </h2>

                            <!-- Add route button -->
                            <button
                                class="bg-obsidian hover:bg-obsidian/75 focus:outline-nonedisabled:cursor-not-allowed absolute top-0
                                    right-0 mx-1 flex cursor-pointer items-center justify-center rounded-xl px-3 py-2 font-bold
                                    disabled:opacity-50"
                                @click="addNewRoute(route.id)"
                                :disabled="route.isLocked"
                            >
                                <UiIcon
                                    name="Fa6SolidPlus"
                                    class="text-stone-gray h-5 w-5"
                                ></UiIcon>
                            </button>
                        </div>

                        <div
                            class="hide-scrollbar flex h-[600px] w-full grow flex-col gap-4 overflow-y-auto"
                        >
                            <TransitionGroup
                                tag="div"
                                name="list"
                                class="hide-scrollbar relative flex h-[600px] w-full grow flex-col gap-4 overflow-y-auto"
                            >
                                <UiSettingsUtilsRouteItem
                                    v-for="r in route.routes"
                                    :key="r.id"
                                    :route="r"
                                    :isLocked="route.isLocked"
                                    @update-route="
                                        (updatedRoute) => updateRoute(r.id, updatedRoute)
                                    "
                                    @delete-route="(id) => deleteRoute(id)"
                                ></UiSettingsUtilsRouteItem>
                            </TransitionGroup>
                        </div>
                    </div>
                </HeadlessTabPanel>
            </HeadlessTabPanels>
        </HeadlessTabGroup>
    </div>
</template>

<style scoped>
.list-move,
.list-enter-active,
.list-leave-active {
    transition: all 0.2s ease-in-out;
}
.list-enter-from,
.list-leave-to {
    opacity: 0;
    transform: translateY(-20px);
}
.list-leave-active {
    position: absolute;
}
</style>
