<script setup lang="ts">
import { HeadlessDialog, HeadlessDialogPanel, HeadlessDialogTitle, HeadlessMenu, HeadlessMenuButton, HeadlessMenuItems, HeadlessMenuItem } from '#components';
import { serializeTableRows, type TableCopyFormat } from '@/utils/tableClipboard';

const props = defineProps<{ table: HTMLTableElement | null }>();
const emit = defineEmits<{ close: [] }>();
const content = ref<HTMLElement | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);
const copyState = ref<'idle' | 'copying' | 'copied' | 'error'>('idle');
const { error: showError } = useToast();
const copyLabel = computed(() => copyState.value === 'copied' ? 'Table copied' : 'Copy table');
const formats: { value: TableCopyFormat; label: string }[] = [
    { value: 'markdown', label: 'Markdown' },
    { value: 'tsv', label: 'TSV' },
    { value: 'csv', label: 'CSV' },
];

watch(() => props.table, () => { copyState.value = 'idle'; });

const copyTable = async (format: TableCopyFormat) => {
    const snapshot = content.value?.querySelector('table');
    if (!snapshot || copyState.value === 'copying') return;
    copyState.value = 'copying';
    try {
        const rows = Array.from(snapshot.rows, (row) => Array.from(row.cells, (cell) => cell.innerText));
        await navigator.clipboard.writeText(serializeTableRows(rows, format));
        if (content.value?.querySelector('table') === snapshot) copyState.value = 'copied';
    } catch {
        if (content.value?.querySelector('table') !== snapshot) return;
        copyState.value = 'error';
        showError('Clipboard unavailable. Allow clipboard access and try again.', { title: 'Copy failed' });
    }
};

watch([content, () => props.table], ([mountpoint, table]) => {
    if (!mountpoint || !table) return;
    // Snapshot only already-rendered DOM, never reinterpret Markdown or decode escaped cell text.
    const snapshot = table.cloneNode(true);
    if (!(snapshot instanceof HTMLTableElement)) return;
    snapshot.removeAttribute('id');
    snapshot.querySelectorAll('[id]').forEach((element) => element.removeAttribute('id'));
    mountpoint.replaceChildren(snapshot);
}, { flush: 'post' });
</script>

<template>
    <HeadlessDialog
        :open="table !== null"
        :initial-focus="closeButton"
        class="fixed inset-0 z-120"
        @close="emit('close')"
    >
        <div class="fixed inset-0 bg-black/60" aria-hidden="true" />
        <div class="fixed inset-0 flex items-center justify-center p-4 sm:p-8">
            <HeadlessDialogPanel
                class="bg-obsidian text-soft-silk border-stone-gray/25 flex max-h-full w-max
                    min-w-0 max-w-full flex-col rounded-xl border shadow-2xl"
            >
                <div class="border-stone-gray/25 flex shrink-0 items-center justify-between gap-4
                    border-b px-5 py-3 sm:gap-8">
                    <HeadlessDialogTitle class="whitespace-nowrap font-semibold">Expanded table</HeadlessDialogTitle>
                    <div class="flex shrink-0 items-center gap-1">
                        <HeadlessMenu as="div" class="relative">
                            <HeadlessMenuButton
                                :aria-label="copyLabel"
                                :title="copyLabel"
                                class="hover:bg-stone-gray/20 focus-visible:ring-soft-silk/60 flex h-9 w-9
                                    items-center justify-center rounded-md focus-visible:ring-2"
                            >
                                <UiIcon
                                    :name="copyState === 'copied'
                                        ? 'MaterialSymbolsCheckSmallRounded'
                                        : 'MaterialSymbolsContentCopyOutlineRounded'"
                                    class="h-5 w-5"
                                />
                            </HeadlessMenuButton>
                            <HeadlessMenuItems
                                class="bg-obsidian border-stone-gray/25 absolute right-0 z-30 mt-1 w-36
                                    rounded-lg border p-1 shadow-xl focus:outline-none"
                            >
                                <HeadlessMenuItem
                                    v-for="format in formats"
                                    :key="format.value"
                                    v-slot="{ active }"
                                    :disabled="copyState === 'copying'"
                                >
                                    <button
                                        type="button"
                                        :class="active ? 'bg-stone-gray/20' : ''"
                                        class="w-full rounded-md px-3 py-2 text-left text-sm"
                                        @click="copyTable(format.value)"
                                    >
                                        {{ format.label }}
                                    </button>
                                </HeadlessMenuItem>
                            </HeadlessMenuItems>
                        </HeadlessMenu>
                        <span role="status" class="sr-only">
                            {{ copyState === 'copied' ? 'Table copied' : copyState === 'error' ? 'Copy failed. Clipboard unavailable.' : '' }}
                        </span>
                        <button
                            ref="closeButton"
                            type="button"
                            aria-label="Close expanded table"
                            class="hover:bg-stone-gray/20 focus-visible:ring-soft-silk/60 flex h-9 w-9
                                items-center justify-center rounded-md focus-visible:ring-2"
                            @click="emit('close')"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                        </button>
                    </div>
                </div>
                <div
                    ref="content"
                    role="region"
                    aria-label="Expanded table contents"
                    tabindex="0"
                    class="markdown-table markdown-table-expanded prose prose-invert custom_scroll
                        m-4 min-h-0 max-w-none overflow-auto sm:m-5"
                />
            </HeadlessDialogPanel>
        </div>
    </HeadlessDialog>
</template>
