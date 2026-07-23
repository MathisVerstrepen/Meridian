<script setup lang="ts">
import type { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    nodeType: NodeTypeEnum;
    control: 'radio' | 'checkbox';
    checked: boolean;
    groupName: string;
    disabled?: boolean;
}>();

const emit = defineEmits<{ change: [checked: boolean] }>();
const { getBlockByNodeType } = useBlocks();
const block = computed(() => getBlockByNodeType(props.nodeType));
</script>

<template>
    <label
        class="quick-workflow-control text-soft-silk relative flex min-w-0 items-start gap-3 rounded-md border p-3
            transition-colors duration-100 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-inset
            has-[:focus-visible]:ring-ember-glow"
        :class="{
            'border-ember-glow bg-ember-glow/10': checked,
            'border-stone-gray/10 bg-anthracite/10': !checked,
            'hover:border-ember-glow hover:bg-ember-glow/20': checked && !disabled,
            'hover:border-stone-gray/30 hover:bg-anthracite/30': !checked && !disabled,
            'cursor-not-allowed opacity-50': disabled,
            'cursor-pointer': !disabled,
        }"
    >
        <input
            :type="control"
            :name="groupName"
            :value="nodeType"
            :checked="checked"
            :disabled="disabled"
            class="sr-only top-3 left-3 z-10 m-0 opacity-0 [clip:auto] [clip-path:none]"
            :aria-label="`${block?.name ?? nodeType} ${control === 'radio' ? 'main block' : 'linked block'}`"
            @change="emit('change', ($event.target as HTMLInputElement).checked)"
        />
        <UiIcon
            :name="block?.icon || ''"
            class="mt-0.5 h-5 w-5 shrink-0"
            :style="block?.icon === 'MdiGithub' ? { color: 'var(--color-soft-silk)' } : { color: block?.color }"
            :data-github-icon-contrast="block?.icon === 'MdiGithub' ? 'settings-choice' : undefined"
            aria-hidden="true"
        />
        <span class="min-w-0">
            <span class="block break-words text-sm font-semibold">{{ block?.name ?? nodeType }}</span>
            <span class="text-stone-gray mt-1 block break-words text-xs leading-relaxed">{{ block?.desc }}</span>
        </span>
    </label>
</template>
