<script lang="ts" setup>
defineProps<{
    billingPeriodEnd: string;
    queryUsed: number;
    queryTotal: number;
    usagePercentage: number;
    isLoading: boolean;
    queryName?: string;
}>();
</script>

<template>
    <div>
        <div class="w-full">
            <h3 class="text-soft-silk font-semibold capitalize">{{ queryName }} Query Usage</h3>
            <div class="flex items-center justify-between">
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Your remaining {{ queryName }} queries for the current billing period.
                </p>
                <p v-if="queryTotal !== 0" class="text-stone-gray/80 mt-1 text-sm">
                    Usage resets on
                    <NuxtTime
                        :datetime="billingPeriodEnd"
                        format="MMMM D, YYYY"
                        class="font-bold"
                    />
                    (<NuxtTime :datetime="billingPeriodEnd" relative />)
                </p>
            </div>
        </div>
        <div v-if="!isLoading && queryTotal !== 0" class="mt-4">
            <div class="bg-anthracite/20 h-4 w-full rounded-full">
                <div
                    class="bg-ember-glow h-4 rounded-full"
                    :style="{ width: `${usagePercentage}%` }"
                ></div>
            </div>
            <p class="text-stone-gray/80 mt-2 h-4 text-right text-sm">
                {{ queryUsed }} / {{ queryTotal }} query used
            </p>
        </div>

        <div
            v-else-if="!isLoading && queryTotal === 0"
            class="bg-obsidian/20 border-stone-gray/10 mt-4 rounded-xl border p-4 text-center"
        >
            <p class="text-stone-gray/80 text-sm">
                Your plan does not include
                <span class="font-semibold">{{ queryName }}</span> queries.
            </p>
            <p class="text-stone-gray/80 mt-2 text-sm">
                Please
                <a href="/upgrade" class="text-ember-glow font-semibold underline"
                    >upgrade your plan</a
                >
                to access this feature.
            </p>
        </div>
    </div>
</template>

<style scoped></style>
