<script lang="ts" setup>
import type { UsageData } from '@/types/graph';

// --- Props ---
defineProps<{
    usageData: UsageData;
    title: string;
    subtitle?: string;
}>();

// --- Composables ---
const { formatMessageCost } = useFormatters();
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
                <tr class="border-stone-gray/40 border-b">
                    <td class="text-stone-gray py-2 pr-4 font-medium">Completion Tokens</td>
                    <td class="text-soft-silk py-2 text-right font-mono">
                        {{ usageData.completion_tokens.toLocaleString() }}
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
            </tbody>
        </table>
    </div>
</template>

<style scoped></style>
