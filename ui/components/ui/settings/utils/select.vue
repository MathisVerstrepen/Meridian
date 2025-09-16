<script lang="ts" setup>
const emit = defineEmits(['update:itemValue']);

interface Item {
    id: string;
    name: string;
    icon?: string;
}

// --- Props ---
const props = defineProps<{
    itemList: Item[];
    selected: string;
}>();

// --- Local State ---
const query = ref('');
const selected = ref<Item | null>(
    props.itemList.find((item) => item.id === props.selected) || null,
);

// --- Watchers ---
watch(
    () => selected.value,
    (newValue) => {
        emit('update:itemValue', newValue?.id);
    },
);
</script>

<template>
    <HeadlessCombobox v-model="selected">
        <div class="relative">
            <div
                class="bg-obsidian/20 dark:border-stone-gray/20 border-soft-silk/20 text-soft-silk/80 relative h-full w-full
                    cursor-default overflow-hidden rounded-2xl border-2 px-2 text-left focus:outline-none"
            >
                <div class="flex items-center">
                    <span v-if="selected?.icon" class="ml-3 flex flex-shrink-0 items-center">
                        <UiIcon :name="selected.icon" class="h-4 w-4" />
                    </span>

                    <HeadlessComboboxInput
                        class="relative w-full border-none py-2 pr-10 pl-2 text-sm leading-5 font-bold focus:ring-0
                            focus:outline-none"
                        :display-value="(item: unknown) => (item as Item).name"
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
                    class="bg-soft-silk absolute z-20 mt-1 h-fit w-full rounded-md p-1 text-base shadow-lg ring-1 ring-black/5
                        focus:outline-none"
                >
                    <HeadlessComboboxOption
                        v-for="item in itemList"
                        v-slot="{ selected: isSelected, active }"
                        :key="item.id"
                        :value="item"
                        as="template"
                    >
                        <li
                            class="relative cursor-pointer rounded-md py-2 pr-4 pl-10 select-none"
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
                                {{ item.name }}
                            </span>
                            <span
                                v-if="item.icon"
                                class="absolute inset-y-0 left-0 flex items-center pl-2"
                                :class="{
                                    'text-soft-silk/80': active,
                                    'text-obsidian': !active,
                                }"
                            >
                                <UiIcon :name="item.icon" class="h-5 w-5" />
                            </span>
                        </li>
                    </HeadlessComboboxOption>
                </HeadlessComboboxOptions>
            </HeadlessTransitionRoot>
        </div>
    </HeadlessCombobox>
</template>

<style scoped></style>
