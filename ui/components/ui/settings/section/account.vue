<script lang="ts" setup>
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- Refs from Store ---
const { isReady, accountSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { user, clear, fetch: fetchUserSession } = useUserSession();
const { success, error, warning } = useToast();
const { updateUsername } = useAPI();

const isResetPassPopupOpen = ref(false);
const isAvatarModalOpen = ref(false);
const avatarCacheBuster = ref(Date.now());

// --- State for Username Editing ---
const isEditingUsername = ref(false);
const newUsername = ref('');
const usernameInput = ref<HTMLInputElement | null>(null);

const onUploadSuccess = async () => {
    isAvatarModalOpen.value = false;
    await fetchUserSession();
    avatarCacheBuster.value = Date.now();
};
const resetPassword = () => {
    isResetPassPopupOpen.value = true;
};

// --- Methods for Username Editing ---
const startEditing = () => {
    newUsername.value = (user.value as User)?.name || '';
    isEditingUsername.value = true;
    nextTick(() => {
        usernameInput.value?.focus();
    });
};

const cancelEditing = () => {
    isEditingUsername.value = false;
    newUsername.value = '';
};

const saveUsername = async () => {
    if (!newUsername.value.trim() || newUsername.value.trim() === (user.value as User).name) {
        warning(
            'New username is the same as the current one or empty, please choose a different name.',
        );
        cancelEditing();
        return;
    }

    try {
        await updateUsername(newUsername.value.trim());
        await fetchUserSession();
        success('Username updated successfully.');
        isEditingUsername.value = false;
    } catch (err) {
        if ((err as { status?: number })?.status === 409) {
            error('This username is already taken. Please choose another one.', {
                title: 'Username Conflict',
            });
            return;
        } else if ((err as { status?: number })?.status === 422) {
            error(
                'Invalid username. Please ensure it meets the required criteria of at least 3 characters and maximum 50 characters.',
                {
                    title: 'Invalid Username',
                },
            );
            return;
        }

        console.error('Failed to update username:', err);
    }
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
                                transition-opacity duration-200 ease-in-out group-hover:opacity-100"
                        >
                            <UiIcon
                                v-if="(user as User).avatarUrl"
                                name="MaterialSymbolsEditRounded"
                                class="text-soft-silk h-5 w-5"
                            />
                            <UiIcon
                                v-else
                                name="HeroiconsArrowUpTray16Solid"
                                class="text-soft-silk h-5 w-5"
                            />
                        </div>
                    </button>
                    <div class="flex flex-col">
                        <div class="relative flex min-h-[28px] items-center gap-2">
                            <!-- Conditional Username Editing -->
                            <div v-if="!isEditingUsername" class="flex items-center gap-2">
                                <span class="text-soft-silk font-bold">{{
                                    (user as User).name
                                }}</span>
                                <button
                                    class="text-stone-gray/60 hover:text-soft-silk/80 p-1 transition-colors duration-200"
                                    aria-label="Edit username"
                                    @click="startEditing"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsEditRounded"
                                        class="h-4 w-4 -translate-y-0.5"
                                    />
                                </button>
                            </div>
                            <div v-else class="mr-4 flex items-center gap-2">
                                <input
                                    ref="usernameInput"
                                    v-model="newUsername"
                                    type="text"
                                    class="border-stone-gray/20 bg-anthracite/20 text-soft-silk focus:border-ember-glow h-8 w-48 rounded-md
                                        border-2 px-2 text-sm transition-colors duration-200 ease-in-out outline-none focus:border-2"
                                    @keydown.enter.prevent="saveUsername"
                                    @keydown.esc.prevent="cancelEditing"
                                />
                                <button
                                    class="text-green-400/80 transition-colors duration-200 hover:text-green-400"
                                    aria-label="Save username"
                                    @click="saveUsername"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsCheckSmallRounded"
                                        class="h-6 w-6"
                                    />
                                </button>
                                <button
                                    class="text-red-400/80 transition-colors duration-200 hover:text-red-400"
                                    aria-label="Cancel editing"
                                    @click="cancelEditing"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsClose"
                                        class="h-5 w-5 -translate-y-[1px]"
                                    />
                                </button>
                            </div>
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
