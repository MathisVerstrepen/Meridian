<script lang="ts" setup>
const blocs = {
    input: [
        {
            id: "primary-prompt-text",
            name: "Prompt",
            desc: "In this block, you can enter a prompt to be sent to the LLM.",
            icon: "material-symbols:text-fields-rounded",
        },
    ],
    output: [
        {
            id: "primary-model-text-to-text",
            name: "Text to Text",
            desc: "In this block, you can select a model, link it to the prompt, and generate a response.",
            icon: "fluent:code-text-16-filled",
        },
    ],
};
</script>

<template>
    <div
        class="bg-stone-500/15 backdrop-blur-lg h-[95%] w-[30rem] absolute right-0 top-[2.5%] rounded-l-4xl border-2 border-stone-500/10"
    >
        <div
            class="flex flex-col items-center justify-start h-full w-full py-10 px-4"
        >
            <h1 class="text-2xl font-bold text-gray-800 mb-4">Blocks</h1>
            <div class="flex flex-col items-center justify-center w-full">
                <div
                    v-for="(blocs, category) in blocs"
                    :key="category"
                    class="w-full flex flex-col mb-4"
                >
                    <h2 class="text-xl font-bold text-gray-800 mb-2">
                        {{
                            category.charAt(0).toUpperCase() + category.slice(1)
                        }}
                    </h2>
                    <div
                        v-for="bloc in blocs"
                        :key="bloc.id"
                        class="mb-2 bg-white rounded-lg p-4 grid grid-cols-[1fr_10fr] grid-rows-1 gap-2 cursor-grab hover:shadow-lg transition-shadow duration-200 ease-in-out"
                    >
                        <Icon
                            :name="bloc.icon"
                            style="color: black; height: 2rem; width: 2rem"
                        />
                        <h3 class="text-lg font-bold text-gray-800">
                            {{ bloc.name }}
                        </h3>
                        <p class="text-gray-600 col-span-2">
                            {{ bloc.desc }}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
