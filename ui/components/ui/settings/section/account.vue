<script lang="ts" setup>
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();

const { setOpenRouterApiKey, getOpenRouterApiKey } = settingsStore;
const { isReady } = storeToRefs(settingsStore);

// --- Composables ---
const { user, clear } = useUserSession();
const { error } = useToast();

const isResetPassPopupOpen = ref(false);

const resetPassword = () => {
    isResetPassPopupOpen.value = true;
};

const disconnect = async () => {
    try {
        localStorage.removeItem('access_token');
        const tokenCookie = useCookie('auth_token');
        tokenCookie.value = null;

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
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <UiSettingsSectionResetPassPopup
            v-if="isResetPassPopupOpen"
            @closeFullscreen="isResetPassPopupOpen = false"
        ></UiSettingsSectionResetPassPopup>

        <div
            v-if="isReady"
            class="dark:bg-obsidian/75 bg-soft-silk/90 border-stone-gray/10 col-span-2 flex justify-between gap-4
                rounded-2xl border-2 px-5 py-4 shadow-lg backdrop-blur-md"
        >
            <div class="flex items-center gap-4">
                <img
                    :src="(user as User).avatarUrl"
                    :srcset="(user as User).avatarUrl"
                    class="bg-obsidian h-10 w-10 rounded-full object-cover"
                    loading="lazy"
                    :width="40"
                    :height="40"
                    v-if="(user as User).avatarUrl"
                />
                <span v-else class="dark:text-stone-gray text-obsidian font-bold">
                    <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
                </span>
                <div class="flex flex-col">
                    <div class="relative flex items-center">
                        <span class="dark:text-stone-gray text-obsidian mr-2 font-bold">{{
                            (user as User).name
                        }}</span>
                        <span
                            class="dark:border-anthracite border-anthracite/50 dark:text-stone-gray/50 text-obsidian/50 rounded-lg
                                border px-2 py-0.5 text-xs font-bold"
                            >{{ (user as User).provider }}</span
                        >
                    </div>
                    <span class="dark:text-stone-gray text-obsidian/50 text-xs">{{
                        (user as User).email
                    }}</span>
                </div>
            </div>

            <button
                class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline dark:text-soft-silk text-obsidian w-fit
                    rounded-lg px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                    focus:outline-none"
                @click="disconnect"
            >
                Disconnect Account
            </button>
        </div>

        <label class="flex gap-2 self-center" for="account-api-key">
            <NuxtLink
                class="text-stone-gray decoration-stone-gray/40 hover:decoration-stone-gray/60 font-bold underline
                    decoration-dashed underline-offset-4 transition-colors duration-200 ease-in-out"
                to="https://openrouter.ai/settings/keys"
                external
                target="_blank"
            >
                OpenRouter API Key
            </NuxtLink>
            <UiSettingsInfobubble>
                This key is used to authenticate your requests to the OpenRouter API. You can manage
                your keys on the OpenRouter website.
            </UiSettingsInfobubble>
        </label>
        <input
            id="account-api-key"
            type="password"
            class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-10 w-full
                max-w-[42rem] rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none
                focus:border-2"
            placeholder="sk-or-v1-..."
            :value="getOpenRouterApiKey(user?.id || '')"
            @input="
                (event: Event) => {
                    setOpenRouterApiKey((event.target as HTMLInputElement).value, user?.id || '');
                }
            "
        />

        <label class="flex gap-2 self-center" for="account-reset-password">
            <h3 class="text-stone-gray font-bold">Change Password</h3>
            <UiSettingsInfobubble> Use this option to change your password. </UiSettingsInfobubble>
        </label>

        <button
            class="hover:bg-stone-gray/10 focus:shadow-outline dark:text-soft-silk text-obsidian border-stone-gray/20
                w-fit rounded-lg border-2 px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                focus:outline-none"
            @click="resetPassword"
        >
            Change Password
        </button>
    </div>
</template>

<style scoped></style>
