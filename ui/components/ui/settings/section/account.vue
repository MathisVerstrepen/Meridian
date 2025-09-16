<script lang="ts" setup>
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- Refs from Store ---
const { isReady, accountSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { user, clear } = useUserSession();
const { error } = useToast();

const isResetPassPopupOpen = ref(false);

const resetPassword = () => {
    isResetPassPopupOpen.value = true;
};

const disconnect = async () => {
    try {
        const tokenCookie = useCookie('auth_token');
        tokenCookie.value = null;

        const nuxtSession = useCookie('nuxt_session');
        nuxtSession.value = null;

        clear().then(() => {
            window.location.reload();
        });
    } catch (err) {
        console.error('Error disconnecting:', err);
        error('Failed to disconnect. Please try again.', {
            title: 'Disconnect Error',
        });
    }
};
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <UiSettingsSectionResetPassPopup
            v-if="isResetPassPopupOpen"
            @close-fullscreen="isResetPassPopupOpen = false"
        />

        <!-- User Profile Section -->
        <div class="py-6">
            <div
                v-if="isReady"
                class="bg-obsidian/75 border-stone-gray/10 flex items-center justify-between gap-4 rounded-2xl border-2
                    px-5 py-4 shadow-lg"
            >
                <div class="flex items-center gap-4">
                    <img
                        v-if="(user as User).avatarUrl"
                        :src="(user as User).avatarUrl"
                        class="h-10 w-10 rounded-full object-cover"
                        loading="lazy"
                        width="40"
                        height="40"
                    />
                    <span v-else class="text-stone-gray font-bold">
                        <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
                    </span>
                    <div class="flex flex-col">
                        <div class="relative flex items-center">
                            <span class="text-soft-silk mr-2 font-bold">{{
                                (user as User).name
                            }}</span>
                            <span
                                class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-0.5 text-xs font-bold"
                            >
                                {{ (user as User).provider }}
                            </span>
                        </div>
                        <span class="text-stone-gray/80 text-xs">{{ (user as User).email }}</span>
                    </div>
                </div>

                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline text-soft-silk w-fit rounded-lg px-4
                        py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer focus:outline-none"
                    @click="disconnect"
                >
                    Disconnect Account
                </button>
            </div>
        </div>

        <!-- Setting: OpenRouter API Key -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold">
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40 hover:decoration-stone-gray/60 underline decoration-dashed
                            underline-offset-4 transition-colors duration-200 ease-in-out"
                        to="https://openrouter.ai/settings/keys"
                        external
                        target="_blank"
                    >
                        OpenRouter API Key
                    </NuxtLink>
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    This key is used to authenticate your requests to the OpenRouter API. You can
                    manage your keys on the OpenRouter website.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <input
                    id="account-api-key"
                    type="password"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-10 w-96 rounded-lg
                        border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="sk-or-v1-..."
                    :value="accountSettings.openRouterApiKey"
                    @input="
                        (event: Event) => {
                            const target = event.target as HTMLInputElement;
                            accountSettings.openRouterApiKey = target.value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Change Password -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Change Password</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Use this option to change your password for local accounts.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <button
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk border-stone-gray/20 w-fit rounded-lg
                        border-2 px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                        focus:outline-none"
                    @click="resetPassword"
                >
                    Change Password
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
