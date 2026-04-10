<script lang="ts" setup>
import type { InferenceProviderStatus } from '@/types/model';
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();
const modelStore = useModelStore();

// --- Refs from Store ---
const { isReady, accountSettings, modelsDropdownSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { user, clear, fetch: fetchUserSession } = useUserSession();
const { success, error, warning } = useToast();
const {
    updateUsername,
    deleteAccount,
    getInferenceProviderStatuses,
    connectClaudeAgentToken,
    disconnectClaudeAgentToken,
    connectZAiCodingPlanApiKey,
    disconnectZAiCodingPlanApiKey,
    getAvailableModels,
} = useAPI();
const { setModels, sortModels, triggerFilter } = modelStore;

const isResetPassPopupOpen = ref(false);
const isAvatarModalOpen = ref(false);
const isDeleteAccountModalOpen = ref(false);
const avatarCacheBuster = ref(Date.now());
const claudeAgentStatus = ref<InferenceProviderStatus | null>(null);
const claudeAgentToken = ref('');
const isClaudeAgentSubmitting = ref(false);
const zAiCodingPlanStatus = ref<InferenceProviderStatus | null>(null);
const zAiCodingPlanApiKey = ref('');
const isZAiCodingPlanSubmitting = ref(false);
const claudeAgentUnsupportedFeatures = [
    'PDF, file, and image attachments input',
    'JSON-schema structured-output',
];
const zAiCodingPlanUnsupportedFeatures = [
    'PDF, file, and image attachments input',
    'JSON-schema structured-output',
];

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

const refreshAvailableModels = async () => {
    const modelList = await getAvailableModels();
    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
};

const refreshInferenceProviderStatuses = async () => {
    const response = await getInferenceProviderStatuses();
    claudeAgentStatus.value =
        response.providers.find((provider) => provider.provider === 'claude_agent') || null;
    zAiCodingPlanStatus.value =
        response.providers.find((provider) => provider.provider === 'z_ai_coding_plan') || null;
};

const saveClaudeAgentToken = async () => {
    if (!claudeAgentToken.value.trim()) {
        warning('Paste a Claude Agent token first.', {
            title: 'Missing Token',
        });
        return;
    }

    isClaudeAgentSubmitting.value = true;
    try {
        await connectClaudeAgentToken(claudeAgentToken.value.trim());
        claudeAgentToken.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Claude Agent connected successfully.');
    } catch (err) {
        console.error('Failed to connect Claude Agent:', err);
        error((err as Error).message || 'Failed to connect Claude Agent.', {
            title: 'Claude Agent Error',
        });
    } finally {
        isClaudeAgentSubmitting.value = false;
    }
};

const removeClaudeAgentToken = async () => {
    isClaudeAgentSubmitting.value = true;
    try {
        await disconnectClaudeAgentToken();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Claude Agent disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect Claude Agent:', err);
        error((err as Error).message || 'Failed to disconnect Claude Agent.', {
            title: 'Claude Agent Error',
        });
    } finally {
        isClaudeAgentSubmitting.value = false;
    }
};

const saveZAiCodingPlanApiKey = async () => {
    if (!zAiCodingPlanApiKey.value.trim()) {
        warning('Paste a Z.AI Coding Plan API key first.', {
            title: 'Missing API Key',
        });
        return;
    }

    isZAiCodingPlanSubmitting.value = true;
    try {
        await connectZAiCodingPlanApiKey(zAiCodingPlanApiKey.value.trim());
        zAiCodingPlanApiKey.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Z.AI Coding Plan connected successfully.');
    } catch (err) {
        console.error('Failed to connect Z.AI Coding Plan:', err);
        error((err as Error).message || 'Failed to connect Z.AI Coding Plan.', {
            title: 'Z.AI Coding Plan Error',
        });
    } finally {
        isZAiCodingPlanSubmitting.value = false;
    }
};

const removeZAiCodingPlanApiKey = async () => {
    isZAiCodingPlanSubmitting.value = true;
    try {
        await disconnectZAiCodingPlanApiKey();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Z.AI Coding Plan disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect Z.AI Coding Plan:', err);
        error((err as Error).message || 'Failed to disconnect Z.AI Coding Plan.', {
            title: 'Z.AI Coding Plan Error',
        });
    } finally {
        isZAiCodingPlanSubmitting.value = false;
    }
};

const handleDeleteAccount = async () => {
    try {
        await deleteAccount();
        success('Account deleted successfully.');
        isDeleteAccountModalOpen.value = false;
        await disconnect();
    } catch (err) {
        console.error('Failed to delete account:', err);
        error('Failed to delete account. Please try again.', {
            title: 'Delete Error',
        });
        isDeleteAccountModalOpen.value = false;
    }
};

onMounted(() => {
    refreshInferenceProviderStatuses().catch((err) => {
        console.error('Failed to fetch inference provider status:', err);
    });
});
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
        <UiSettingsUtilsDeleteAccountModal
            v-if="isDeleteAccountModalOpen"
            @close="isDeleteAccountModalOpen = false"
            @confirm="handleDeleteAccount"
        />

        <!-- User Profile Section -->
        <div class="py-6">
            <div
                v-if="isReady"
                class="bg-obsidian/75 border-stone-gray/10 flex items-center justify-between gap-4
                    rounded-2xl border-2 px-5 py-4 shadow-lg"
            >
                <div class="flex items-center gap-4">
                    <button
                        class="group relative shrink-0 rounded-full"
                        @click="isAvatarModalOpen = true"
                    >
                        <UiUtilsUserProfilePicture :avatar-cache-buster="avatarCacheBuster" />
                        <div
                            class="absolute inset-0 z-50 flex cursor-pointer items-center
                                justify-center rounded-full bg-black/50 opacity-0 transition-opacity
                                duration-200 ease-in-out group-hover:opacity-100"
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
                                    class="text-stone-gray/60 hover:text-soft-silk/80 p-1
                                        transition-colors duration-200"
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
                                    class="border-stone-gray/20 bg-anthracite/20 text-soft-silk
                                        focus:border-ember-glow h-8 w-48 rounded-md border-2 px-2
                                        text-sm transition-colors duration-200 ease-in-out
                                        outline-none focus:border-2"
                                    @keydown.enter.prevent="saveUsername"
                                    @keydown.esc.prevent="cancelEditing"
                                />
                                <button
                                    class="text-green-400/80 transition-colors duration-200
                                        hover:text-green-400"
                                    aria-label="Save username"
                                    @click="saveUsername"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsCheckSmallRounded"
                                        class="h-6 w-6"
                                    />
                                </button>
                                <button
                                    class="text-red-400/80 transition-colors duration-200
                                        hover:text-red-400"
                                    aria-label="Cancel editing"
                                    @click="cancelEditing"
                                >
                                    <UiIcon
                                        name="MaterialSymbolsClose"
                                        class="h-5 w-5 -translate-y-px"
                                    />
                                </button>
                            </div>
                            <UiUtilsPlanLevelChip :level="(user as User).plan_type" />
                        </div>
                        <span class="text-stone-gray/80 text-xs">{{ (user as User).email }}</span>
                    </div>
                </div>

                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline
                        text-soft-silk flex w-fit items-center gap-2 rounded-lg px-4 py-2 text-sm
                        font-bold duration-200 ease-in-out hover:cursor-pointer focus:outline-none"
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
                        class="text-soft-silk decoration-stone-gray/40
                            hover:decoration-stone-gray/60 underline decoration-dashed
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
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow h-10 w-96 rounded-lg border-2 p-2 transition-colors
                        duration-200 ease-in-out outline-none focus:border-2"
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

        <!-- Setting: Claude Agent -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold">
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40
                            hover:decoration-stone-gray/60 underline decoration-dashed
                            underline-offset-4 transition-colors duration-200 ease-in-out"
                        to="https://code.claude.com/docs/en/authentication"
                        external
                        target="_blank"
                    >
                        Claude Agent Subscription
                    </NuxtLink>
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Generate a long-lived token with <code>claude setup-token</code>, then paste it
                    here to enable Claude Agent subscription-backed models on this Meridian server.
                </p>
                <p class="text-stone-gray/60 mt-2 text-xs">
                    Status:
                    <span
                        :class="
                            claudeAgentStatus?.isConnected ? 'text-green-400/80' : 'text-red-400/80'
                        "
                    >
                        {{ claudeAgentStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                    </span>
                </p>

                <p class="text-golden-ochre text-xs font-bold mt-3">
                    Unsupported features:
                </p>
                <ul class="text-stone-gray/80 mt-2 space-y-1 text-sm">
                    <li
                        v-for="feature in claudeAgentUnsupportedFeatures"
                        :key="feature"
                        class="flex items-start gap-2"
                    >
                        <span class="mt-[1px]">•</span>
                        <span>{{ feature }}</span>
                    </li>
                </ul>
            </div>
            <div class="ml-6 flex shrink-0 items-center gap-3">
                <input
                    id="account-claude-agent-token"
                    v-model="claudeAgentToken"
                    type="password"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow h-10 w-96 rounded-lg border-2 p-2 transition-colors
                        duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="Paste Claude Agent token"
                />
                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline
                        text-soft-silk flex w-fit items-center gap-2 rounded-lg px-4 py-2 text-sm
                        font-bold duration-200 ease-in-out hover:cursor-pointer focus:outline-none
                        disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="isClaudeAgentSubmitting"
                    @click="saveClaudeAgentToken"
                >
                    Connect
                </button>
                <button
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                        border-stone-gray/20 w-fit rounded-lg border-2 px-4 py-2 text-sm font-bold
                        duration-200 ease-in-out hover:cursor-pointer focus:outline-none
                        disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="!claudeAgentStatus?.isConnected || isClaudeAgentSubmitting"
                    @click="removeClaudeAgentToken"
                >
                    Disconnect
                </button>
            </div>
        </div>

        <!-- Setting: Z.AI Coding Plan -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold">
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40
                            hover:decoration-stone-gray/60 underline decoration-dashed
                            underline-offset-4 transition-colors duration-200 ease-in-out"
                        to="https://docs.z.ai/devpack/overview"
                        external
                        target="_blank"
                    >
                        Z.AI Coding Plan
                    </NuxtLink>
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Paste a Z.AI API key here to enable Meridian&apos;s Z.AI Coding Plan provider.
                    Meridian always routes these requests through the Coding Plan endpoint and only
                    exposes the documented Coding Plan models.
                </p>
                <p class="text-stone-gray/60 mt-2 text-xs">
                    Status:
                    <span
                        :class="
                            zAiCodingPlanStatus?.isConnected
                                ? 'text-green-400/80'
                                : 'text-red-400/80'
                        "
                    >
                        {{ zAiCodingPlanStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                    </span>
                </p>
                <p class="text-golden-ochre mt-2 text-xs">
                    Z.AI documents Coding Plan quota as limited to supported or recognized coding
                    tools and coding scenarios.
                </p>

                <p class="text-golden-ochre text-xs font-bold mt-3">
                    Unsupported features:
                </p>
                <ul class="text-stone-gray/80 mt-2 space-y-1 text-sm">
                    <li
                        v-for="feature in zAiCodingPlanUnsupportedFeatures"
                        :key="feature"
                        class="flex items-start gap-2"
                    >
                        <span class="mt-[1px]">•</span>
                        <span>{{ feature }}</span>
                    </li>
                </ul>
            </div>
            <div class="ml-6 flex shrink-0 items-center gap-3">
                <input
                    id="account-z-ai-coding-plan-api-key"
                    v-model="zAiCodingPlanApiKey"
                    type="password"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow h-10 w-96 rounded-lg border-2 p-2 transition-colors
                        duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="Paste Z.AI API key"
                />
                <button
                    class="bg-ember-glow/80 hover:bg-ember-glow/60 focus:shadow-outline
                        text-soft-silk flex w-fit items-center gap-2 rounded-lg px-4 py-2 text-sm
                        font-bold duration-200 ease-in-out hover:cursor-pointer focus:outline-none
                        disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="isZAiCodingPlanSubmitting"
                    @click="saveZAiCodingPlanApiKey"
                >
                    Connect
                </button>
                <button
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                        border-stone-gray/20 w-fit rounded-lg border-2 px-4 py-2 text-sm font-bold
                        duration-200 ease-in-out hover:cursor-pointer focus:outline-none
                        disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="!zAiCodingPlanStatus?.isConnected || isZAiCodingPlanSubmitting"
                    @click="removeZAiCodingPlanApiKey"
                >
                    Disconnect
                </button>
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
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                        border-stone-gray/20 w-fit rounded-lg border-2 px-4 py-2 text-sm font-bold
                        duration-200 ease-in-out hover:cursor-pointer focus:outline-none"
                    @click="resetPassword"
                >
                    Change Password
                </button>
            </div>
        </div>

        <!-- Setting: Delete Account -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold text-red-400">Delete Account</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Permanently delete your account and all associated data.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <button
                    class="focus:shadow-outline w-fit rounded-lg border-2 border-red-500/20 px-4
                        py-2 text-sm font-bold text-red-400 duration-200 ease-in-out
                        hover:cursor-pointer hover:bg-red-500/10 focus:outline-none"
                    @click="isDeleteAccountModalOpen = true"
                >
                    Delete Account
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
