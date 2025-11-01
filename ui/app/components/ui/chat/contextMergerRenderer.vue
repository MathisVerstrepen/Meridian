<script lang="ts" setup>
import type { Message } from '@/types/graph';

const props = defineProps<{
    message: Message;
}>();

const emit = defineEmits(['rendered', 'triggerScroll']);

const branches = computed(() => {
    const text = props.message.content[0]?.text || '';
    const branchRegex =
        /--- Start of Merged Context from Branch (\d+) ---([\s\S]*?)--- End of Merged Context from Branch \1 ---/g;
    const matches = [...text.matchAll(branchRegex)];
    return matches.map((match, index) => ({
        number: index + 1,
        content: match[2].trim(),
    }));
});

onMounted(() => {
    emit('rendered');
    emit('triggerScroll');
});
</script>

<template>
    <HeadlessDisclosure v-slot="{ open }" as="div" class="group relative">
        <div
            class="dark:bg-obsidian bg-soft-silk/75 border-soft-silk/10 relative overflow-hidden
                rounded-xl border backdrop-blur-md transition-all duration-300"
            :class="{
                'hover:border-ember-glow/50': !open,
                'border-ember-glow': open,
            }"
        >
            <HeadlessDisclosureButton
                class="flex w-full items-center justify-between p-4 text-left focus:outline-none"
            >
                <div class="flex items-center gap-3">
                    <div class="flex items-center gap-2">
                        <div
                            class="bg-ember-glow/10 text-ember-glow flex h-8 w-8 items-center
                                justify-center rounded-lg font-bold"
                        >
                            <UiIcon :name="'TablerArrowMerge'" class="h-5 w-5" />
                        </div>
                        <span class="font-semibold">Merged Context from Branches</span>
                    </div>
                    <span class="text-stone-gray dark:text-soft-silk/60 text-sm font-medium">
                        (Combined from {{ branches.length }} sources)
                    </span>
                </div>

                <UiIcon
                    :name="'FlowbiteChevronDownOutline'"
                    :class="{
                        'rotate-180 transform': open,
                    }"
                    class="h-5 w-5"
                />
            </HeadlessDisclosureButton>

            <HeadlessDisclosurePanel
                class="dark:bg-anthracite/30 hide-scrollbar overflow-y-auto transition-[max-height]
                    duration-300 ease-in-out"
                :class="{
                    'max-h-0': !open,
                    'max-h-[800px]': open,
                }"
            >
                <div
                    class="border-t-stone-gray/10 dark:border-t-anthracite/70 space-y-4 border-t
                        p-4"
                >
                    <div
                        v-for="(branch, index) in branches"
                        :key="index"
                        class="dark:bg-anthracite/40 bg-stone-gray/10 rounded-lg p-4"
                    >
                        <div class="flex items-center gap-2 text-sm font-semibold">
                            <span
                                class="bg-ember-glow/10 text-ember-glow-dark dark:text-ember-glow
                                    rounded px-2 py-1"
                            >
                                Branch #{{ branch.number }}
                            </span>
                        </div>
                        <div class="dark:text-soft-silk/80 mt-2 text-sm whitespace-pre-wrap">
                            {{ branch.content }}
                        </div>
                    </div>
                </div>
            </HeadlessDisclosurePanel>
        </div>
    </HeadlessDisclosure>
</template>
