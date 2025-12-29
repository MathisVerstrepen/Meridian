<script lang="ts" setup>
import type { ExtractedIssue } from '@/types/github';

const props = defineProps<{
    issue: ExtractedIssue;
}>();

const iconName = computed(() =>
    props.issue.type === 'Pull Request' ? 'MdiSourcePull' : 'MdiAlertCircleOutline',
);

const stateClass = computed(() => {
    if (props.issue.state === 'open') return 'text-green-500';
    if (props.issue.type === 'Pull Request') return 'text-purple-500';
    return 'text-stone-gray/60';
});
</script>

<template>
    <a
        :href="issue.url"
        target="_blank"
        rel="noopener noreferrer"
        class="border-stone-gray/25 hover:bg-obsidian/80 bg-obsidian/50 flex items-center rounded-lg
            border px-2 py-1 text-xs font-bold no-underline transition-colors"
        :title="issue.title"
    >
        <UiIcon :name="iconName" class="mr-2 h-4 w-4" :class="stateClass" />
        <span class="text-stone-gray/80">
            #{{ issue.number }} -
            {{ issue.title.length > 50 ? issue.title.substring(0, 47) + '...' : issue.title }}
        </span>
    </a>
</template>
