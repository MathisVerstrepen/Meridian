<script lang="ts" setup>
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
        description: 'Sort folders and files alphabetically by name.',
    },
    {
        id: 'name_desc',
        name: 'Name Z-A',
        description: 'Sort folders and files in reverse alphabetical order.',
    },
    {
        id: 'date_desc',
        name: 'Date newest first',
        description: 'Show recently modified folders and files first.',
    },
    {
        id: 'date_asc',
        name: 'Date oldest first',
        description: 'Show oldest modified folders and files first.',
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
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: PDF Engine -->
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

        <!-- Setting: Default Upload Folder -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Upload Folder</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Specify the default folder where uploaded files will be stored when uploading
                    from devices. Folder will be created if it does not exist.
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
                <h3 class="text-soft-silk font-semibold">Default Sort</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the sort order used when the file manager opens.
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
                <h3 class="text-soft-silk font-semibold">Default View</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the layout used when the file manager opens.
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
                <h3 class="text-soft-silk font-semibold">Remember Last Sort</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Save manual sort changes in this browser and use them instead of the default.
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
                <h3 class="text-soft-silk font-semibold">Remember Last View</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Save manual view changes in this browser and use them instead of the default.
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
