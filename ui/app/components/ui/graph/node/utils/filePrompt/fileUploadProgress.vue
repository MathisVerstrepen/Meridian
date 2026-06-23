<script lang="ts" setup>
import { motion, AnimatePresence } from 'motion-v';

const props = defineProps<{
    isUploading: boolean;
    status: 'idle' | 'uploading' | 'completed' | 'completed_with_errors';
    totalFiles: number;
    completedFiles: number;
    failedFiles: number;
    currentFileName: string;
    currentFileProgress: number;
    errors: { name: string; message: string }[];
}>();

const emit = defineEmits<{
    (e: 'dismiss'): void;
}>();

const showErrors = ref(false);
let dismissTimer: ReturnType<typeof setTimeout> | null = null;

const visible = computed(() => props.status !== 'idle');
const isDone = computed(
    () => props.status === 'completed' || props.status === 'completed_with_errors',
);
const hasErrors = computed(() => props.status === 'completed_with_errors' && props.failedFiles > 0);
const processedFiles = computed(() => props.completedFiles + props.failedFiles);
const currentIndex = computed(() =>
    Math.min(processedFiles.value + (props.isUploading ? 1 : 0), props.totalFiles),
);

const displayProgress = computed(() => {
    if (props.totalFiles === 0) return 0;
    if (isDone.value) {
        return hasErrors.value
            ? (props.completedFiles / props.totalFiles) * 100
            : 100;
    }
    return Math.min(
        100,
        ((processedFiles.value + props.currentFileProgress / 100) / props.totalFiles) * 100,
    );
});

const progressLabel = computed(() => `${Math.round(displayProgress.value)}%`);

const headerIcon = computed(() => {
    if (props.status === 'uploading') return 'MaterialSymbolsProgressActivity';
    if (hasErrors.value) return 'MdiAlertCircle';
    return 'MaterialSymbolsCheckSmallRounded';
});

const clearDismissTimer = () => {
    if (dismissTimer) {
        clearTimeout(dismissTimer);
        dismissTimer = null;
    }
};

watch(
    () => props.status,
    (status) => {
        clearDismissTimer();
        showErrors.value = false;
        // Auto-dismiss only on a fully successful batch so the user keeps a
        // chance to review failures when something went wrong.
        if (status === 'completed') {
            dismissTimer = setTimeout(() => emit('dismiss'), 4000);
        }
    },
);

watch(
    () => props.isUploading,
    (uploading) => {
        if (uploading) clearDismissTimer();
    },
);

onBeforeUnmount(clearDismissTimer);
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-if="visible"
            class="bg-obsidian/95 border-stone-gray/20 dark-scrollbar w-full shrink-0 overflow-hidden
                rounded-xl border p-4 shadow-2xl backdrop-blur"
            :initial="{ opacity: 0, y: 16, scale: 0.96 }"
            :animate="{ opacity: 1, y: 0, scale: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
            :exit="{ opacity: 0, y: 16, scale: 0.96, transition: { duration: 0.15, ease: 'easeIn' } }"
        >
            <!-- Header -->
            <div class="mb-3 flex items-start justify-between gap-3">
                <div class="flex min-w-0 items-center gap-2.5">
                    <div
                        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                        :class="
                            hasErrors
                                ? 'bg-red-500/10'
                                : isDone
                                  ? 'bg-ember-glow/10'
                                  : 'bg-ember-glow/10'
                        "
                    >
                        <UiIcon
                            :name="headerIcon"
                            class="h-5 w-5"
                            :class="[
                                status === 'uploading' ? 'animate-spin text-ember-glow' : '',
                                hasErrors ? 'text-red-400' : 'text-ember-glow',
                            ]"
                        />
                    </div>
                    <div class="min-w-0">
                        <p class="text-soft-silk truncate text-sm font-semibold">
                            <template v-if="status === 'uploading'">Uploading files</template>
                            <template v-else-if="hasErrors">Upload finished</template>
                            <template v-else>Upload complete</template>
                        </p>
                        <p class="text-stone-gray/60 truncate text-xs">
                            <template v-if="status === 'uploading'">
                                {{ currentIndex }} of {{ totalFiles }}
                                <span v-if="currentFileName" class="text-stone-gray/40">·</span>
                                <span v-if="currentFileName" class="text-stone-gray/50">{{
                                    currentFileName
                                }}</span>
                            </template>
                            <template v-else-if="hasErrors">
                                {{ completedFiles }} uploaded · {{ failedFiles }} failed
                            </template>
                            <template v-else>
                                {{ completedFiles }}
                                file{{ completedFiles === 1 ? '' : 's' }} uploaded
                            </template>
                        </p>
                    </div>
                </div>
                <button
                    v-if="isDone"
                    class="text-stone-gray/60 hover:bg-stone-gray/10 hover:text-soft-silk -mr-1
                        -mt-1 rounded-lg p-1 transition-colors"
                    title="Dismiss"
                    @click="emit('dismiss')"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                </button>
            </div>

            <!-- Progress Bar -->
            <div class="bg-stone-gray/15 relative h-2 w-full overflow-hidden rounded-full">
                <div
                    class="h-full rounded-full transition-[width] duration-300 ease-out"
                    :class="hasErrors ? 'bg-red-400' : 'bg-ember-glow'"
                    :style="{ width: `${displayProgress}%` }"
                />
            </div>
            <div class="mt-1.5 flex items-center justify-between text-[11px]">
                <span class="text-stone-gray/50">
                    {{ processedFiles }} / {{ totalFiles }} processed
                </span>
                <span
                    class="font-semibold"
                    :class="hasErrors ? 'text-red-400' : 'text-ember-glow'"
                >
                    {{ progressLabel }}
                </span>
            </div>

            <!-- Error Details -->
            <div v-if="hasErrors" class="mt-3">
                <button
                    class="text-stone-gray/60 hover:text-soft-silk flex w-full items-center gap-1.5
                        text-xs font-medium transition-colors"
                    @click="showErrors = !showErrors"
                >
                    <UiIcon
                        name="LineMdChevronSmallUp"
                        class="h-3.5 w-3.5 transition-transform duration-200"
                        :class="showErrors ? '' : '-rotate-90'"
                    />
                    {{ showErrors ? 'Hide' : 'View' }} failed files ({{ failedFiles }})
                </button>
                <Transition
                    enter-active-class="transition duration-200 ease-out"
                    enter-from-class="opacity-0 -translate-y-1"
                    enter-to-class="opacity-100 translate-y-0"
                    leave-active-class="transition duration-150 ease-in"
                    leave-from-class="opacity-100 translate-y-0"
                    leave-to-class="opacity-0 -translate-y-1"
                >
                    <div
                        v-if="showErrors"
                        class="dark-scrollbar mt-2 max-h-32 space-y-1.5 overflow-y-auto pr-1"
                    >
                        <div
                            v-for="(entry, index) in errors"
                            :key="index"
                            class="border-stone-gray/10 bg-red-500/5 rounded-lg border px-2.5 py-1.5"
                        >
                            <p class="text-soft-silk truncate text-xs font-medium" :title="entry.name">
                                {{ entry.name }}
                            </p>
                            <p class="text-red-400/80 truncate text-[11px]" :title="entry.message">
                                {{ entry.message }}
                            </p>
                        </div>
                    </div>
                </Transition>
            </div>
        </motion.div>
    </AnimatePresence>
</template>
