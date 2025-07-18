<script lang="ts" setup>
const { blockDefinitions } = useBlocks();

// --- Stores ---
const sidebarCanvasStore = useSidebarCanvasStore();

// --- State from Stores ---
const { isOpen } = storeToRefs(sidebarCanvasStore);

// --- Composables ---
const { onDragStart, onDragEnd } = useGraphDragAndDrop();
</script>

<template>
    <div class="w-full overflow-hidden">
        <div
            class="flex w-[28rem] flex-col items-center px-4 pb-10 transition-opacity duration-300 ease-in-out"
            :class="{
                'opacity-0': !isOpen,
                'opacity-100': isOpen,
            }"
        >
            <HeadlessDisclosure
                v-for="(blocsInCategory, category) in blockDefinitions"
                :key="category"
                class="flex w-full flex-col"
                as="div"
                :defaultOpen="true"
            >
                <HeadlessDisclosureButton
                    class="mb-4 flex cursor-pointer items-center select-none"
                    as="div"
                >
                    <h2 class="text-stone-gray font-outfit text-xl font-bold">
                        {{ String(category).charAt(0).toUpperCase() + String(category).slice(1) }}
                    </h2>

                    <div class="mx-3 flex flex-1 items-center">
                        <div class="bg-stone-gray/20 h-[1px] w-full"></div>
                    </div>

                    <UiIcon
                        name="LineMdChevronSmallUp"
                        class="ui-open:rotate-180 ui-open:transform text-stone-gray h-6 w-6 transition-transform duration-200"
                    />
                </HeadlessDisclosureButton>

                <transition
                    enter-active-class="transition duration-100 ease-out"
                    enter-from-class="transform scale-95 opacity-0"
                    enter-to-class="transform scale-100 opacity-100"
                    leave-active-class="transition duration-75 ease-out"
                    leave-from-class="transform scale-100 opacity-100"
                    leave-to-class="transform scale-95 opacity-0"
                >
                    <HeadlessDisclosurePanel class="ui-open:mb-8" as="div">
                        <div
                            v-for="bloc in blocsInCategory"
                            :key="bloc.id"
                            class="dark:bg-stone-gray dark:hover:shadow-soft-silk/10 bg-anthracite relative mb-2 grid cursor-grab
                                grid-cols-[1fr_12fr] grid-rows-1 gap-2 overflow-hidden rounded-xl p-4 duration-300 hover:shadow-lg"
                            draggable="true"
                            @dragstart="onDragStart($event, bloc.id)"
                            @dragend="onDragEnd($event, bloc.id)"
                        >
                            <UiIcon
                                :name="bloc.icon"
                                class="dark:text-obsidian text-soft-silk h-6 w-6 self-center"
                            />
                            <h3
                                class="dark:text-obsidian text-soft-silk self-center text-lg font-bold"
                            >
                                {{ bloc.name }}
                            </h3>
                            <p class="dark:text-anthracite text-soft-silk/70 col-span-2 text-sm">
                                {{ bloc.desc }}
                            </p>

                            <!-- Color indicator -->
                            <span
                                class="absolute top-0 right-0 h-4 w-8 rounded-bl-lg"
                                :style="'background-color: ' + bloc.color"
                            >
                            </span>
                        </div>
                    </HeadlessDisclosurePanel>
                </transition>
            </HeadlessDisclosure>
        </div>
    </div>
</template>

<style scoped></style>
