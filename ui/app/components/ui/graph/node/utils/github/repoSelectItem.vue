<script lang="ts" setup>
import type { RepositoryInfo } from '@/types/github';

const props = defineProps<{
    repo: RepositoryInfo;
}>();

const providerIcon = computed(() => {
    return props.repo.provider.startsWith('gitlab') ? 'MdiGitlab' : 'MdiGithub';
});

const instanceName = computed(() => {
    if (props.repo.provider.startsWith('gitlab:')) {
        try {
            const url = new URL(props.repo.provider.split(':', 2)[1]);
            return url.hostname;
        } catch {
            return 'GitLab';
        }
    }
    return null;
});
</script>

<template>
    <div class="flex grow items-center justify-between overflow-hidden">
        <div class="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
            <div
                class="bg-stone-gray/20 flex shrink-0 items-center rounded-full p-1.5"
                :title="instanceName || repo.provider"
            >
                <UiIcon :name="providerIcon" class="text-stone-gray h-4 w-4" />
            </div>

            <p
                class="text-stone-gray/70 min-w-0 overflow-hidden text-sm text-ellipsis whitespace-nowrap"
            >
                {{ repo.full_name }}
            </p>
        </div>
    </div>
</template>

<style scoped></style>