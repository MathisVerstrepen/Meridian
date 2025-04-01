<script lang="ts" setup>
const { blockDefinitions } = useBlocks();

const onDragStart = (event: DragEvent, blocId: string) => {
    if (event.dataTransfer) {
        event.dataTransfer.setData('application/json', JSON.stringify({ blocId }));
        event.dataTransfer.effectAllowed = 'copy';
    } else {
        console.error('DataTransfer is not available.');
    }
};
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 right-2 z-10 flex h-[calc(100%-1rem)] w-[30rem]
            flex-col items-center justify-start rounded-2xl border-2 px-4 py-10 shadow-lg backdrop-blur-md"
    >
        <h1 class="mb-8 flex items-center space-x-3">
            <Icon
                name="clarity:block-solid"
                style="color: var(--color-stone-gray); height: 2rem; width: 2rem"
            />
            <span class="text-stone-gray font-outfit text-2xl font-bold">Blocks</span>
        </h1>
        <div class="flex w-full flex-col items-center justify-start overflow-y-auto px-4 pb-10">
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

                    <Icon
                        :name="'line-md:chevron-small-up'"
                        style="color: var(--color-stone-gray); height: 1.5rem; width: 1.5rem"
                        class="ui-open:rotate-180 ui-open:transform transition-transform duration-200"
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
                            class="bg-stone-gray hover:shadow-soft-silk/10 mb-2 grid cursor-grab grid-cols-[1fr_12fr] grid-rows-1 gap-2
                                rounded-lg p-4 duration-300 hover:shadow-lg"
                            draggable="true"
                            @dragstart="onDragStart($event, bloc.id)"
                        >
                            <Icon
                                :name="bloc.icon"
                                style="color: var(--color-obsidian); height: 1.5rem; width: 1.5rem"
                                class="self-center"
                            />
                            <h3 class="text-obsidian self-center text-lg font-bold">
                                {{ bloc.name }}
                            </h3>
                            <p class="text-anthracite col-span-2 text-sm">
                                {{ bloc.desc }}
                            </p>
                        </div>
                    </HeadlessDisclosurePanel>
                </transition>
            </HeadlessDisclosure>
        </div>
    </div>
</template>

<style scoped>
[draggable='true']:active {
    cursor: grabbing;
    opacity: 0.7;
}
</style>
