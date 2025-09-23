<script lang="ts" setup>
import type { User } from '@/types/user';

const props = defineProps<{
    avatarCacheBuster?: number;
}>();

// --- Composables ---
const { user } = useUserSession();
const { fetchWithRefresh } = useAPI();
const requestUrl = useRequestURL();

const imageSrc = ref<string | null>(null);

const loadAvatar = async () => {
    const performRequest = async (): Promise<Blob> => {
        const cacheBuster = props.avatarCacheBuster ? `?t=${props.avatarCacheBuster}` : '';
        const fullUrl = new URL(`/api/user/avatar${cacheBuster}`, requestUrl.origin).href;
        const response = await fetch(fullUrl);

        if (response.status === 401) {
            const error = new Error('Unauthorized');
            (error as { response?: { status?: number } }).response = { status: 401 };
            throw error;
        }
        if (!response.ok) {
            throw new Error(`Failed to fetch avatar: ${response.statusText}`);
        }
        return response.blob();
    };

    try {
        const blob = await fetchWithRefresh(performRequest, 'Avatar Error');
        if (imageSrc.value && imageSrc.value.startsWith('blob:')) {
            URL.revokeObjectURL(imageSrc.value);
        }
        imageSrc.value = URL.createObjectURL(blob);
    } catch (error) {
        console.error('Could not load user avatar:', error);
        imageSrc.value = null;
    }
};

watch(
    () => [(user.value as User)?.avatarUrl, props.avatarCacheBuster],
    ([avatarUrl]) => {
        if (!avatarUrl) {
            imageSrc.value = '';
            return;
        }

        if (typeof avatarUrl === 'string' && avatarUrl.startsWith('http')) {
            imageSrc.value = avatarUrl;
        } else {
            if (import.meta.client) {
                loadAvatar();
            }
        }
    },
    { immediate: true },
);

onUnmounted(() => {
    if (imageSrc.value && imageSrc.value.startsWith('blob:')) {
        URL.revokeObjectURL(imageSrc.value);
    }
});
</script>

<template>
    <div class="relative h-10 w-10">
        <div class="bg-anthracite h-10 w-10 rounded-full absolute z-0"></div>

        <img
            v-if="imageSrc !== '' && imageSrc !== null"
            :src="imageSrc"
            class="h-10 w-10 rounded-full object-cover transition-opacity group-hover:opacity-50 z-10 relative"
            loading="lazy"
            width="40"
            height="40"
            alt="User Avatar"
        />
        <span v-else-if="imageSrc === ''" class="text-stone-gray z-10 relative">
            <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
        </span>
    </div>
</template>
