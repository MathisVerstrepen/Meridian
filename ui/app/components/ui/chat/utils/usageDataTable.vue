<script lang="ts" setup>
import type { UsageData, UsageDataRequest } from '@/types/graph';

// --- Props ---
const props = defineProps<{
    usageData: UsageData | UsageDataRequest;
    subtitle?: string;
    isTotal?: boolean;
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
    <div class="px-3 py-2.5">
        <p
            v-if="subtitle"
            class="text-stone-gray/55 mb-2 truncate text-[10px] font-medium tracking-wide"
            :title="subtitle"
        >
            {{ subtitle }}
        </p>

        <dl class="space-y-[5px] text-[11px] leading-none">
            <!-- Prompt -->
            <div class="flex items-baseline justify-between gap-3 py-0.5">
                <dt class="text-stone-gray font-semibold">Prompt</dt>
                <dd class="text-soft-silk font-mono tabular-nums">
                    {{ usageData.prompt_tokens.toLocaleString() }}
                </dd>
            </div>
            <div
                v-for="[key, value] in promptTokenDetails"
                :key="`prompt-${key}`"
                class="flex items-baseline justify-between gap-3 pl-3"
            >
                <dt class="text-stone-gray/55 truncate text-[10px] font-normal">
                    {{ formatDetailLabel(key) }}
                </dt>
                <dd class="text-soft-silk/65 font-mono text-[10px] tabular-nums">
                    {{ value.toLocaleString() }}
                </dd>
            </div>

            <!-- Separator -->
            <div
                aria-hidden="true"
                class="via-stone-gray/15 mx-auto h-px w-full bg-gradient-to-r from-transparent to-transparent"
            />

            <!-- Completion -->
            <div class="flex items-baseline justify-between gap-3 py-0.5">
                <dt class="text-stone-gray font-semibold">Completion</dt>
                <dd class="text-soft-silk font-mono tabular-nums">
                    {{ usageData.completion_tokens.toLocaleString() }}
                </dd>
            </div>
            <div
                v-for="[key, value] in completionTokenDetails"
                :key="`completion-${key}`"
                class="flex items-baseline justify-between gap-3 pl-3"
            >
                <dt class="text-stone-gray/55 truncate text-[10px] font-normal">
                    {{ formatDetailLabel(key) }}
                </dt>
                <dd class="text-soft-silk/65 font-mono text-[10px] tabular-nums">
                    {{ value.toLocaleString() }}
                </dd>
            </div>

            <!-- Separator -->
            <div
                aria-hidden="true"
                class="via-stone-gray/15 mx-auto h-px w-full bg-gradient-to-r from-transparent to-transparent"
            />

            <!-- Total tokens -->
            <div class="flex items-baseline justify-between gap-3 py-0.5">
                <dt class="text-stone-gray/80 text-[10px] tracking-wider uppercase">Tokens</dt>
                <dd class="text-soft-silk font-mono tabular-nums">
                    {{ usageData.total_tokens.toLocaleString() }}
                </dd>
            </div>
        </dl>

        <!-- Cost block -->
        <div
            class="border-stone-gray/15 mt-2.5 flex items-baseline justify-between gap-3 border-t pt-2"
        >
            <dt class="text-stone-gray text-[10px] font-bold tracking-[0.14em] uppercase">
                {{ isTotal ? 'Total Cost' : 'Cost' }}
            </dt>
            <dd class="text-ember-glow font-mono text-xs font-bold tabular-nums whitespace-nowrap">
                {{ formatMessageCost(usageData.cost) }}
            </dd>
        </div>
        <div v-if="hasUpstreamInferenceCost" class="flex items-baseline justify-between gap-3 pt-1 pl-3">
            <dt class="text-stone-gray/55 text-[10px] font-normal">Upstream</dt>
            <dd class="text-soft-silk/65 font-mono text-[10px] tabular-nums whitespace-nowrap">
                {{ formatMessageCost(upstreamInferenceCost) }}
            </dd>
        </div>
    </div>
</template>

<style scoped></style>
