<script setup lang="ts">
import type { AgentProfile } from '@/types/agent';
import { AGENT_ICONS } from '@/utils/agentEditor';
defineProps<{ presets: AgentProfile[] }>();
defineEmits<{ choose: [profile: AgentProfile] }>();
const iconFor = (profile: AgentProfile) =>
    AGENT_ICONS.find(
        (icon) =>
            icon.label ===
            (profile.category === 'Engineering'
                ? 'Code'
                : profile.category === 'Research'
                  ? 'Research'
                  : profile.category === 'Design'
                    ? 'Design'
                    : profile.category === 'Creative'
                      ? 'Images'
                      : 'Assistant'),
    )?.icon ?? 'RiBrain2Line';
</script>

<template>
    <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="Starter templates">
        <button
            v-for="starter in presets"
            :key="starter.handle"
            type="button"
            class="border-stone-gray/15 hover:border-ember-glow/50 hover:bg-ember-glow/5
                focus-visible:ring-ember-glow/60 flex items-start gap-3 rounded-xl border p-3
                text-left transition-colors focus-visible:ring-2"
            :aria-label="`Use ${starter.name} template`"
            @click="$emit('choose', starter)"
        >
            <UiIcon :name="iconFor(starter)" class="text-ember-glow mt-0.5 size-5 shrink-0" />
            <span class="min-w-0"
                ><span class="text-soft-silk block text-sm font-semibold">{{ starter.name }}</span>
                <span class="text-stone-gray/60 mt-1 block text-xs">{{
                    starter.category
                }}</span></span
            >
        </button>
    </div>
</template>
