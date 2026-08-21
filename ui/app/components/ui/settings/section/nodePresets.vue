<script setup lang="ts">
import { DEFAULT_NODE_PRESET_ACCENT_COLOR } from '@/types/nodePresets';
import type { User } from '@/types/user';

interface PresetCanvasExpose {
    flush: () => boolean;
}

const settingsStore = useSettingsStore();
const { nodePresetSettings, nodePresetValidation } = storeToRefs(settingsStore);
const { generateId } = useUniqueId();
const { user } = useUserSession();

const selectedId = ref<string | null>(nodePresetSettings.value.presets[0]?.id ?? null);
const canvas = ref<PresetCanvasExpose | null>(null);
const selectedPreset = computed(() =>
    nodePresetSettings.value.presets.find((preset) => preset.id === selectedId.value),
);
const freePlan = computed(() => (user.value)?.plan_type === 'free');

const flushCanvas = () => canvas.value?.flush() ?? true;
const firstAvailableName = () => {
    const keys = new Set(
        nodePresetSettings.value.presets.map((preset) => preset.name.normalize('NFKC').toLocaleLowerCase()),
    );
    let index = 1;
    while (keys.has((index === 1 ? 'Untitled preset' : `Untitled preset ${index}`).toLocaleLowerCase())) {
        index += 1;
    }
    return index === 1 ? 'Untitled preset' : `Untitled preset ${index}`;
};

const createPreset = () => {
    if (!flushCanvas()) return;
    const preset = {
        id: generateId(),
        name: firstAvailableName(),
        accentColor: DEFAULT_NODE_PRESET_ACCENT_COLOR,
        nodes: [],
        edges: [],
    };
    nodePresetSettings.value.presets.push(preset);
    selectedId.value = preset.id;
};

const selectPreset = (id: string) => {
    if (id === selectedId.value || !flushCanvas()) return;
    settingsStore.setNodePresetEditorIssues([]);
    selectedId.value = id;
};

const renamePreset = (id: string, name: string) => {
    const preset = nodePresetSettings.value.presets.find((entry) => entry.id === id);
    if (preset) preset.name = name;
};

const updatePresetAccent = (id: string, accentColor: string) => {
    const preset = nodePresetSettings.value.presets.find((entry) => entry.id === id);
    if (preset) preset.accentColor = accentColor;
};

const deletePreset = (id: string) => {
    const preset = nodePresetSettings.value.presets.find((entry) => entry.id === id);
    if (!preset || !window.confirm(`Delete “${preset.name}”?`)) return;
    const index = nodePresetSettings.value.presets.findIndex((entry) => entry.id === id);
    nodePresetSettings.value.presets.splice(index, 1);
    if (selectedId.value === id) {
        settingsStore.setNodePresetEditorIssues([]);
        selectedId.value =
            nodePresetSettings.value.presets[Math.min(index, nodePresetSettings.value.presets.length - 1)]?.id ?? null;
    }
};

const movePreset = (from: number, to: number) => {
    if (to < 0 || to >= nodePresetSettings.value.presets.length) return;
    const [preset] = nodePresetSettings.value.presets.splice(from, 1);
    if (preset) nodePresetSettings.value.presets.splice(to, 0, preset);
};

</script>

<template>
    <div class="flex min-h-full min-w-0 flex-col gap-3 py-4 lg:h-full lg:min-h-0 lg:overflow-hidden">
        <div>
            <h2 class="text-soft-silk font-semibold">Node Presets</h2>
            <p class="text-stone-gray/70 mt-1 max-w-3xl text-sm">
                Build account-synced node groups and workflows. Changes save with the Settings Save Changes button.
            </p>
        </div>

        <div
            v-if="!nodePresetValidation.valid"
            class="border-red-400/30 bg-red-400/10 rounded-lg border px-3 py-2 text-xs text-red-300"
            role="alert"
        >
            <p v-for="issue in nodePresetValidation.issues.slice(0, 4)" :key="`${issue.path.join('.')}-${issue.code}`">
                {{ issue.path.join('.') || 'nodePresets' }}: {{ issue.message }}
            </p>
        </div>

        <div class="grid min-w-0 flex-1 grid-cols-1 gap-3 lg:h-full lg:min-h-0 lg:grid-cols-[260px_minmax(0,1fr)] lg:overflow-hidden">
            <UiSettingsNodePresetsPresetList
                :presets="nodePresetSettings.presets"
                :selected-id="selectedId"
                :issues="nodePresetValidation.issues"
                @create="createPreset"
                @select="selectPreset"
                @rename="renamePreset"
                @accent="updatePresetAccent"
                @delete="deletePreset"
                @move="movePreset"
            />

            <UiSettingsNodePresetsPresetCanvas
                v-if="selectedPreset"
                :key="selectedPreset.id"
                ref="canvas"
                :preset="selectedPreset"
                :free-plan="freePlan"
            />
            <div
                v-else
                class="border-stone-gray/15 bg-obsidian/35 text-stone-gray/60 flex min-h-[420px] flex-col items-center justify-center rounded-xl border px-6 text-center text-sm lg:h-full lg:min-h-0"
            >
                <UiIcon name="MaterialSymbolsDashboardCustomizeOutlineRounded" class="text-stone-gray/35 mb-3 h-9 w-9" />
                <span class="text-soft-silk/80 font-semibold">Canvas waiting for a preset</span>
                <span class="mt-1 max-w-xs text-xs">Create a preset from the rail to start arranging reusable blocks.</span>
            </div>
        </div>
    </div>
</template>
