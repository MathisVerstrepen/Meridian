<script lang="ts" setup>
import { watch } from 'vue';
import type { User } from '@/types/user';

const props = defineProps<{
    avatarCacheBuster?: number;
}>();

// --- Composables ---
const { user } = useUserSession();
const { avatarSrc, loadAvatar } = useUserAvatar();

watch(
    () => props.avatarCacheBuster,
    () => {
        if (props.avatarCacheBuster) {
            loadAvatar({ force: true });
        }
    },
);

onMounted(() => {
    if (!avatarSrc.value && (user.value as User)?.avatarUrl) {
        loadAvatar();
    } else if (!(user.value as User)?.avatarUrl) {
        avatarSrc.value = '';
    }
});
</script>

<template>
    <div class="relative h-10 w-10">
        <div
            v-if="avatarSrc !== ''"
            class="bg-anthracite absolute z-0 h-10 w-10 rounded-full"
        ></div>

        <img
            v-if="avatarSrc !== '' && avatarSrc !== null"
            :src="avatarSrc"
            class="relative z-10 h-10 w-10 rounded-full object-cover transition-opacity group-hover:opacity-50"
            loading="lazy"
            width="40"
            height="40"
            alt="User Avatar"
        />
        <span v-else-if="avatarSrc === ''" class="text-stone-gray relative z-10">
            <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
        </span>
    </div>
</template>
