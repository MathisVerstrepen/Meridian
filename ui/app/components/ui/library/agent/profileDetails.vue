<script setup lang="ts">
import type { AgentProfile } from '@/types/agent';
import { AGENT_COLORS } from '@/utils/agentEditor';
defineProps<{ editing: boolean; disabled?: boolean }>();
defineEmits<{ iconBusy: [busy: boolean] }>();
const profile = defineModel<AgentProfile>({ required: true });
const tags = computed({
    get: () => profile.value.tags.join(', '),
    set: (value: string) => {
        profile.value.tags = value
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean);
    },
});
const inputClass =
    'bg-anthracite/30 border-stone-gray/20 focus:border-ember-glow/70 text-soft-silk w-full rounded-xl border px-3 py-2.5 outline-none transition-colors';
</script>

<template>
    <details class="group border-stone-gray/15 rounded-xl border">
        <summary class="flex cursor-pointer list-none items-center gap-3 p-4">
            <UiIcon name="MaterialSymbolsPaletteOutline" class="text-stone-gray size-5 shrink-0" />
            <span class="flex-1"
                ><span class="text-soft-silk block text-sm font-medium"
                    >Appearance & organization</span
                >
                <span class="text-stone-gray/60 mt-0.5 block text-xs"
                    >Icon, color, category, and tags</span
                ></span
            >
            <UiIcon
                name="FlowbiteChevronDownOutline"
                class="text-stone-gray/60 size-4 transition-transform group-open:rotate-180"
            />
        </summary>
        <div class="border-stone-gray/10 flex flex-col gap-5 border-t p-4">
            <UiLibraryAgentIconPicker
                v-model="profile"
                :disabled="disabled"
                @busy="$emit('iconBusy', $event)"
            />
            <fieldset>
                <legend class="text-stone-gray mb-2 text-sm">Accent color</legend>
                <div class="flex flex-wrap items-center gap-3">
                    <button
                        v-for="color in AGENT_COLORS"
                        :key="color"
                        type="button"
                        :aria-label="`Use accent ${color}`"
                        :aria-pressed="profile.accentColor === color"
                        :style="{ backgroundColor: color }"
                        class="ring-offset-obsidian flex size-8 items-center justify-center
                            rounded-full ring-offset-2"
                        :class="profile.accentColor === color ? 'ring-soft-silk ring-2' : ''"
                        @click="profile.accentColor = color"
                    >
                        <UiIcon
                            v-if="profile.accentColor === color"
                            name="MaterialSymbolsCheckSmallRounded"
                            class="size-5 text-white"
                        />
                    </button>
                    <label class="text-stone-gray/70 flex cursor-pointer items-center gap-2 text-xs"
                        >Custom
                        <input
                            v-model="profile.accentColor"
                            type="color"
                            aria-label="Custom accent color"
                            class="size-8 cursor-pointer overflow-hidden rounded-lg border-0
                                bg-transparent p-0"
                        />
                    </label>
                </div>
            </fieldset>
            <div class="grid gap-4 sm:grid-cols-2">
                <label class="text-stone-gray flex flex-col gap-2 text-sm"
                    >Category
                    <input
                        v-model="profile.category"
                        :class="inputClass"
                        maxlength="100"
                        list="agent-categories"
                /></label>
                <datalist id="agent-categories">
                    <option>General</option>
                    <option>Engineering</option>
                    <option>Research</option>
                    <option>Design</option>
                    <option>Creative</option>
                    <option>Writing</option>
                </datalist>
                <label class="text-stone-gray flex flex-col gap-2 text-sm"
                    >Tags
                    <input
                        v-model="tags"
                        :class="inputClass"
                        placeholder="research, writing, code…"
                    /><span class="text-stone-gray/50 text-xs"
                        >Separate tags with commas.</span
                    ></label
                >
            </div>
        </div>
    </details>
    <details class="group border-stone-gray/15 rounded-xl border">
        <summary class="flex cursor-pointer list-none items-center gap-3 p-4">
            <UiIcon
                name="MaterialSymbolsLightAdminPanelSettingsOutline"
                class="text-stone-gray size-5 shrink-0"
            />
            <span class="flex-1"
                ><span class="text-soft-silk block text-sm font-medium"
                    >Visibility & availability</span
                >
                <span class="text-stone-gray/60 mt-0.5 block text-xs">{{
                    profile.visibility === 'private'
                        ? 'Private · only you can use and edit this Agent'
                        : 'Public · discoverable in the marketplace'
                }}</span></span
            >
            <UiIcon
                name="FlowbiteChevronDownOutline"
                class="text-stone-gray/60 size-4 transition-transform group-open:rotate-180"
            />
        </summary>
        <div class="border-stone-gray/10 grid gap-4 border-t p-4 sm:grid-cols-2">
            <label class="text-stone-gray flex flex-col gap-2 text-sm"
                >Visibility
                <select
                    v-model="profile.visibility"
                    :class="inputClass"
                    :disabled="profile.lifecycle === 'draft'"
                >
                    <option value="private">Private — only you</option>
                    <option value="public">Public — list in marketplace</option></select
                ><span class="text-stone-gray/60 text-xs"
                    >Publishing shares your instructions and settings. Others can fork a copy.</span
                >
            </label>
            <label v-if="editing" class="text-stone-gray flex flex-col gap-2 text-sm"
                >Availability
                <select
                    v-model="profile.lifecycle"
                    :class="inputClass"
                    @change="profile.lifecycle === 'draft' && (profile.visibility = 'private')"
                >
                    <option value="active">Ready to use</option>
                    <option value="draft">Draft</option>
                    <option value="archived">Archived</option></select
                ><span class="text-stone-gray/60 text-xs"
                    >Draft and archived Agents are kept in your library and cannot run.</span
                >
            </label>
        </div>
    </details>
</template>
