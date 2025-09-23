<script lang="ts" setup>
import type { User } from '@/types/user';

const props = defineProps<{
    avatarCacheBuster?: number;
}>();

// --- Composables ---
const { user } = useUserSession();

const avatarSrc = computed(() => {
    if (!(user.value as User)?.avatarUrl) return null;
    if ((user.value as User).avatarUrl?.startsWith('http')) {
        return (user.value as User).avatarUrl;
    }
    return `/api/user/avatar?t=${props.avatarCacheBuster}`;
});
</script>

<template>
    <img
        v-if="(user as User).avatarUrl"
        :src="avatarSrc!"
        class="h-10 w-10 rounded-full object-cover transition-opacity group-hover:opacity-50"
        loading="lazy"
        width="40"
        height="40"
    />
    <span v-else class=" text-stone-gray">
        <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
    </span>
</template>

<style scoped></style>
