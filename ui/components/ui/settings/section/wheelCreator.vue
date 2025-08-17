<script lang="ts" setup>
import { NodeTypeEnum } from '@/types/enums';
import type { WheelSlot } from '@/types/settings';

const props = defineProps<{
    slots: WheelSlot[];
}>();

// --- Composables ---
const { getBlockByNodeType } = useBlocks();

// --- Local State ---
const openedSlot = ref<number | null>(null);

// --- Core Logic Functions ---
const toggleOption = (slotIndex: number, option: NodeTypeEnum | null | undefined) => {
    if (option === null || option === undefined) return;

    const slot = props.slots[slotIndex];
    if (slot) {
        const optionIndex = slot.options.indexOf(option);
        if (optionIndex > -1) {
            slot.options.splice(optionIndex, 1);
        } else {
            slot.options.push(option);
        }
    }
};
</script>

<template>
    <ul class="row-auto grid w-full grid-cols-4 gap-2">
        <li v-for="(slot, index) in slots" @click="openedSlot = index" class="relative">
            <div
                class="bg-soft-silk/10 border-soft-silk/20 text-stone-gray hover:bg-soft-silk/5 flex h-20 w-full
                    cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-4 border-dashed p-2
                    transition-colors duration-200 ease-in-out"
                v-if="!slot.mainBloc"
            >
                <p class="text-center text-sm font-bold">{{ slot.name }}</p>
                <UiIcon name="Fa6SolidPlus" class="h-4 w-4"></UiIcon>
            </div>

            <template v-for="mainBloc in [getBlockByNodeType(slot.mainBloc)]" v-if="slot.mainBloc">
                <div
                    class="flex h-20 w-full cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-4"
                    :style="{
                        borderColor: `color-mix(in oklab, ${mainBloc?.color} 30%, transparent)`,
                        backgroundColor: `color-mix(in oklab, ${mainBloc?.color} 10%, transparent)`,
                        color: mainBloc?.color,
                    }"
                    v-if="slot.mainBloc"
                >
                    <div class="flex h-fit w-full items-center justify-center gap-1 px-2">
                        <UiIcon :name="mainBloc?.icon || ''" class="h-4 w-4" />
                        <p class="text-center text-sm font-bold">{{ mainBloc?.name }}</p>
                    </div>

                    <ul
                        class="flex max-h-8 w-full flex-wrap justify-center gap-1 overflow-y-auto px-2"
                        v-if="slot.options.length > 0"
                    >
                        <li v-for="option in slot.options" :key="option">
                            <template v-for="optBloc in [getBlockByNodeType(option)]">
                                <div
                                    class="rounded px-1 py-0.5 text-xs font-bold"
                                    :style="{
                                        color: optBloc?.color,
                                        backgroundColor: `color-mix(in oklab, ${optBloc?.color} 20%, transparent)`,
                                    }"
                                >
                                    {{ optBloc?.name }}
                                </div>
                            </template>
                        </li>
                    </ul>

                    <button
                        class="absolute top-2 right-2 flex cursor-pointer items-center justify-center rounded-lg p-0.5
                            transition-colors duration-200 ease-in-out hover:brightness-125"
                        :style="{
                            color: mainBloc?.color,
                            backgroundColor: `color-mix(in oklab, ${mainBloc?.color} 20%, transparent)`,
                        }"
                        @click="
                            () => {
                                slots[index].mainBloc = null;
                                slots[index].options = [];
                            }
                        "
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-3 w-3" />
                    </button>
                </div>
            </template>
        </li>

        <li
            v-if="openedSlot !== null"
            class="bg-soft-silk/10 text-stone-gray col-span-4 flex h-fit w-full flex-col gap-4 rounded-xl p-4"
        >
            <template v-if="slots[openedSlot]">
                <!-- Header with Title and Close Button -->
                <div
                    class="border-soft-silk/20 relative flex w-full items-center justify-center border-b pb-3"
                >
                    <h3 class="text-soft-silk text-base font-bold">{{ slots[openedSlot].name }}</h3>
                    <button
                        @click="openedSlot = null"
                        class="text-stone-gray hover:text-soft-silk absolute top-0 right-0 flex cursor-pointer items-center
                            justify-center transition-colors"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                    </button>
                </div>

                <div class="grid w-full grid-cols-2 items-start">
                    <!-- Main Bloc Section -->
                    <div class="border-soft-silk/20 flex flex-col items-center gap-3 border-r pr-4">
                        <label for="wheel-main-bloc" class="font-semibold">Main Bloc</label>
                        <ul
                            id="wheel-main-bloc"
                            class="grid w-full auto-rows-auto grid-cols-2 gap-2"
                        >
                            <li
                                v-for="bloc in [
                                    getBlockByNodeType(NodeTypeEnum.TEXT_TO_TEXT),
                                    getBlockByNodeType(NodeTypeEnum.ROUTING),
                                    getBlockByNodeType(NodeTypeEnum.PARALLELIZATION),
                                ]"
                                :key="bloc?.id"
                                class="bg-stone-gray text-obsidian hover:bg-stone-gray/80 border-stone-gray flex w-full cursor-pointer
                                    items-center gap-2 rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out"
                                :class="{
                                    '!bg-ember-glow/10 !border-ember-glow !text-ember-glow':
                                        slots[openedSlot].mainBloc === bloc?.nodeType,
                                }"
                                @click="slots[openedSlot].mainBloc = bloc?.nodeType ?? null"
                            >
                                <UiIcon :name="bloc?.icon || ''" class="h-4 w-4 shrink-0" />
                                <p class="text-sm">{{ bloc?.name }}</p>
                            </li>
                        </ul>
                    </div>

                    <!-- Options Section -->
                    <div class="flex flex-col items-center gap-3 pl-4">
                        <label for="wheel-options" class="font-semibold">Options</label>
                        <ul id="wheel-options" class="grid w-full auto-rows-auto grid-cols-2 gap-2">
                            <li
                                v-for="bloc in [
                                    getBlockByNodeType(NodeTypeEnum.PROMPT),
                                    getBlockByNodeType(NodeTypeEnum.FILE_PROMPT),
                                ]"
                                :key="bloc?.id"
                                class="bg-stone-gray text-obsidian hover:bg-stone-gray/80 border-stone-gray flex w-full cursor-pointer
                                    items-center gap-2 rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out"
                                :class="{
                                    '!bg-ember-glow/10 !border-ember-glow !text-ember-glow':
                                        bloc?.nodeType !== undefined &&
                                        slots[openedSlot].options.includes(bloc.nodeType),
                                }"
                                @click="toggleOption(openedSlot, bloc?.nodeType)"
                            >
                                <UiIcon :name="bloc?.icon || ''" class="h-4 w-4 shrink-0" />
                                <p class="text-sm">{{ bloc?.name }}</p>
                            </li>
                        </ul>
                    </div>
                </div>
            </template>
        </li>
    </ul>
</template>

<style scoped></style>
