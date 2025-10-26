<script lang="ts" setup>
import { SavingStatus } from '@/types/enums';
import type { RouteGroup } from '@/types/settings';

// --- Stores ---
const settingsStore = useSettingsStore();
const canvasSaveStore = useCanvasSaveStore();

// --- State from Stores ---
const { blockRoutingSettings, isReady } = storeToRefs(settingsStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;

// --- Props ---
const props = defineProps<{
    routingGroupId: string | undefined;
    setRoutingGroupId: (id: string) => void;
    color?: 'grey' | null;
}>();

// --- Local State ---
const selected = ref<RouteGroup | undefined>();
const query = ref<string>('');

// --- Watchers ---
watchEffect(() => {
    if (!isReady.value) {
        return;
    }

    const targetRoutingGroupId =
        props.routingGroupId ||
        blockRoutingSettings.value.routeGroups.find((group) => group.isDefault)?.id;
    selected.value = blockRoutingSettings.value.routeGroups.find(
        (group) => group.id === targetRoutingGroupId,
    );
});

watch(selected, (newSelected) => {
    if (!newSelected) return;

    if (props.routingGroupId !== newSelected.id) {
        props.setRoutingGroupId(newSelected.id);
    }

    setNeedSave(SavingStatus.NOT_SAVED);
});
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative">
            <div
                class="relative flex h-full w-full cursor-default items-center overflow-hidden
                    rounded-2xl border-2 text-left focus:outline-none"
                :class="{
                    'dark:bg-soft-silk/50 bg-soft-silk/20 border-obsidian/80 text-obsidian/80':
                        color === undefined || color === null,
                    'bg-obsidian/20 dark:border-stone-gray/20 border-soft-silk/20 text-soft-silk/80':
                        color === 'grey',
                }"
            >
                <div class="flex items-center gap-2 pl-3">
                    <UiIcon name="MaterialSymbolsTabGroupRounded" class="h-5 w-5" />
                    <HeadlessComboboxInput
                        class="relative w-full border-none py-1 pr-10 text-sm leading-5 font-bold
                            focus:ring-0 focus:outline-none"
                        :display-value="(routegroup: unknown) => (routegroup as RouteGroup).name"
                        @change="query = $event.target.value"
                    />
                </div>
                <HeadlessComboboxButton
                    class="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-1"
                >
                    <UiIcon name="FlowbiteChevronDownOutline" class="h-7 w-7" />
                </HeadlessComboboxButton>
            </div>

            <HeadlessTransitionRoot
                leave="transition ease-in duration-100"
                leave-from="opacity-100"
                leave-to="opacity-0"
                @after-leave="query = ''"
            >
                <HeadlessComboboxOptions
                    class="bg-soft-silk absolute z-40 mt-1 h-fit w-[20rem] rounded-md p-1 text-base
                        shadow-lg ring-1 ring-black/5 focus:outline-none"
                >
                    <HeadlessComboboxOption
                        v-for="blockRouting in blockRoutingSettings.routeGroups"
                        v-slot="{ selected: isSelected, active }"
                        :key="blockRouting.id"
                        :value="blockRouting"
                        as="template"
                    >
                        <li
                            class="relative cursor-pointer rounded-md px-4 py-2 select-none"
                            :class="{
                                'bg-olive-grove-dark text-soft-silk/80': active,
                                'text-obsidian': !active,
                            }"
                        >
                            <span
                                class="block truncate"
                                :class="{
                                    'font-medium': isSelected,
                                    'font-normal': !isSelected,
                                }"
                            >
                                {{ blockRouting.name }}
                            </span>
                        </li>
                    </HeadlessComboboxOption>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped></style>
