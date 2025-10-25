<script lang="ts" setup>
import type { DataTextToText } from '@/types/graph';
import { ToolEnum } from '@/types/enums';

const props = defineProps<{
    data: DataTextToText;
}>();
</script>

<template>
    <div class="flex gap-1">
        <div
            v-if="props.data.selectedTools?.includes(ToolEnum.WEB_SEARCH)"
            class="bg-soft-silk/10 text-soft-silk/80 flex -translate-y-0.5 items-center rounded-lg
                p-1"
            title="Web Search Enabled"
        >
            <UiIcon name="MdiWeb" class="h-5 w-5" />
        </div>
        <div
            v-if="props.data.selectedTools?.includes(ToolEnum.LINK_EXTRACTION)"
            class="bg-soft-silk/10 text-soft-silk/80 flex -translate-y-0.5 items-center rounded-lg
                p-1"
            title="Link Extraction Enabled"
        >
            <UiIcon name="MdiLinkVariant" class="h-5 w-5" />
        </div>
    </div>
</template>

<style scoped></style>
