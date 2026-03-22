<script setup lang="ts">
const props = withDefaults(
    defineProps<{
        fileId: string;
        label: string;
        filename?: string;
        compact?: boolean;
    }>(),
    {
        filename: '',
        compact: false,
    },
);

const { getFileBlob } = useAPI();
const { error } = useToast();

const isDownloading = ref(false);

const triggerDownload = async () => {
    if (!props.fileId || isDownloading.value) {
        return;
    }

    isDownloading.value = true;

    try {
        const blob = await getFileBlob(props.fileId);
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = props.filename || props.label || 'download';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        console.error(err);
        error('Failed to download file.');
    } finally {
        isDownloading.value = false;
    }
};
</script>

<template>
    <button
        class="inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-left
            transition-colors duration-200"
        :class="
            props.compact
                ? 'border-stone-gray/15 bg-stone-gray/10 text-soft-silk hover:bg-stone-gray/20 text-sm'
                : 'border-stone-gray/15 bg-obsidian text-soft-silk hover:bg-obsidian/80 text-sm font-medium'
        "
        type="button"
        @click="triggerDownload"
    >
        <UiIcon
            :name="isDownloading ? 'MaterialSymbolsProgressActivity' : 'UilDownloadAlt'"
            class="h-4 w-4 shrink-0"
            :class="{ 'animate-spin': isDownloading }"
        />
        <span class="min-w-0 truncate">{{ label }}</span>
    </button>
</template>
