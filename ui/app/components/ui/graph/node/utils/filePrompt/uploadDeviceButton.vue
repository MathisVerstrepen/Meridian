<script lang="ts" setup>
const props = defineProps<{
    files: FileSystemObject[];
}>();
const emit = defineEmits<{
    (e: 'updateNodeInternals'): void;
    (e: 'add-file', newFiles: FileList): Promise<void>;
}>();
</script>

<template>
    <label
        class="group nodrag bg-dried-heather-dark/40 text-stone-gray/50 hover:text-stone-gray
            border-dried-heather-dark/80 hover:border-dried-heather-dark relative flex h-full w-full
            cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl border-2
            border-dashed p-1 duration-300 ease-in-out"
    >
        <div
            class="text-soft-silk/50 group-hover:text-soft-silk/80 relative z-10 flex items-center gap-2 text-center
                transition-colors"
            :class="{
                'flex-col': props.files.length === 0,
            }"
        >
            <UiIcon name="UilUpload" class="h-5 w-5" />
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
                    >from device</span
                >
            </div>
            <input
                type="file"
                multiple
                accept=".pdf,image/*"
                class="hidden"
                @change="
                    async (e) => {
                        const target = e.target as HTMLInputElement;
                        if (target.files) {
                            emit('add-file', target.files);
                            emit('updateNodeInternals');
                        }
                    }
                "
            />
        </div>
    </label>
</template>

<style scoped></style>
