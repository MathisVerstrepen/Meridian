<script setup lang="ts">
import type { AgentProfile } from '@/types/agent';
import { agentIconDataUrl } from '@/utils/agentIcon';
const props = defineProps<{
    profile: Pick<AgentProfile, 'icon' | 'iconSvg' | 'accentColor'>;
    label?: string;
}>();
const source = computed(() =>
    props.profile.iconSvg ? agentIconDataUrl(props.profile.iconSvg, props.profile.accentColor) : '',
);
</script>
<template>
    <img
        v-if="source"
        :src="source"
        :alt="label ?? ''"
        :aria-hidden="label ? undefined : true"
        class="inline-block shrink-0 object-contain"
        draggable="false"
    />
    <UiIcon v-else :name="profile.icon === 'LucideBot' ? 'RiBrain2Line' : profile.icon" />
</template>
