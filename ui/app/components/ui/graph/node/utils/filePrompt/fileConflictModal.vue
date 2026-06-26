<script lang="ts" setup>
defineProps<{
    isOpen: boolean;
    title: string;
    description: string;
    conflicts: { name: string; type: 'file' | 'folder'; destination: string }[];
}>();

const emit = defineEmits<{
    (e: 'resolve', policy: FileConflictPolicy): void;
    (e: 'cancel'): void;
}>();
</script>

<template>
    <UiUtilsBaseModal
        :model-value="isOpen"
        :title="title"
        :description="description"
        icon="MdiAlertCircleOutline"
        size="md"
        z-index-class="z-100"
        @close="emit('cancel')"
    >

                <div
                    class="border-stone-gray/15 bg-stone-gray/5 dark-scrollbar mb-4 max-h-40 overflow-y-auto
                        rounded-xl border p-2"
                >
                    <div
                        v-for="conflict in conflicts.slice(0, 8)"
                        :key="`${conflict.destination}/${conflict.name}`"
                        class="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
                    >
                        <UiIcon
                            :name="conflict.type === 'folder' ? 'MdiFolderOutline' : 'MdiFileOutline'"
                            class="text-stone-gray/70 h-4 w-4 shrink-0"
                        />
                        <span class="truncate font-medium" :title="conflict.name">{{ conflict.name }}</span>
                        <span class="text-stone-gray/45 min-w-0 truncate text-xs">
                            in {{ conflict.destination }}
                        </span>
                    </div>
                    <p v-if="conflicts.length > 8" class="text-stone-gray/50 px-2 py-1 text-xs">
                        +{{ conflicts.length - 8 }} more conflict{{ conflicts.length - 8 === 1 ? '' : 's' }}
                    </p>
                </div>

                <div class="grid gap-2 sm:grid-cols-3">
                    <button
                        class="bg-red-500/10 text-red-300 hover:bg-red-500/15 rounded-xl px-3 py-2.5
                            text-left transition-colors ring-1 ring-red-500/20"
                        @click="emit('resolve', 'replace')"
                    >
                        <span class="block text-sm font-semibold">Replace</span>
                        <div class="text-xs text-red-200/70">Overwrite existing items.</div>
                    </button>
                    <button
                        class="bg-ember-glow/10 text-ember-glow hover:bg-ember-glow/15 rounded-xl px-3 py-2.5
                            text-left transition-colors ring-1 ring-ember-glow/25"
                        @click="emit('resolve', 'keep_both')"
                    >
                        <span class="block text-sm font-semibold">Keep both</span>
                        <div class="text-xs text-ember-glow/70">Rename incoming items.</div>
                    </button>
                    <button
                        class="bg-stone-gray/10 text-stone-gray/80 hover:bg-stone-gray/20 hover:text-soft-silk
                            rounded-xl px-3 py-2.5 text-left transition-colors ring-1 ring-stone-gray/15"
                        @click="emit('resolve', 'skip')"
                    >
                        <span class="block text-sm font-semibold">Skip</span>
                        <div class="text-xs text-stone-gray/60">Leave existing items as-is.</div>
                    </button>
                </div>

        <template #footer>
                    <button
                        class="text-stone-gray hover:text-soft-silk rounded-lg px-4 py-2 text-sm transition-colors"
                        @click="emit('cancel')"
                    >
                        Cancel operation
                    </button>
        </template>
    </UiUtilsBaseModal>
</template>
