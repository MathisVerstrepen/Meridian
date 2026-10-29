<script setup lang="ts">
import type { ToolEnum } from '@/types/enums';
import { AGENT_TOOLS, changeAgentTool } from '@/utils/agentEditor';
const tools = defineModel<ToolEnum[]>({ required: true });
const toggle = (tool: ToolEnum, event: Event) => {
    if (event.target instanceof HTMLInputElement)
        tools.value = changeAgentTool(tools.value, tool, event.target.checked);
};
</script>

<template>
    <fieldset>
        <legend class="text-soft-silk text-base font-semibold">What can it do?</legend>
        <p class="text-stone-gray/70 mt-1 mb-4 text-sm">
            Choose the tools it needs. You can change these later.
        </p>
        <div class="grid gap-2 sm:grid-cols-2">
            <label
                v-for="tool in AGENT_TOOLS"
                :key="tool.value"
                class="focus-within:ring-ember-glow/60 flex cursor-pointer items-start gap-3
                    rounded-xl border p-3 transition-colors focus-within:ring-2"
                :class="
                    tools.includes(tool.value)
                        ? 'border-ember-glow/50 bg-ember-glow/5'
                        : 'border-stone-gray/15 hover:border-stone-gray/35 hover:bg-stone-gray/5'
                "
            >
                <UiIcon :name="tool.icon" class="text-stone-gray mt-0.5 size-5 shrink-0" />
                <span class="min-w-0 flex-1"
                    ><span class="text-soft-silk block text-sm font-medium">{{ tool.name }}</span>
                    <span class="text-stone-gray/65 mt-1 block text-xs leading-relaxed">{{
                        tool.description
                    }}</span></span
                >
                <input
                    type="checkbox"
                    :aria-label="tool.name"
                    :checked="tools.includes(tool.value)"
                    class="accent-ember-glow mt-1 size-4 shrink-0 cursor-pointer"
                    @change="toggle(tool.value, $event)"
                />
            </label>
        </div>
        <p class="text-stone-gray/60 mt-3 text-xs">
            Web search includes permission to read links. Each Agent keeps its own tool permissions.
        </p>
    </fieldset>
</template>
