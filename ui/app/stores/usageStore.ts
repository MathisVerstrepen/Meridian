// ui/app/stores/usageStore.ts
import { defineStore } from 'pinia';

interface QueryUsageResponse {
    used: number;
    total: number;
    billing_period_end: string;
}

interface AllUsageResponse {
    web_search: QueryUsageResponse;
}

export const useUsageStore = defineStore('usage', () => {
    // State
    const webSearchUsed = ref(0);
    const webSearchTotal = ref(200);
    const billingPeriodEnd = ref('');
    const isLoading = ref(true);

    // Getters
    const usagePercentage = computed(() => {
        if (webSearchTotal.value === 0) return 0;
        return (webSearchUsed.value / webSearchTotal.value) * 100;
    });

    // Actions
    async function fetchUsage() {
        isLoading.value = true;
        try {
            const data = await $fetch<AllUsageResponse>('/api/user/usage');
            if (data.web_search) {
                webSearchUsed.value = data.web_search.used;
                webSearchTotal.value = data.web_search.total;
                billingPeriodEnd.value = data.web_search.billing_period_end;
            }
        } catch (error) {
            console.error('Failed to fetch usage data:', error);
            webSearchUsed.value = 0;
            webSearchTotal.value = 0;
        } finally {
            isLoading.value = false;
        }
    }

    return {
        webSearchUsed,
        webSearchTotal,
        billingPeriodEnd,
        isLoading,
        usagePercentage,
        fetchUsage,
    };
});
