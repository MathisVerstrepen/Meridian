<script lang="ts" setup>
import type { RepoContent } from '@/types/github';

defineProps<{ context: RepoContent }>();
defineEmits<{ (e: 'remove'): void }>();
</script>

<template>
    <li
        class="bg-stone-gray/10 border-stone-gray/10 text-soft-silk/80 flex max-w-full items-center
            gap-2 rounded-xl border px-3 py-2 text-sm"
    >
        <UiIcon
            :name="context.repo.provider.startsWith('gitlab') ? 'MdiGitlab' : 'MdiGithub'"
            class="h-5 w-5 shrink-0"
        />
        <span class="truncate font-semibold">{{ context.repo.full_name }}</span>
        <span class="text-stone-gray/60 shrink-0">{{ context.currentBranch }}</span>
        <span class="text-stone-gray/60 shrink-0">
            {{ context.selectedFiles.length }} file(s),
            {{ context.selectedIssues?.length ?? 0 }} issue(s)
        </span>
        <button
            type="button"
            :aria-label="`Remove Git context for ${context.repo.full_name}`"
            class="hover:bg-stone-gray/20 ml-auto flex h-6 w-6 shrink-0 cursor-pointer items-center
                justify-center rounded-full"
            @click="$emit('remove')"
        >
            <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
        </button>
    </li>
</template>
