<script lang="ts" setup>
import { FileType } from '@/types/enums';

defineEmits<{
    (e: 'removeFile' | 'open-cloud-select'): void;
    (e: 'add-files', files: FileList): void;
}>();

// --- Props ---
const props = withDefaults(defineProps<{
    file: FileSystemObject;
    removeFiles: boolean;
    showImagePreview?: boolean;
}>(), {
    showImagePreview: false,
});

// --- Composables ---
const { getFileType } = useFiles();

const isImageFile = computed(() => {
    if (props.file.type !== 'file') return false;

    const contentType = props.file.content_type?.toLowerCase().split(';')[0]?.trim();
    if (contentType?.startsWith('image/')) return true;

    return /\.(?:avif|bmp|gif|jpe?g|png|svg|webp)$/i.test(props.file.name);
});

const imagePreviewUrl = computed(
    () => `/api/auth/refresh/files/view/${props.file.id}?size=160x160`,
);

const isPreviewImage = computed(() => props.showImagePreview && isImageFile.value);
</script>

<template>
    <li
        v-if="file"
        :key="file.id"
        class="text-soft-silk/70 relative flex items-center text-sm font-bold transition-colors
            duration-200"
        :class="
            isPreviewImage
                ? 'group h-14 w-14 rounded-lg'
                : 'border-stone-gray/30 rounded-xl border py-1.5 pr-1.5 pl-3'
        "
    >
        <img
            v-if="isPreviewImage"
            :src="imagePreviewUrl"
            alt=""
            width="56"
            height="56"
            class="h-14 w-14 rounded-lg object-cover"
        >
        <template v-else>
            <template v-for="fileType in [getFileType(file.name)]" :key="fileType">
                <UiIcon
                    v-if="fileType === FileType.Other"
                    class="h-5 w-5"
                    name="BxBxsFileBlank"
                />
                <UiIcon
                    v-else-if="fileType === FileType.PDF"
                    class="h-5 w-5"
                    name="BxBxsFilePdf"
                />
                <UiIcon
                    v-else-if="fileType === FileType.Image"
                    class="h-5 w-5"
                    name="MaterialSymbolsImageRounded"
                />
            </template>
        </template>
        <span v-if="!isPreviewImage" class="px-2">
            {{ file.name.length > 20 ? file.name.slice(0, 20) + '…' : file.name }}
        </span>
        <button
            v-if="removeFiles"
            type="button"
            :aria-label="`Remove ${file.name}`"
            class="flex cursor-pointer items-center justify-center transition-all duration-200
                focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-soft-silk/70"
            :class="{
                'text-soft-silk/70 hover:text-soft-silk bg-stone-gray/10 hover:bg-stone-gray/10 h-5 w-5 rounded-lg':
                    !isPreviewImage,
                'pointer-events-none absolute top-1 right-1 h-6 w-6 rounded-full border opacity-0 shadow-md':
                    isPreviewImage,
                'border-soft-silk/40 bg-obsidian/90 text-soft-silk': isPreviewImage,
                'group-hover:pointer-events-auto group-hover:opacity-100 group-hover:shadow-lg':
                    isPreviewImage,
                'group-hover:border-soft-silk/60 group-hover:bg-obsidian': isPreviewImage,
                'group-focus-within:pointer-events-auto group-focus-within:opacity-100':
                    isPreviewImage,
                'focus:pointer-events-auto focus:opacity-100 focus:shadow-lg': isPreviewImage,
            }"
            @click="$emit('removeFile')"
        >
            <UiIcon class="h-4 w-4" name="MaterialSymbolsClose" />
        </button>
    </li>
</template>

<style scoped></style>
