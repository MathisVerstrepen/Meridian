<script setup lang="ts">
import type { AgentModelSettings } from '@/types/agent';
import { ReasoningEffortEnum } from '@/types/enums';
const settings = defineModel<AgentModelSettings>({ required: true });
const numericFields = [
    { key: 'max_tokens', label: 'Max tokens', min: 1, max: 1000000, step: 1 },
    { key: 'temperature', label: 'Temperature', min: 0, max: 2, step: 0.1 },
    { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.05 },
    { key: 'top_k', label: 'Top K', min: 0, max: undefined, step: 1 },
    { key: 'frequency_penalty', label: 'Frequency penalty', min: -2, max: 2, step: 0.1 },
    { key: 'presence_penalty', label: 'Presence penalty', min: -2, max: 2, step: 0.1 },
    { key: 'repetition_penalty', label: 'Repetition penalty', min: 0.01, max: 2, step: 0.1 },
] as const;
const updateNumber = (key: (typeof numericFields)[number]['key'], event: Event) => {
    if (!(event.target instanceof HTMLInputElement)) return;
    settings.value[key] = event.target.value === '' ? null : event.target.valueAsNumber;
};
const inputClass =
    'bg-anthracite/30 border-stone-gray/20 focus:border-ember-glow/70 text-soft-silk w-full rounded-xl border px-3 py-2.5 outline-none transition-colors';
</script>

<template>
    <details class="group border-stone-gray/15 rounded-xl border">
        <summary class="flex cursor-pointer list-none items-center gap-3 p-4">
            <UiIcon name="MaterialSymbolsSettingsRounded" class="text-stone-gray size-5 shrink-0" />
            <span class="flex-1"
                ><span class="text-soft-silk block text-sm font-medium"
                    >Advanced model settings</span
                >
                <span class="text-stone-gray/60 mt-0.5 block text-xs"
                    >Optional · reasoning, generation parameters, and fallback</span
                ></span
            >
            <UiIcon
                name="FlowbiteChevronDownOutline"
                class="text-stone-gray/60 size-4 transition-transform group-open:rotate-180"
            />
        </summary>
        <div class="border-stone-gray/10 flex flex-col gap-5 border-t p-4">
            <p class="text-stone-gray/70 text-sm">
                Leave overrides empty to use your graph settings.
            </p>
            <div class="grid gap-4 sm:grid-cols-2">
                <label class="text-stone-gray flex flex-col gap-2 text-sm"
                    >Reasoning effort
                    <select v-model="settings.reasoning_effort" :class="inputClass">
                        <option :value="null">Use graph setting</option>
                        <option v-for="effort in ReasoningEffortEnum" :key="effort" :value="effort">
                            {{ effort.charAt(0).toUpperCase() + effort.slice(1) }}
                        </option>
                    </select>
                </label>
                <label class="text-stone-gray flex flex-col gap-2 text-sm"
                    >Reasoning visibility
                    <select v-model="settings.exclude_reasoning" :class="inputClass">
                        <option :value="null">Use graph setting</option>
                        <option :value="false">Show reasoning</option>
                        <option :value="true">Hide reasoning</option>
                    </select>
                </label>
                <label
                    v-for="field in numericFields"
                    :key="field.key"
                    class="text-stone-gray flex flex-col gap-2 text-sm"
                    >{{ field.label }}
                    <input
                        :value="settings[field.key] ?? ''"
                        type="number"
                        :step="field.step"
                        :min="field.min"
                        :max="field.max"
                        placeholder="Use graph setting"
                        :class="inputClass"
                        @input="updateNumber(field.key, $event)"
                    />
                </label>
                <label class="text-stone-gray flex flex-col gap-2 text-sm"
                    >Retries
                    <input
                        v-model.number="settings.retry_count"
                        type="number"
                        min="0"
                        max="3"
                        :class="inputClass"
                /></label>
            </div>
            <div class="border-stone-gray/10 flex items-center justify-between gap-4 border-t pt-4">
                <label class="text-stone-gray text-sm" for="agent-structured-output"
                    >Structured JSON output</label
                >
                <UiSettingsUtilsSwitch
                    id="agent-structured-output"
                    :state="settings.structured_output"
                    :set-state="(value) => (settings.structured_output = value)"
                />
            </div>
            <div class="border-stone-gray/10 border-t pt-4">
                <div class="flex items-center justify-between gap-3">
                    <label class="text-stone-gray text-sm">Fallback model</label>
                    <button
                        v-if="settings.fallback_model"
                        type="button"
                        class="text-stone-gray/65 hover:text-soft-silk text-xs"
                        @click="settings.fallback_model = null"
                    >
                        Remove fallback
                    </button>
                </div>
                <p class="text-stone-gray/60 mt-1 mb-3 text-xs">
                    Use another model if this Agent's model fails before it runs tools.
                </p>
                <button
                    v-if="!settings.fallback_model"
                    type="button"
                    class="border-stone-gray/20 text-stone-gray hover:bg-stone-gray/5 rounded-xl
                        border px-3 py-2 text-sm"
                    @click="settings.fallback_model = settings.model"
                >
                    Choose a fallback model
                </button>
                <UiModelsSelect
                    v-else
                    :model="settings.fallback_model"
                    :set-model="(value) => (settings.fallback_model = value)"
                    :disabled="false"
                    variant="grey"
                    to="right"
                    from="bottom"
                    class="h-11 w-full"
                    prevent-trigger-on-mount
                />
            </div>
        </div>
    </details>
</template>
