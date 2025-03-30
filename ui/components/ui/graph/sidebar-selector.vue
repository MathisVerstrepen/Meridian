<script lang="ts" setup>
const { blockDefinitions } = useBlocks();

const categoryExpandedState = reactive<Record<string, boolean>>({});

const toggleCategory = (category: string) => {
    categoryExpandedState[category] = !categoryExpandedState[category];
};

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
        class="bg-anthracite/75 backdrop-blur-md h-[calc(100%-1rem)] w-[30rem] absolute top-2 right-2 z-10 rounded-2xl border-2 border-stone-gray/10 shadow-lg"
    >
        <div class="flex flex-col items-center justify-start h-full w-full py-10 px-4">
            <h1 class="mb-8 flex items-center space-x-2">
                <Icon
                    name="clarity:block-solid"
                    style="color: var(--color-stone-gray); height: 2rem; width: 2rem"
                />
                <span class="text-2xl font-bold text-stone-gray">Blocks</span>
            </h1>
            <div class="flex flex-col items-center justify-start w-full px-4 pb-10 overflow-y-auto">
                <div
                    v-for="(blocsInCategory, category) in blockDefinitions"
                    :key="category"
                    class="w-full flex flex-col"
                    :class="{
                        'mb-8': !categoryExpandedState[String(category)],
                    }"
                >
                    <div
                        class="flex items-center mb-4 cursor-pointer select-none"
                        :id="'block-' + category"
                        @click="toggleCategory(String(category))"
                    >
                        <h2 class="text-xl font-bold text-stone-gray">
                            {{
                                String(category).charAt(0).toUpperCase() + String(category).slice(1)
                            }}
                        </h2>

                        <div class="flex items-center flex-1 mx-3">
                            <div class="h-[1px] w-full bg-stone-gray/20"></div>
                        </div>

                        <Icon
                            :name="'line-md:chevron-small-up'"
                            style="color: var(--color-stone-gray); height: 1.5rem; width: 1.5rem"
                            class="transition-transform duration-200"
                            :class="{
                                'transform rotate-180': !categoryExpandedState[String(category)],
                            }"
                        />
                    </div>

                    <div v-show="!categoryExpandedState[String(category)]">
                        <div
                            v-for="bloc in blocsInCategory"
                            :key="bloc.id"
                            class="mb-2 bg-stone-gray rounded-lg p-4 grid grid-cols-[1fr_12fr] grid-rows-1 gap-2 cursor-grab hover:shadow-lg hover:shadow-soft-silk/10 duration-300"
                            draggable="true"
                            @dragstart="onDragStart($event, bloc.id)"
                        >
                            <Icon
                                :name="bloc.icon"
                                style="color: var(--color-obsidian); height: 1.5rem; width: 1.5rem"
                                class="self-center"
                            />
                            <h3 class="self-center text-lg font-bold text-obsidian">
                                {{ bloc.name }}
                            </h3>
                            <p class="text-anthracite col-span-2 text-sm">
                                {{ bloc.desc }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
[draggable='true']:active {
    cursor: grabbing;
    opacity: 0.7;
}
</style>
