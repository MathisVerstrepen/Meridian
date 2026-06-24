<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import type { FileManagerSort } from '@/types/settings';

const settingsStore = useSettingsStore();
const { blockAttachmentSettings } = storeToRefs(settingsStore);

const fileManagerSortOptions = [
    { id: 'name_asc', name: 'Name A-Z' },
    { id: 'name_desc', name: 'Name Z-A' },
    { id: 'date_desc', name: 'Date newest first' },
    { id: 'date_asc', name: 'Date oldest first' },
    { id: 'size_desc', name: 'Size largest first' },
    { id: 'size_asc', name: 'Size smallest first' },
    { id: 'type_asc', name: 'Type A-Z' },
    { id: 'type_desc', name: 'Type Z-A' },
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
const uploadFolderEntry = SETTINGS_ENTRY.filesUploadFolder;
const defaultSortEntry = SETTINGS_ENTRY.filesDefaultSort;
const defaultViewEntry = SETTINGS_ENTRY.filesDefaultView;
const rememberSortEntry = SETTINGS_ENTRY.filesRememberLastSort;
const rememberViewEntry = SETTINGS_ENTRY.filesRememberLastView;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
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
