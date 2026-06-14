import { useMediaQuery } from '@vueuse/core';

export function useHydratedMediaQuery(query: string) {
    const isMounted = ref(false);
    const matches = useMediaQuery(query);

    onMounted(() => {
        isMounted.value = true;
    });

    return computed(() => isMounted.value && matches.value);
}
