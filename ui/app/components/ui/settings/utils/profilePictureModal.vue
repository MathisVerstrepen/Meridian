<script lang="ts" setup>
import 'cropperjs/dist/cropper.css';
import VueCropper from 'vue-cropperjs';
import { motion } from 'motion-v';

// --- Emits ---
const emit = defineEmits(['close', 'upload-success']);

// --- Composables ---
const { uploadAvatar } = useAPI();
const { success, error } = useToast();

// --- State ---
const cropper = ref<InstanceType<typeof VueCropper> | null>(null);
const imageSrc = ref<string | null>(null);
const previewUrl = ref<string | null>(null);
const isDragging = ref(false);
const isLoading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

// --- Methods ---
const handleFileChange = (event: Event) => {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
        const file = input.files[0];
        if (!file.type.startsWith('image/')) {
            error('Please select an image file.', { title: 'Invalid File' });
            return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            imageSrc.value = e.target?.result as string;
        };
        reader.readAsDataURL(file);
    }
};

const triggerFileInput = () => {
    fileInput.value?.click();
};

const handleDrop = (event: DragEvent) => {
    isDragging.value = false;
    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
        const file = event.dataTransfer.files[0];
        if (!file.type.startsWith('image/')) {
            error('Please select an image file.', { title: 'Invalid File' });
            return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            imageSrc.value = e.target?.result as string;
        };
        reader.readAsDataURL(file);
    }
};

const updatePreview = () => {
    if (cropper.value) {
        previewUrl.value = cropper.value.getCroppedCanvas().toDataURL();
    }
};

const saveAndUpload = () => {
    if (!cropper.value) return;
    isLoading.value = true;
    cropper.value
        .getCroppedCanvas({
            width: 256, // Save a reasonably sized image
            height: 256,
            imageSmoothingQuality: 'high',
        })
        .toBlob(
            async (blob: Blob | null) => {
                if (!blob) {
                    error('Could not process image.', { title: 'Upload Error' });
                    isLoading.value = false;
                    return;
                }
                const formData = new FormData();
                formData.append('file', blob, 'avatar.png');

                try {
                    await uploadAvatar(formData);
                    success('Profile picture updated successfully!', { title: 'Success' });
                    emit('upload-success');
                } catch (err) {
                    console.error('Avatar upload failed:', err);
                    error('Failed to upload profile picture.', { title: 'Upload Error' });
                } finally {
                    isLoading.value = false;
                }
            },
            'image/png',
            0.9,
        );
};
</script>

<template>
    <Teleport to="body">
        <div
            class="bg-obsidian/10 fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur"
            @click.self="emit('close')"
        >
            <AnimatePresence>
                <motion.div
                    :initial="{ opacity: 0, scale: 0.85 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        transition: { duration: 0.2, ease: 'easeOut' },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.85,
                        transition: { duration: 0.15, ease: 'easeIn' },
                    }"
                    class="bg-obsidian/60 border-stone-gray/10 relative w-full max-w-2xl rounded-2xl border-2 shadow-2xl"
                >
                    <!-- Header -->
                    <div
                        class="border-stone-gray/10 flex items-center justify-between border-b-2 px-6 py-3"
                    >
                        <h2 class="text-soft-silk text-lg font-bold">Update Profile Picture</h2>
                        <button
                            class="text-stone-gray hover:text-soft-silk hover:bg-stone-gray/10 cursor-pointer rounded-full p-1
                                transition-colors focus:outline-none"
                            @click="emit('close')"
                        >
                            <UiIcon name="MaterialSymbolsClose" class="h-6 w-6" />
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="p-6">
                        <div v-if="!imageSrc" class="flex flex-col items-center">
                            <input
                                ref="fileInput"
                                type="file"
                                class="hidden"
                                accept="image/*"
                                @change="handleFileChange"
                            />
                            <div
                                class="border-stone-gray/40 bg-anthracite/20 flex h-64 w-full cursor-pointer flex-col items-center
                                    justify-center rounded-lg border-2 border-dashed transition-colors"
                                :class="{ 'border-ember-glow': isDragging }"
                                @click="triggerFileInput"
                                @dragover.prevent="isDragging = true"
                                @dragleave.prevent="isDragging = false"
                                @drop.prevent="handleDrop"
                            >
                                <UiIcon
                                    name="MaterialSymbolsImageRounded"
                                    class="text-soft-silk/10 h-16 w-16"
                                />
                                <p class="text-stone-gray mt-4">
                                    <span class="text-ember-glow/80 font-semibold"
                                        >Click to upload</span
                                    >
                                    or drag and drop
                                </p>
                                <p class="text-stone-gray/60 text-sm">
                                    PNG, JPG, or WEBP (max 4MB)
                                </p>
                            </div>
                        </div>

                        <div v-else class="grid grid-cols-2 gap-6">
                            <div>
                                <h3 class="text-stone-gray mb-2 text-sm font-semibold">
                                    Crop Image
                                </h3>
                                <div
                                    class="bg-anthracite/20 h-64 w-full overflow-hidden rounded-lg"
                                >
                                    <VueCropper
                                        ref="cropper"
                                        :src="imageSrc"
                                        :aspect-ratio="1"
                                        :view-mode="1"
                                        drag-mode="move"
                                        :auto-crop-area="0.8"
                                        :background="false"
                                        class="h-full w-full"
                                        :cropend="updatePreview"
                                        :ready="updatePreview"
                                    />
                                </div>
                            </div>
                            <div>
                                <h3 class="text-stone-gray mb-2 text-sm font-semibold">Preview</h3>
                                <div
                                    class="border-stone-gray/20 bg-anthracite/20 flex h-64 w-full items-center justify-center rounded-lg border"
                                >
                                    <img
                                        v-if="previewUrl"
                                        :src="previewUrl"
                                        alt="Avatar Preview"
                                        class="h-40 w-40 rounded-full object-cover"
                                    />
                                    <div
                                        v-else
                                        class="bg-obsidian flex h-40 w-40 items-center justify-center rounded-full"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsImageRounded"
                                            class="text-stone-gray/50 h-16 w-16"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="border-stone-gray/10 flex justify-end gap-4 border-t-2 px-6 py-4">
                        <button
                            class="hover:bg-stone-gray/10 text-soft-silk border-stone-gray/20 rounded-lg border-2 px-4 py-2 text-sm
                                font-bold transition-colors"
                            @click="emit('close')"
                        >
                            Cancel
                        </button>
                        <button
                            class="bg-ember-glow/80 hover:bg-ember-glow text-soft-silk rounded-lg px-4 py-2 text-sm font-bold
                                transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                            :disabled="!imageSrc || isLoading"
                            @click="saveAndUpload"
                        >
                            <span v-if="isLoading">Uploading...</span>
                            <span v-else>Save</span>
                        </button>
                    </div>
                </motion.div>
            </AnimatePresence>
        </div>
    </Teleport>
</template>
