<script setup lang="ts">
import type { ToolCallArtifact } from '@/types/toolCall';
import GeneratedImageCard from '~/components/ui/chat/utils/generatedImageCard.vue';

const props = defineProps<{
    artifacts: ToolCallArtifact[];
}>();

const imageArtifacts = computed(() => {
    return props.artifacts.filter((artifact) => artifact.kind === 'image');
});

const fileArtifacts = computed(() => {
    return props.artifacts.filter((artifact) => artifact.kind !== 'image');
});
</script>

<template>
    <div v-if="props.artifacts.length" class="mt-4 space-y-4">
        <div v-if="imageArtifacts.length" class="space-y-2">
            <p class="text-stone-gray text-xs font-semibold tracking-wide uppercase">
                Generated images
            </p>
            <GeneratedImageCard
                v-for="artifact in imageArtifacts"
                :key="artifact.id"
                :prompt="artifact.relative_path || artifact.name"
                :image-url="`/api/files/view/${artifact.id}`"
            />
        </div>

        <div v-if="fileArtifacts.length" class="space-y-2">
            <p class="text-stone-gray text-xs font-semibold tracking-wide uppercase">
                Downloads
            </p>
            <div class="flex flex-wrap gap-2">
                <UiChatUtilsSandboxArtifactDownload
                    v-for="artifact in fileArtifacts"
                    :key="artifact.id"
                    :file-id="artifact.id"
                    :filename="artifact.name"
                    :label="artifact.relative_path || artifact.name"
                />
            </div>
        </div>
    </div>
</template>
