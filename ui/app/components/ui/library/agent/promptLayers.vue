<script setup lang="ts">
import type { AgentProfile } from '@/types/agent';
const layers = defineModel<AgentProfile['prompt_stack']>({ required: true });
const move = (index: number, direction: number) => {
    const target = index + direction;
    if (target < 0 || target >= layers.value.length) return;
    const layer = layers.value.splice(index, 1)[0];
    if (layer) layers.value.splice(target, 0, layer);
};
const addLayer = () => {
    if (!layers.value.length) layers.value.push({ name: 'Instructions', text: '', enabled: true });
    layers.value.push({ name: 'Additional instructions', text: '', enabled: true });
};
</script>

<template>
    <details class="group border-stone-gray/15 rounded-xl border">
        <summary class="flex cursor-pointer list-none items-center gap-3 p-4">
            <UiIcon name="FluentCodeText16Filled" class="text-stone-gray size-5 shrink-0" />
            <span class="flex-1"
                ><span class="text-soft-silk block text-sm font-medium">Instruction layers</span>
                <span class="text-stone-gray/60 mt-0.5 block text-xs"
                    >Optional · organize instructions and control their order</span
                ></span
            >
            <UiIcon
                name="FlowbiteChevronDownOutline"
                class="text-stone-gray/60 size-4 transition-transform group-open:rotate-180"
            />
        </summary>
        <div class="border-stone-gray/10 flex flex-col gap-4 border-t p-4">
            <p class="text-stone-gray/70 text-xs">
                Enabled layers run from top to bottom, alongside your graph and global prompts. The
                first layer is shown in the main instructions field.
            </p>
            <div
                v-for="(layer, index) in layers"
                :key="index"
                class="border-stone-gray/15 rounded-xl border p-3"
            >
                <div class="flex flex-wrap items-center gap-2">
                    <input
                        v-model="layer.name"
                        :aria-label="`Layer ${index + 1} name`"
                        maxlength="100"
                        required
                        class="bg-anthracite/30 text-soft-silk min-w-0 flex-1 rounded-lg px-3 py-2
                            text-sm"
                    />
                    <label class="text-stone-gray flex items-center gap-1.5 text-xs"
                        ><input v-model="layer.enabled" type="checkbox" class="accent-ember-glow" />
                        Enabled</label
                    >
                    <button
                        type="button"
                        :disabled="index === 0"
                        aria-label="Move layer up"
                        class="text-stone-gray rounded-lg p-2 disabled:opacity-25"
                        @click="move(index, -1)"
                    >
                        <UiIcon name="LineMdChevronSmallUp" class="size-4" />
                    </button>
                    <button
                        type="button"
                        :disabled="index === layers.length - 1"
                        aria-label="Move layer down"
                        class="text-stone-gray rounded-lg p-2 disabled:opacity-25"
                        @click="move(index, 1)"
                    >
                        <UiIcon name="LineMdChevronSmallUp" class="size-4 rotate-180" />
                    </button>
                    <button
                        type="button"
                        class="text-stone-gray/60 rounded-lg p-2 text-xs hover:text-red-400"
                        @click="layers.splice(index, 1)"
                    >
                        Remove
                    </button>
                </div>
                <textarea
                    v-if="index > 0"
                    v-model="layer.text"
                    :aria-label="`Layer ${index + 1} instructions`"
                    rows="4"
                    class="bg-anthracite/30 border-stone-gray/15 focus:border-ember-glow/70
                        text-soft-silk mt-3 w-full rounded-lg border p-3 text-sm outline-none"
                />
            </div>
            <button
                type="button"
                :disabled="layers.length >= 32"
                class="text-ember-glow self-start text-sm disabled:opacity-40"
                @click="addLayer"
            >
                + Add instruction layer
            </button>
        </div>
    </details>
</template>
