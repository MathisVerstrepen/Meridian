<script lang="ts" setup>
import type { PDFEngine } from '@/types/enums';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { blockAttachmentSettings } = storeToRefs(settingsStore);

const pdfEnginesOptions = [
    {
        id: 'default',
        name: 'Default',
        description:
            'Default first to the model’s native file processing capabilities, and if that’s not available, we will use the "mistral-ocr" engine.',
    },
    {
        id: 'mistral-ocr',
        name: 'mistral-ocr',
        description: 'Best for scanned documents or PDFs with images ($2 per 1,000 pages).',
    },
    {
        id: 'pdf-text',
        name: 'pdf-text',
        description: 'Best for well-structured PDFs with clear text content (Free).',
    },
    {
        id: 'native',
        name: 'native',
        description:
            'Only available for models that support file input natively (charged as input tokens).',
    },
];
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">PDF Engine</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the default PDF engine for document processing.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    :item-list="pdfEnginesOptions"
                    :selected="blockAttachmentSettings.pdf_engine"
                    @update:item-value="
                        (value: PDFEngine) => {
                            blockAttachmentSettings.pdf_engine = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
