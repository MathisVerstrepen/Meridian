<script setup lang="ts">
import type { AgentProfile } from '@/types/agent';
import { AGENT_ICONS } from '@/utils/agentEditor';
import { useAgentIconGenerator } from '@/composables/useAgentIconGenerator';
const props = defineProps<{ disabled?: boolean }>();
const profile = defineModel<AgentProfile>({ required: true });
const emit = defineEmits<{ busy: [value: boolean] }>();
const { generating, error, candidate, canGenerate, stale, generate, apply } =
    useAgentIconGenerator(profile);
const storedIcon = ref(profile.value.iconSvg ?? '');
watch(
    () => profile.value.iconSvg,
    (value) => {
        if (value) storedIcon.value = value;
    },
);
watch(generating, (value) => emit('busy', value), { flush: 'sync' });
const selectPreset = (icon: string) => {
    profile.value.icon = icon;
    profile.value.iconSvg = null;
};
</script>
<template>
    <fieldset :disabled="props.disabled || generating" class="space-y-3">
        <legend class="text-stone-gray mb-2 text-sm">Icon</legend>
        <div class="flex flex-wrap gap-2">
            <button
                v-for="choice in AGENT_ICONS"
                :key="choice.icon"
                type="button"
                :aria-label="`${choice.label} icon`"
                :aria-pressed="!profile.iconSvg && profile.icon === choice.icon"
                :title="choice.label"
                class="flex size-10 items-center justify-center rounded-xl border transition-colors
                    disabled:opacity-40"
                :class="
                    !profile.iconSvg && profile.icon === choice.icon
                        ? 'border-ember-glow bg-ember-glow/10 text-ember-glow'
                        : 'border-stone-gray/20 text-stone-gray hover:bg-stone-gray/10'
                "
                @click="selectPreset(choice.icon)"
            >
                <UiIcon :name="choice.icon" class="size-5" />
            </button>
            <button
                v-if="storedIcon"
                type="button"
                aria-label="Custom SVG icon"
                :aria-pressed="!!profile.iconSvg"
                class="flex size-10 items-center justify-center rounded-xl border transition-colors"
                :class="
                    profile.iconSvg
                        ? 'border-ember-glow bg-ember-glow/10'
                        : 'border-stone-gray/20 hover:bg-stone-gray/10'
                "
                @click="profile.iconSvg = storedIcon"
            >
                <UiLibraryAgentIcon :profile="{ ...profile, iconSvg: storedIcon }" class="size-5" />
            </button>
        </div>
        <div class="border-stone-gray/15 bg-obsidian/10 space-y-3 rounded-xl border p-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                    <p class="text-soft-silk text-sm font-medium">Create a custom icon</p>
                    <p class="text-stone-gray/65 mt-1 text-xs leading-relaxed">
                        Use this Agent’s name, description, and instructions. The SVG follows your
                        accent color.
                    </p>
                </div>
                <button
                    type="button"
                    :disabled="!canGenerate || props.disabled || generating"
                    class="border-ember-glow/30 text-ember-glow hover:bg-ember-glow/10 inline-flex
                        items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium
                        disabled:cursor-not-allowed disabled:opacity-40"
                    @click="generate"
                >
                    <UiIcon
                        :name="generating ? 'LineMdLoadingTwotoneLoop' : 'MynauiSparklesSolid'"
                        class="size-4"
                    />{{
                        generating ? 'Generating…' : candidate ? 'Regenerate icon' : 'Generate icon'
                    }}
                </button>
            </div>
            <p v-if="!canGenerate" class="text-stone-gray/60 text-xs">
                Add a name, description, or instructions and choose a model first.
            </p>
            <div
                v-if="candidate"
                class="border-stone-gray/10 flex flex-wrap items-center gap-3 border-t pt-3"
            >
                <span
                    class="bg-stone-gray/5 flex size-16 shrink-0 items-center justify-center
                        rounded-xl"
                    ><UiLibraryAgentIcon
                        :profile="{ ...profile, iconSvg: candidate }"
                        label="Generated SVG icon"
                        class="size-10"
                /></span>
                <div class="min-w-0 flex-1">
                    <p class="text-soft-silk text-sm font-medium">
                        {{
                            candidate === profile.iconSvg
                                ? 'Custom icon selected'
                                : 'Preview your generated icon'
                        }}
                    </p>
                    <p class="text-stone-gray/65 mt-1 text-xs">
                        {{
                            stale
                                ? 'Details changed. Regenerate for the latest Agent details.'
                                : candidate === profile.iconSvg
                                  ? 'Save your Agent to keep this custom icon.'
                                  : 'Choose Use icon, then save your Agent to keep it.'
                        }}
                    </p>
                </div>
                <button
                    type="button"
                    :disabled="
                        stale || props.disabled || generating || candidate === profile.iconSvg
                    "
                    class="bg-ember-glow hover:bg-ember-glow/85 rounded-lg px-3 py-2 text-sm
                        font-semibold disabled:opacity-40"
                    @click="apply"
                >
                    {{ candidate === profile.iconSvg ? 'Selected' : 'Use icon' }}
                </button>
            </div>
            <p v-if="generating" role="status" class="text-stone-gray/70 text-xs">
                Generating a custom SVG icon…
            </p>
            <p v-if="error" role="alert" class="text-xs text-red-400">{{ error }}</p>
        </div>
    </fieldset>
</template>
