import type { InferenceProvider, InferenceProviderStatus } from '@/types/model';

import {
    SUBSCRIPTION_PROVIDERS,
    type SubscriptionInferenceProvider,
} from '@/constants/modelDropdownSections';

export const useInferenceProviderStatuses = () => {
    const { getInferenceProviderStatuses } = useAPI();

    const statuses = useState<InferenceProviderStatus[]>('inference-provider-statuses', () => []);
    const hasLoaded = useState<boolean>('inference-provider-statuses-loaded', () => false);
    const pendingRequest = useState<Promise<InferenceProviderStatus[]> | null>(
        'inference-provider-statuses-pending',
        () => null,
    );

    const statusMap = computed(() => {
        const nextMap = new Map<InferenceProvider, InferenceProviderStatus>();

        for (const status of statuses.value) {
            nextMap.set(status.provider, status);
        }

        return nextMap;
    });

    const refreshInferenceProviderStatuses = async () => {
        if (pendingRequest.value) {
            return pendingRequest.value;
        }

        pendingRequest.value = getInferenceProviderStatuses()
            .then((response) => {
                statuses.value = response.providers;
                hasLoaded.value = true;
                return response.providers;
            })
            .finally(() => {
                pendingRequest.value = null;
            });

        return pendingRequest.value;
    };

    const getProviderStatus = (provider: InferenceProvider) => statusMap.value.get(provider) ?? null;

    const isProviderConnected = (provider: InferenceProvider) => !!getProviderStatus(provider)?.isConnected;

    const connectedSubscriptionProviders = computed<SubscriptionInferenceProvider[]>(() =>
        SUBSCRIPTION_PROVIDERS.filter((provider) => isProviderConnected(provider)),
    );

    return {
        statuses,
        hasLoaded,
        refreshInferenceProviderStatuses,
        getProviderStatus,
        isProviderConnected,
        connectedSubscriptionProviders,
    };
};
