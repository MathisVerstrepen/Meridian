<script lang="ts" setup>
import type { Workspace } from '@/types/graph';
import { useEventListener } from '@vueuse/core';

const props = defineProps<{
    workspaces: Workspace[];
    activeId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', id: string): void;
}>();

const workspaceTitle = (workspace: Workspace, index: number) => {
    const directShortcut = index < 9 ? `Alt+${index + 1}; ` : '';
    return `${workspace.name} (${directShortcut}Alt+PageUp / Alt+PageDown)`;
};

useEventListener('keydown', (event: KeyboardEvent) => {
    if (
        props.workspaces.length <= 1 ||
        event.defaultPrevented ||
        event.isComposing ||
        event.repeat ||
        !event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.getModifierState('AltGraph')
    )
        return;

    if (
        event.target instanceof HTMLElement &&
        event.target.closest(
            'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]',
        )
    )
        return;

    let index: number;
    if (event.key === 'PageUp' || event.key === 'PageDown') {
        const currentIndex = props.workspaces.findIndex((ws) => ws.id === props.activeId);
        if (currentIndex < 0) return;
        index = Math.max(
            0,
            Math.min(
                props.workspaces.length - 1,
                currentIndex + (event.key === 'PageDown' ? 1 : -1),
            ),
        );
    } else {
        const digit = /^Digit([1-9])$/.exec(event.code)?.[1] ?? event.key;
        if (!/^[1-9]$/.test(digit)) return;
        index = Number(digit) - 1;
    }

    const workspace = props.workspaces[index];
    if (!workspace) return;
    event.preventDefault();
    if (workspace.id !== props.activeId) emit('select', workspace.id);
});
</script>

<template>
    <div v-if="workspaces.length > 1" class="mt-3 mb-2 shrink-0">
        <div
            role="group"
            aria-label="Workspaces"
            class="flex w-full items-center gap-2"
            @wheel.stop
        >
            <button
                v-for="(ws, index) in workspaces"
                :key="ws.id"
                :data-id="ws.id"
                type="button"
                :aria-pressed="ws.id === activeId"
                class="focus-visible:ring-ember-glow flex h-9 min-w-0 flex-1 cursor-pointer
                    items-center justify-center rounded-lg border px-3 text-sm font-semibold
                    transition-colors focus-visible:ring-2 focus-visible:outline-none
                    focus-visible:ring-inset"
                :class="
                    ws.id === activeId
                        ? 'border-ember-glow/40 bg-ember-glow/15 text-ember-glow'
                        : `bg-stone-gray/5 text-stone-gray/70 hover:bg-stone-gray/10
                            hover:text-stone-gray border-transparent`
                "
                :title="workspaceTitle(ws, index)"
                :aria-keyshortcuts="index < 9 ? `Alt+${index + 1}` : undefined"
                @click="emit('select', ws.id)"
            >
                <span class="truncate">{{ ws.name }}</span>
            </button>
        </div>
    </div>
</template>
