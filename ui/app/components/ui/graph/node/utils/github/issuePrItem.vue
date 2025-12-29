<script lang="ts" setup>
import type { GithubIssue } from '@/types/github';

defineProps<{
    item: GithubIssue;
    selected: boolean;
}>();

defineEmits<{
    (e: 'toggle'): void;
}>();
</script>

<template>
    <div
        class="group hover:bg-stone-gray/10 flex cursor-pointer items-start gap-3 rounded-lg p-3
            transition-colors duration-200"
        :class="{ 'bg-stone-gray/5': selected }"
        @click="$emit('toggle')"
    >
        <!-- Checkbox -->
        <div class="pt-1">
            <div
                class="border-stone-gray/20 bg-obsidian/50 flex h-5 w-5 items-center justify-center
                    rounded border-2 transition-all duration-200"
                :class="{
                    '!bg-ember-glow/30 !border-ember-glow/50': selected,
                }"
            >
                <UiIcon
                    v-if="selected"
                    name="MaterialSymbolsCheckSmallRounded"
                    class="text-ember-glow h-4 w-4"
                />
            </div>
        </div>

        <!-- Icon -->
        <div>
            <UiIcon
                v-if="item.is_pull_request"
                name="MdiSourcePull"
                class="h-5 w-5"
                :class="item.state === 'open' ? 'text-green-500' : 'text-purple-500'"
            />
            <UiIcon
                v-else
                name="MdiAlertCircleOutline"
                class="h-5 w-5"
                :class="item.state === 'open' ? 'text-green-500' : 'text-stone-gray/60'"
            />
        </div>

        <!-- Content -->
        <div class="flex min-w-0 flex-1 flex-col gap-1">
            <div class="flex items-start justify-between gap-2">
                <span
                    class="text-soft-silk line-clamp-1 font-medium break-all"
                    :class="{ 'text-ember-glow': selected }"
                >
                    {{ item.title }}
                </span>
                <span class="text-stone-gray/40 text-xs whitespace-nowrap">
                    #{{ item.number }}
                </span>
            </div>

            <div class="flex items-center gap-2 text-xs">
                <span class="text-stone-gray/60">
                    {{ item.state }}
                </span>
                <span class="text-stone-gray/20">•</span>
                <span class="text-stone-gray/60 flex items-center gap-1">
                    <img
                        v-if="item.user_avatar"
                        :src="item.user_avatar"
                        class="h-4 w-4 rounded-full"
                        alt=""
                    />
                    {{ item.user_login }}
                </span>
                <span class="text-stone-gray/20">•</span>
                <NuxtTime :datetime="item.updated_at" class="text-stone-gray/60" format="short" />
            </div>

            <div v-if="item.body" class="text-stone-gray/50 mt-1 line-clamp-2 text-xs">
                {{ item.body }}
            </div>
        </div>
    </div>
</template>
