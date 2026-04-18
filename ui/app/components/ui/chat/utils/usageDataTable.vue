<script lang="ts" setup>
import type { UsageData } from '@/types/graph';

// --- Props ---
const props = defineProps<{
    usageData: UsageData;
    title: string;
    subtitle?: string;
}>();

// --- Composables ---
const { formatMessageCost } = useFormatters();

const formatDetailLabel = (key: string) =>
    key
        .split('_')
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');

const promptTokenDetails = computed(() =>
    Object.entries(props.usageData.prompt_tokens_details ?? {}).filter(([, value]) => value > 0),
);

const completionTokenDetails = computed(() =>
    Object.entries(props.usageData.completion_tokens_details ?? {}).filter(([, value]) => value > 0),
);

const hasUpstreamInferenceCost = computed(() =>
    Object.hasOwn(props.usageData.cost_details ?? {}, 'upstream_inference_cost'),
);

const upstreamInferenceCost = computed(
    () => props.usageData.cost_details?.upstream_inference_cost ?? 0,
);
</script>

<template>
    <div>
        <p class="mt-1 mb-0.5 text-xs font-bold whitespace-break-spaces">{{ title }}</p>
        <p class="mb-1 text-xs font-medium whitespace-break-spaces">{{ subtitle }}</p>
        <table class="w-full text-xs">
            <tbody>
                <tr class="border-stone-gray/40 border-b">
                    <td class="text-stone-gray py-2 pr-4 font-medium">Prompt Tokens</td>
                    <td class="text-soft-silk py-2 text-right font-mono">
                        {{ usageData.prompt_tokens.toLocaleString() }}
                    </td>
                </tr>
                <tr
                    v-for="([key, value], index) in promptTokenDetails"
                    :key="`prompt-${key}`"
                    :class="{
                        'border-stone-gray/40 border-b': index !== promptTokenDetails.length - 1,
                    }"
                >
                    <td class="text-stone-gray/80 py-2 pr-4 pl-6 font-medium">
                        {{ formatDetailLabel(key) }}
                    </td>
                    <td class="text-soft-silk/85 py-2 text-right font-mono">
                        {{ value.toLocaleString() }}
                    </td>
                </tr>
                <tr class="border-stone-gray/40 border-b">
                    <td class="text-stone-gray py-2 pr-4 font-medium">Completion Tokens</td>
                    <td class="text-soft-silk py-2 text-right font-mono">
                        {{ usageData.completion_tokens.toLocaleString() }}
                    </td>
                </tr>
                <tr
                    v-for="([key, value], index) in completionTokenDetails"
                    :key="`completion-${key}`"
                    :class="{
                        'border-stone-gray/40 border-b':
                            index !== completionTokenDetails.length - 1,
                    }"
                >
                    <td class="text-stone-gray/80 py-2 pr-4 pl-6 font-medium">
                        {{ formatDetailLabel(key) }}
                    </td>
                    <td class="text-soft-silk/85 py-2 text-right font-mono">
                        {{ value.toLocaleString() }}
                    </td>
                </tr>
                <tr class="border-stone-gray/40 border-b">
                    <td class="text-stone-gray py-2 pr-4 font-medium">Total Tokens</td>
                    <td class="text-soft-silk py-2 text-right font-mono">
                        {{ usageData.total_tokens.toLocaleString() }}
                    </td>
                </tr>
                <tr>
                    <td class="text-stone-gray pt-2 font-bold">Cost</td>
                    <td class="text-soft-silk pt-2 text-right font-bold whitespace-nowrap">
                        {{ formatMessageCost(usageData.cost) }}
                    </td>
                </tr>
                <tr v-if="hasUpstreamInferenceCost">
                    <td class="text-stone-gray/80 pt-2 pr-4 pl-6 font-medium">Upstream Cost</td>
                    <td class="text-soft-silk/85 pt-2 text-right font-mono whitespace-nowrap">
                        {{ formatMessageCost(upstreamInferenceCost) }}
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</template>

<style scoped></style>
