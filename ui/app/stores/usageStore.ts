import { defineStore } from 'pinia';

export const useUsageStore = defineStore('usage', () => {
    // Composables
    const { getUsage } = useAPI();

    // State
    const webSearchUsage = ref({ used: 0, total: 0, billing_period_end: '' });
    const linkExtractionUsage = ref({ used: 0, total: 0, billing_period_end: '' });

    const isLoading = ref(true);

    // Actions
    async function fetchUsage() {
        try {
            const data = await getUsage();
            if (data?.web_search) {
                webSearchUsage.value = {
                    used: data.web_search.used,
                    total: data.web_search.total,
                    billing_period_end: data.web_search.billing_period_end,
                };
            }
            if (data?.link_extraction) {
                linkExtractionUsage.value = {
                    used: data.link_extraction.used,
                    total: data.link_extraction.total,
                    billing_period_end: data.link_extraction.billing_period_end,
                };
            }
        } catch (error) {
            console.error('Failed to fetch usage data:', error);
            webSearchUsage.value = { used: 0, total: 0, billing_period_end: '' };
            linkExtractionUsage.value = { used: 0, total: 0, billing_period_end: '' };
        } finally {
            isLoading.value = false;
        }
    }

    const getUsagePercentage = (used: number, total: number): number => {
        if (total === 0) return 0;
        return Math.min((used / total) * 100, 100);
    };

    return {
        webSearchUsage,
        linkExtractionUsage,
        isLoading,
        getUsagePercentage,
        fetchUsage,
    };
});
