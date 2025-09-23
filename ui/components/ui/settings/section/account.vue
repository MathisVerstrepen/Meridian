<script lang="ts" setup>
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- Refs from Store ---
const { isReady, accountSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { user, clear, fetch: fetchUserSession } = useUserSession();
const { error } = useToast();

const isResetPassPopupOpen = ref(false);
const isAvatarModalOpen = ref(false);
const avatarCacheBuster = ref(Date.now());

const onUploadSuccess = async () => {
    isAvatarModalOpen.value = false;
    await fetchUserSession();
    avatarCacheBuster.value = Date.now();
};
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
        <UiSettingsUtilsProfilePictureModal
            v-if="isAvatarModalOpen"
            @close="isAvatarModalOpen = false"
            @upload-success="onUploadSuccess"
        />

        <!-- User Profile Section -->
        <div class="py-6">
            <div
                v-if="isReady"
                class="bg-obsidian/75 border-stone-gray/10 flex items-center justify-between gap-4 rounded-2xl border-2
                    px-5 py-4 shadow-lg"
            >
                <div class="flex items-center gap-4">
                    <button
                        class="group relative flex-shrink-0 rounded-full"
                        @click="isAvatarModalOpen = true"
                    >
                        <UiUtilsUserProfilePicture :avatar-cache-buster="avatarCacheBuster" />
                        <div
                            class="absolute inset-0 flex cursor-pointer items-center justify-center rounded-full bg-black/50 opacity-0
                                transition-opacity group-hover:opacity-100 duration-200 ease-in-out"
                        >
                            <UiIcon
                                v-if="(user as User).avatarUrl"
                                name="MaterialSymbolsEditRounded"
                                class="h-5 w-5 text-soft-silk"
                            />
                            <UiIcon
                                v-else
                                name="HeroiconsArrowUpTray16Solid"
                                class="h-5 w-5 text-soft-silk"
                            />
                        </div>
                    </button>
                    <div class="flex flex-col">
                        <div class="relative flex items-center gap-2">
                            <span class="text-soft-silk font-bold">{{ (user as User).name }}</span>
                            <UiUtilsPlanLevelChip :level="(user as User).plan_type" />
                        </div>
                        <span class="text-stone-gray/80 text-xs">{{ (user as User).email }}</span>
                    </div>
                </div>

                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline text-soft-silk flex w-fit items-center
                        gap-2 rounded-lg px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                        focus:outline-none"
                    @click="disconnect"
                >
                    <UiIcon name="MaterialSymbolsLogoutRounded" class="h-5 w-5" />
                    Log Out
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
