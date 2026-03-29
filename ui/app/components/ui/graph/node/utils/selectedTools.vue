<script lang="ts" setup>
import type { DataRouting, DataTextToText } from '@/types/graph';
import { ToolEnum } from '@/types/enums';

const props = defineProps<{
    data: DataTextToText | DataRouting;
    theme?: 'light' | 'dark';
}>();
</script>

<template>
    <div class="flex gap-1">
        <div
            v-if="props.data.autoSelectTools"
            class="flex -translate-y-0.5 items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Automatic tool selection enabled"
        >
            <UiIcon name="MynauiSparklesSolid" class="h-4 w-4" />
            Auto
        </div>
        <div
            v-if="!props.data.autoSelectTools && props.data.selectedTools?.includes(ToolEnum.WEB_SEARCH)"
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Web Search Enabled"
        >
            <UiIcon name="MdiWeb" class="h-5 w-5" />
        </div>
        <div
            v-if="
                !props.data.autoSelectTools &&
                props.data.selectedTools?.includes(ToolEnum.LINK_EXTRACTION)
            "
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Link Extraction Enabled"
        >
            <UiIcon name="MdiLinkVariant" class="h-5 w-5" />
        </div>
        <div
            v-if="
                !props.data.autoSelectTools &&
                props.data.selectedTools?.includes(ToolEnum.IMAGE_GENERATION)
            "
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Image Generation Enabled"
        >
            <UiIcon name="MdiImageMultipleOutline" class="h-4.5 w-4.5" />
        </div>
        <div
            v-if="
                !props.data.autoSelectTools && props.data.selectedTools?.includes(ToolEnum.EXECUTE_CODE)
            "
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Code Execution Enabled"
        >
            <UiIcon name="MaterialSymbolsTerminalRounded" class="h-4.5 w-4.5" />
        </div>
        <div
            v-if="!props.data.autoSelectTools && props.data.selectedTools?.includes(ToolEnum.VISUALISE)"
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Visualise Enabled"
        >
            <UiIcon name="MaterialSymbolsBarChartRounded" class="h-4.5 w-4.5" />
        </div>
        <div
            v-if="!props.data.autoSelectTools && props.data.selectedTools?.includes(ToolEnum.ASK_USER)"
            class="flex -translate-y-0.5 items-center rounded-lg p-1"
            :class="{
                'bg-soft-silk/10 text-soft-silk/80': props.theme === 'dark',
                'bg-obsidian/10 text-obsidian/80': props.theme === 'light',
            }"
            title="Ask User Enabled"
        >
            <UiIcon name="LucideMessageCircleDashed" class="h-4.5 w-4.5" />
        </div>
    </div>
</template>

<style scoped></style>
