<script setup lang="ts">
import { ChromePicker } from 'vue-color';
import 'vue-color/style.css';
import type { CSSProperties } from 'vue';

import {
    DEFAULT_NODE_PRESET_ACCENT_COLOR,
    isNodePresetAccentColor,
    MAX_NODE_PRESETS,
    type NodePreset,
} from '@/types/nodePresets';
import type { NodePresetValidationIssue } from '@/utils/nodePresets';

const props = defineProps<{
    presets: NodePreset[];
    selectedId: string | null;
    issues: NodePresetValidationIssue[];
}>();

const emit = defineEmits<{
    create: [];
    select: [id: string];
    rename: [id: string, name: string];
    accent: [id: string, accentColor: string];
    delete: [id: string];
    move: [from: number, to: number];
}>();

const draggedIndex = ref<number | null>(null);
const activeColorPresetId = ref<string | null>(null);
const colorPicker = ref<HTMLElement | null>(null);
const colorPickerPosition = ref<CSSProperties>({ top: '0', left: '0' });
const hasIssue = (index: number) =>
    props.issues.some((issue) => issue.path[0] === 'presets' && issue.path[1] === index);
const presetAccent = (preset: NodePreset) =>
    isNodePresetAccentColor(preset.accentColor)
        ? preset.accentColor.toLowerCase()
        : DEFAULT_NODE_PRESET_ACCENT_COLOR;
const activePreset = computed(() =>
    props.presets.find((preset) => preset.id === activeColorPresetId.value),
);
const activeColor = computed({
    get: () => (activePreset.value ? presetAccent(activePreset.value) : DEFAULT_NODE_PRESET_ACCENT_COLOR),
    set: (accentColor: string) => {
        if (!activePreset.value || !isNodePresetAccentColor(accentColor)) return;
        emit('accent', activePreset.value.id, accentColor.toLowerCase());
    },
});
const cardStyle = (preset: NodePreset): CSSProperties => {
    const accentColor = presetAccent(preset);
    if (props.selectedId !== preset.id) return { '--preset-accent': accentColor };
    return {
        '--preset-accent': accentColor,
        borderColor: accentColor,
        boxShadow: `inset 3px 0 0 ${accentColor}`,
        backgroundColor: `color-mix(in srgb, ${accentColor} 9%, transparent)`,
    };
};
const closeColorPicker = () => {
    activeColorPresetId.value = null;
};
const toggleColorPicker = async (event: MouseEvent, preset: NodePreset) => {
    event.stopPropagation();
    if (activeColorPresetId.value === preset.id) {
        closeColorPicker();
        return;
    }
    const trigger = event.currentTarget as HTMLElement;
    const bounds = trigger.getBoundingClientRect();
    const pickerWidth = 225;
    const pickerHeight = 310;
    const left = Math.min(Math.max(8, bounds.left), window.innerWidth - pickerWidth - 8);
    const top =
        bounds.bottom + pickerHeight + 8 <= window.innerHeight
            ? bounds.bottom + 8
            : Math.max(8, bounds.top - pickerHeight - 8);
    colorPickerPosition.value = { top: `${top}px`, left: `${left}px` };
    activeColorPresetId.value = preset.id;
    await nextTick();
    colorPicker.value?.querySelector<HTMLInputElement>('.vc-input-input')?.focus();
};
const onDragStart = (event: DragEvent, index: number) => {
    draggedIndex.value = index;
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
};
const onCardKeydown = (event: KeyboardEvent, index: number) => {
    if (!event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return;
    event.preventDefault();
    event.stopPropagation();
    const targetIndex = index + (event.key === 'ArrowUp' ? -1 : 1);
    if (targetIndex >= 0 && targetIndex < props.presets.length) emit('move', index, targetIndex);
};
</script>

<template>
    <aside aria-label="Preset rail" class="border-stone-gray/15 bg-obsidian/40 flex min-h-0 flex-col overflow-hidden rounded-xl border lg:h-full">
        <div class="border-stone-gray/10 border-b p-3.5">
            <div class="flex items-center gap-2.5">
                <span class="bg-ember-glow/15 text-ember-glow flex h-9 w-9 shrink-0 items-center justify-center rounded-xl">
                    <UiIcon name="MaterialSymbolsDashboardCustomizeOutlineRounded" class="h-5 w-5" />
                </span>
                <div class="min-w-0 flex-1">
                    <h2 class="text-soft-silk text-sm font-bold">Presets</h2>
                    <p class="text-stone-gray/55 truncate text-[11px]">Wheel-ready workflows</p>
                </div>
                <span class="bg-stone-gray/10 text-stone-gray/75 rounded-full px-2 py-1 text-[10px] font-bold tabular-nums">
                    {{ presets.length }}/{{ MAX_NODE_PRESETS }}
                </span>
            </div>
            <button
                type="button"
                class="bg-ember-glow text-soft-silk focus-visible:ring-soft-silk/60 mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold transition-colors hover:brightness-110 focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="presets.length >= MAX_NODE_PRESETS"
                @click="emit('create')"
            >
                <UiIcon name="Fa6SolidPlus" class="h-3 w-3" />
                New
            </button>
        </div>

        <div v-if="presets.length === 0" class="flex flex-1 flex-col items-center justify-center px-5 py-10 text-center">
            <span class="border-stone-gray/15 bg-anthracite/45 text-stone-gray/45 flex h-11 w-11 items-center justify-center rounded-2xl border">
                <UiIcon name="MaterialSymbolsDashboardCustomizeOutlineRounded" class="h-5 w-5" />
            </span>
            <p class="text-soft-silk/80 mt-3 text-xs font-semibold">No presets yet</p>
            <p class="text-stone-gray/55 mt-1 text-[11px] leading-relaxed">Create one, arrange blocks, then launch it from the canvas wheel.</p>
            <button
                type="button"
                class="text-ember-glow focus-visible:ring-ember-glow/60 mt-3 rounded-md px-2 py-1 text-xs font-semibold focus-visible:ring-2 focus-visible:outline-none"
                @click="emit('create')"
            >
                Create first preset
            </button>
        </div>
        <ul v-else class="hide-scrollbar flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto p-2" aria-label="Node presets">
            <li
                v-for="(preset, index) in presets"
                :key="preset.id"
                draggable="true"
                tabindex="0"
                :aria-current="selectedId === preset.id ? 'true' : undefined"
                aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
                :aria-describedby="`preset-reorder-${preset.id}`"
                :style="cardStyle(preset)"
                :class="[
                    'group focus-within:ring-[var(--preset-accent)] relative cursor-pointer rounded-xl border p-2 transition-colors focus-within:ring-1',
                    selectedId === preset.id
                        ? ''
                        : 'border-stone-gray/10 bg-anthracite/35 hover:border-stone-gray/25 hover:bg-anthracite/55',
                    draggedIndex === index ? 'border-stone-gray/40 border-dashed opacity-45' : '',
                ]"
                @click="emit('select', preset.id)"
                @dragstart="onDragStart($event, index)"
                @dragenter.prevent="
                    draggedIndex !== null && draggedIndex !== index
                        ? (emit('move', draggedIndex, index), (draggedIndex = index))
                        : undefined
                "
                @dragover.prevent
                @dragend="draggedIndex = null"
                @keydown="onCardKeydown($event, index)"
            >
                <span :id="`preset-reorder-${preset.id}`" class="sr-only">
                    Press Alt plus Arrow Up or Arrow Down to reorder this preset.
                </span>
                <div class="flex items-start gap-1.5">
                    <span
                        class="text-stone-gray/35 group-hover:text-stone-gray/65 flex h-6 w-4 shrink-0 cursor-grab items-center justify-center active:cursor-grabbing"
                        :aria-label="`Drag ${preset.name} to reorder`"
                        role="img"
                        title="Drag to reorder"
                    >
                        <UiIcon name="MaterialSymbolsDragIndicator" class="h-4 w-4" />
                    </span>
                    <div class="min-w-0 flex-1">
                        <input
                            :value="preset.name"
                            maxlength="64"
                            aria-label="Preset name"
                            class="text-soft-silk focus:border-ember-glow/60 focus:bg-obsidian/40 w-full truncate rounded-md border border-transparent bg-transparent px-1.5 py-0.5 text-sm font-semibold outline-none"
                            @click.stop="emit('select', preset.id)"
                            @change="emit('rename', preset.id, ($event.target as HTMLInputElement).value)"
                        />
                        <div class="mt-0.5 flex min-w-0 items-center gap-1">
                            <div class="flex min-w-0 flex-1 items-center gap-1.5 px-1.5">
                                <template v-if="hasIssue(index)">
                                    <span
                                        class="h-1.5 w-1.5 shrink-0 rounded-full bg-red-400"
                                    />
                                    <span class="truncate text-[10px] font-semibold text-red-400">Invalid</span>
                                </template>
                                <template v-else-if="preset.nodes.length === 0">
                                    <span class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                                    <span class="truncate text-[10px] font-semibold text-amber-400">
                                        Draft · not placeable
                                    </span>
                                </template>
                                <span v-else class="text-stone-gray/50 truncate text-[10px]">
                                    {{ preset.nodes.length }} {{ preset.nodes.length === 1 ? 'node' : 'nodes' }}
                                </span>
                            </div>
                            <button
                                type="button"
                                draggable="false"
                                :aria-label="`Choose accent color for ${preset.name}`"
                                aria-haspopup="dialog"
                                :aria-expanded="activeColorPresetId === preset.id"
                                :aria-controls="`preset-color-picker-${preset.id}`"
                                class="border-soft-silk/25 focus-visible:ring-soft-silk/70 h-6 w-6 shrink-0 rounded-md border shadow-sm outline-none focus-visible:ring-2"
                                :style="{ backgroundColor: presetAccent(preset) }"
                                @click.stop="toggleColorPicker($event, preset)"
                                @mousedown.stop
                                @pointerdown.stop
                                @dragstart.stop.prevent
                                @keydown.esc.stop.prevent="closeColorPicker"
                            />
                            <button type="button" aria-label="Delete preset" title="Delete preset" class="text-stone-gray/55 hover:bg-red-400/10 hover:text-red-400 focus-visible:ring-red-400/60 shrink-0 rounded-md h-7 w-7 focus-visible:ring-2 focus-visible:outline-none flex items-center justify-center" @click.stop="emit('delete', preset.id)">
                                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </li>
        </ul>

        <Teleport to="body">
            <div
                v-if="activePreset"
                :id="`preset-color-picker-${activePreset.id}`"
                ref="colorPicker"
                role="dialog"
                :aria-label="`Accent color for ${activePreset.name}`"
                class="fixed z-50"
                :style="colorPickerPosition"
                @click.stop
                @mousedown.stop
                @pointerdown.stop
                @dragstart.stop.prevent
                @keydown.esc.stop.prevent="closeColorPicker"
            >
                <ChromePicker v-model="activeColor" disable-alpha :formats="['hex']" />
            </div>
        </Teleport>
    </aside>
</template>
