<script lang="ts" setup>
const props = defineProps<{
    files: FileSystemObject[];
    nodeId: string;
}>();

// --- Composables ---
const graphEvents = useGraphEvents();

const openCloudFileSelect = () => {
    graphEvents.emit('open-attachment-select', {
        nodeId: props.nodeId,
        selectedFiles: props.files
    });
};
</script>

<template>
    <button
        class="group nodrag bg-dried-heather-dark/40 text-stone-gray/50 hover:text-stone-gray
            border-dried-heather-dark/80 hover:border-dried-heather-dark relative flex h-full w-full
            cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl border-2
            border-dashed p-1 duration-300 ease-in-out"
        @click.prevent="openCloudFileSelect"
    >
        <div
            class="text-soft-silk/50 group-hover:text-soft-silk/80 relative z-10 flex items-center gap-2 text-center
                transition-colors"
                                    :class="{
                        'flex-col': props.files.length === 0,
                    }"
        >
            <UiIcon name="MdiCloudUploadOutline" class="h-5 w-5" />
            <div class="flex flex-col">
                <span
                    class="font-semibold"
                    :class="{
                        'text-sm': props.files.length !== 0,
                    }"
                    >Select Files</span
                >
                <span
                    class="text-xs"
                    :class="{
                        'text-[10px]': props.files.length !== 0,
                    }"
                    >from cloud</span
                >
            </div>
        </div>
    </button>
</template>

<style scoped></style>
