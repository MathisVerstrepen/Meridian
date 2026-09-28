<script setup lang="ts">
import type {
    AttachmentCollision,
    AttachmentCollisionChoice,
} from '@/composables/useAttachmentUploads';

const props = defineProps<{ collision: AttachmentCollision }>();
const emit = defineEmits<{ resolve: [choice: AttachmentCollisionChoice] }>();
const content = ref<HTMLElement | null>(null);
const previews = ref<{
    label: string;
    src: string;
    status: 'loading' | 'ready' | 'error';
}[]>([]);
let incomingUrl: string | null = null;
let previousFocus: HTMLElement | null = null;
let dialog: Element | null = null;

const isImage = (name: string, type?: string | null) => {
    const mime = type?.toLowerCase().split(';')[0]?.trim();
    return mime ? mime.startsWith('image/') : /\.(?:avif|bmp|gif|jpe?g|png|svg|webp)$/i.test(name);
};

const releasePreview = () => {
    if (incomingUrl) URL.revokeObjectURL(incomingUrl);
    incomingUrl = null;
    previews.value = [];
};

const resolve = (choice: AttachmentCollisionChoice) => {
    releasePreview();
    emit('resolve', choice);
};

const trapFocus = (event: Event) => {
    if (!(event instanceof KeyboardEvent) || event.key !== 'Tab') return;
    const buttons = dialog?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)');
    const first = buttons?.[0];
    const last = buttons?.[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
    }
};

onMounted(() => {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog = content.value?.closest('[role="dialog"]') ?? null;
    dialog?.addEventListener('keydown', trapFocus);
    dialog?.querySelector<HTMLButtonElement>('button[aria-label="Close modal"]')?.focus();

    watch(() => props.collision, ({ existing, incoming }) => {
        releasePreview();
        if (existing.type !== 'file'
            || !isImage(existing.name, existing.content_type)
            || !isImage(incoming.name, incoming.type)) return;

        try {
            incomingUrl = URL.createObjectURL(incoming);
        } catch {
            // Preview failure must never prevent the user from resolving the collision.
        }
        previews.value = [
            {
                label: 'Already uploaded',
                src: `/api/auth/refresh/files/view/${encodeURIComponent(existing.id)}`,
                status: 'loading',
            },
            {
                label: 'Incoming upload',
                src: incomingUrl ?? '',
                status: incomingUrl ? 'loading' : 'error',
            },
        ];
    }, { immediate: true });
});

onBeforeUnmount(() => {
    releasePreview();
    dialog?.removeEventListener('keydown', trapFocus);
    if (previousFocus?.isConnected) previousFocus.focus();
});
</script>

<template>
    <UiUtilsBaseModal
        :model-value="true"
        title="An item with this name already exists"
        icon="MdiAlertCircleOutline"
        size="md"
        z-index-class="z-100"
        panel-class="flex max-h-[calc(100dvh-2rem)] flex-col"
        header-class="shrink-0"
        body-class="min-h-0 overflow-y-auto p-5"
        @close="resolve(null)"
    >
        <p ref="content" class="text-soft-silk text-sm font-medium wrap-anywhere">
            {{ collision.existing.name }} in {{ collision.destination }}
        </p>
        <p class="text-stone-gray mt-2 text-sm">
            {{
                collision.existing.type === 'file'
                    ? 'Only the name matches. The existing file may have different contents.'
                    : 'The existing item is a folder and cannot be attached. Upload with rename to keep both.'
            }}
        </p>
        <div v-if="previews.length" class="mt-4 grid grid-cols-2 gap-3">
            <figure v-for="preview in previews" :key="preview.src || preview.label" class="min-w-0">
                <figcaption class="text-soft-silk mb-2 text-sm font-medium">
                    {{ preview.label }}
                </figcaption>
                <div class="bg-stone-gray/10 relative flex aspect-square max-h-60 items-center justify-center overflow-hidden rounded-lg">
                    <img
                        v-if="preview.status !== 'error'"
                        :src="preview.src"
                        :alt="`${preview.label}: ${collision.existing.name}`"
                        class="absolute inset-0 h-full w-full object-contain"
                        :class="{ 'opacity-0': preview.status === 'loading' }"
                        @load="preview.status = 'ready'"
                        @error="preview.status = 'error'"
                    >
                    <span v-if="preview.status === 'loading'" class="sr-only" role="status">
                        Loading {{ preview.label.toLowerCase() }} preview
                    </span>
                    <span v-else-if="preview.status === 'error'" class="text-stone-gray p-3 text-center text-sm" role="status">
                        Preview unavailable
                    </span>
                </div>
            </figure>
        </div>
        <div class="mt-5 flex flex-col gap-2 sm:flex-row">
            <button
                type="button"
                :disabled="collision.existing.type !== 'file'"
                class="bg-ember-glow text-obsidian hover:bg-ember-glow/90
                    focus-visible:outline-ember-glow min-h-11 rounded-xl px-4 py-2 text-sm
                    font-semibold focus-visible:outline-2 focus-visible:outline-offset-2
                    disabled:cursor-not-allowed disabled:opacity-40"
                @click="resolve('reuse')"
            >
                Use already uploaded file
            </button>
            <button
                type="button"
                class="border-stone-gray/40 text-soft-silk hover:bg-stone-gray/10
                    focus-visible:outline-ember-glow min-h-11 rounded-xl border px-4 py-2 text-sm
                    font-semibold focus-visible:outline-2 focus-visible:outline-offset-2"
                @click="resolve('keep_both')"
            >
                Upload with rename
            </button>
        </div>
    </UiUtilsBaseModal>
</template>
