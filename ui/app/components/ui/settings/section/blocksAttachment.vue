<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import type { PDFEngine } from '@/types/enums';
import type { FileManagerSort } from '@/types/settings';

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

const fileManagerSortOptions = [
    {
        id: 'name_asc',
        name: 'Name A-Z',
    },
    {
        id: 'name_desc',
        name: 'Name Z-A',
    },
    {
        id: 'date_desc',
        name: 'Date newest first',
    },
    {
        id: 'date_asc',
        name: 'Date oldest first',
    },
    {
        id: 'size_desc',
        name: 'Size largest first',
    },
    {
        id: 'size_asc',
        name: 'Size smallest first',
    },
    {
        id: 'type_asc',
        name: 'Type A-Z',
    },
    {
        id: 'type_desc',
        name: 'Type Z-A',
    },
];

const fileManagerViewOptions = [
    {
        id: 'grid',
        name: 'Grid',
        description: 'Compact tiles for browsing mixed files.',
    },
    {
        id: 'gallery',
        name: 'Gallery',
        description: 'Larger previews for image-heavy folders.',
    },
    {
        id: 'list',
        name: 'List',
        description: 'Dense rows with file metadata.',
    },
];
const pdfEngineEntry = SETTINGS_ENTRY.filesPdfEngine;
const uploadFolderEntry = SETTINGS_ENTRY.filesUploadFolder;
const defaultSortEntry = SETTINGS_ENTRY.filesDefaultSort;
const defaultViewEntry = SETTINGS_ENTRY.filesDefaultView;
const rememberSortEntry = SETTINGS_ENTRY.filesRememberLastSort;
const rememberViewEntry = SETTINGS_ENTRY.filesRememberLastView;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: PDF Engine -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ pdfEngineEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ pdfEngineEntry.description }}
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

        <!-- Setting: Default Upload Folder -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ uploadFolderEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ uploadFolderEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <input
                    id="default-upload-folder"
                    v-model="blockAttachmentSettings.default_upload_folder"
                    placeholder="default: uploads"
                    type="text"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow dark-scrollbar w-72 rounded-xl border-2 px-3 py-2
                        transition-colors duration-200 ease-in-out outline-none focus:border-2"
                />
            </div>
        </div>

        <!-- Setting: Default Sort -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ defaultSortEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ defaultSortEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    :item-list="fileManagerSortOptions"
                    :selected="blockAttachmentSettings.file_manager_default_sort"
                    @update:item-value="
                        (value: FileManagerSort) => {
                            blockAttachmentSettings.file_manager_default_sort = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Default View -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ defaultViewEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ defaultViewEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    :item-list="fileManagerViewOptions"
                    :selected="blockAttachmentSettings.file_manager_default_view"
                    @update:item-value="
                        (value: ViewMode) => {
                            blockAttachmentSettings.file_manager_default_view = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Remember Last Sort -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ rememberSortEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ rememberSortEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="file-manager-remember-last-sort"
                    :state="blockAttachmentSettings.file_manager_remember_last_sort"
                    :set-state="
                        (value: boolean) => {
                            blockAttachmentSettings.file_manager_remember_last_sort = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Remember Last View -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ rememberViewEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ rememberViewEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="file-manager-remember-last-view"
                    :state="blockAttachmentSettings.file_manager_remember_last_view"
                    :set-state="
                        (value: boolean) => {
                            blockAttachmentSettings.file_manager_remember_last_view = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
