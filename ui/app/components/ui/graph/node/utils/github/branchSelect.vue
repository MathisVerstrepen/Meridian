<script lang="ts" setup>
const currentBranch = defineModel<string>('currentBranch');

defineProps<{
    branches: string[];
}>();
</script>

<template>
    <HeadlessListbox v-model="currentBranch" as="div" class="relative w-1/3">
        <HeadlessListboxButton
            class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow relative w-full
                cursor-pointer rounded-lg border py-2 pr-10 pl-3 text-left focus:outline-none"
        >
            <span class="block truncate">
                <UiIcon name="MdiSourceBranch" class="text-stone-gray/60 mr-2 h-4 w-4" />{{
                    currentBranch
                }}</span
            >
            <span class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <UiIcon
                    name="FlowbiteChevronDownOutline"
                    class="text-stone-gray/60 h-5 w-5"
                    aria-hidden="true"
                />
            </span>
        </HeadlessListboxButton>
        <transition
            leave-active-class="transition duration-100 ease-in"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <HeadlessListboxOptions
                class="bg-obsidian border-stone-gray/20 dark-scrollbar ring-opacity-5 absolute z-10 mt-1 max-h-60 w-full
                    overflow-auto rounded-md py-1 text-base shadow-lg ring-1 ring-black focus:outline-none sm:text-sm"
            >
                <HeadlessListboxOption
                    v-for="branch in branches"
                    :key="branch"
                    v-slot="{ active, selected }"
                    :value="branch"
                    as="template"
                >
                    <li
                        :class="[
                            active ? 'bg-ember-glow/20 text-ember-glow' : 'text-soft-silk',
                            'relative cursor-pointer py-2 pr-4 pl-10 select-none',
                        ]"
                    >
                        <span
                            :class="[selected ? 'font-medium' : 'font-normal', 'block truncate']"
                            >{{ branch }}</span
                        >
                        <span
                            v-if="selected"
                            class="text-ember-glow absolute inset-y-0 left-0 flex items-center pl-3"
                        >
                            <UiIcon
                                name="MaterialSymbolsCheckSmallRounded"
                                class="h-5 w-5"
                                aria-hidden="true"
                            />
                        </span>
                    </li>
                </HeadlessListboxOption>
            </HeadlessListboxOptions>
        </transition>
    </HeadlessListbox>
</template>

<style scoped></style>
