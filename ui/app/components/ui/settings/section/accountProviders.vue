<script lang="ts" setup>
import type { InferenceProviderStatus } from '@/types/model';

// --- Stores ---
const modelStore = useModelStore();

// --- Refs from Store ---
const settingsStore = useSettingsStore();
const { modelsDropdownSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { success, error, warning } = useToast();
const { getProviderStatus, refreshInferenceProviderStatuses } = useInferenceProviderStatuses();
const {
    connectClaudeAgentToken,
    disconnectClaudeAgentToken,
    connectGitHubCopilotToken,
    disconnectGitHubCopilotToken,
    connectZAiCodingPlanApiKey,
    disconnectZAiCodingPlanApiKey,
    connectGeminiCliOAuthCreds,
    disconnectGeminiCliOAuthCreds,
    connectOpenAICodexAuthJson,
    disconnectOpenAICodexAuthJson,
    connectOpenCodeGoApiKey,
    disconnectOpenCodeGoApiKey,
    getAvailableModels,
} = useAPI();
const { setModels, sortModels, triggerFilter } = modelStore;

// --- Provider state ---
const claudeAgentStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('claude_agent'),
);
const claudeAgentToken = ref('');
const isClaudeAgentSubmitting = ref(false);

const githubCopilotStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('github_copilot'),
);
const githubCopilotToken = ref('');
const isGitHubCopilotSubmitting = ref(false);

const zAiCodingPlanStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('z_ai_coding_plan'),
);
const zAiCodingPlanApiKey = ref('');
const isZAiCodingPlanSubmitting = ref(false);

const geminiCliStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('gemini_cli'),
);
const geminiCliOAuthCredsJson = ref('');
const isGeminiCliSubmitting = ref(false);

const openAICodexStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('openai_codex'),
);
const openAICodexAuthJson = ref('');
const isOpenAICodexSubmitting = ref(false);

const openCodeGoStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('opencode_go'),
);
const openCodeGoApiKey = ref('');
const isOpenCodeGoSubmitting = ref(false);

// --- Collapsed/expanded state ---
const expandedProvider = ref<string | null>(null);

const toggleProvider = (id: string) => {
    expandedProvider.value = expandedProvider.value === id ? null : id;
};

// --- Helpers ---
const refreshAvailableModels = async () => {
    const modelList = await getAvailableModels();
    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
};

// --- Provider actions ---
const saveClaudeAgentToken = async () => {
    if (!claudeAgentToken.value.trim()) {
        warning('Paste a Claude Agent token first.', { title: 'Missing Token' });
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

const saveGitHubCopilotToken = async () => {
    if (!githubCopilotToken.value.trim()) {
        warning('Paste a GitHub Copilot token first.', { title: 'Missing Token' });
        return;
    }
    isGitHubCopilotSubmitting.value = true;
    try {
        await connectGitHubCopilotToken(githubCopilotToken.value.trim());
        githubCopilotToken.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('GitHub Copilot connected successfully.');
    } catch (err) {
        console.error('Failed to connect GitHub Copilot:', err);
        error((err as Error).message || 'Failed to connect GitHub Copilot.', {
            title: 'GitHub Copilot Error',
        });
    } finally {
        isGitHubCopilotSubmitting.value = false;
    }
};

const removeGitHubCopilotToken = async () => {
    isGitHubCopilotSubmitting.value = true;
    try {
        await disconnectGitHubCopilotToken();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('GitHub Copilot disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect GitHub Copilot:', err);
        error((err as Error).message || 'Failed to disconnect GitHub Copilot.', {
            title: 'GitHub Copilot Error',
        });
    } finally {
        isGitHubCopilotSubmitting.value = false;
    }
};

const saveZAiCodingPlanApiKey = async () => {
    if (!zAiCodingPlanApiKey.value.trim()) {
        warning('Paste a Z.AI Coding Plan API key first.', { title: 'Missing API Key' });
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

const saveGeminiCliOAuthCreds = async () => {
    if (!geminiCliOAuthCredsJson.value.trim()) {
        warning('Paste Gemini CLI oauth_creds.json content first.', {
            title: 'Missing OAuth Credentials',
        });
        return;
    }
    isGeminiCliSubmitting.value = true;
    try {
        await connectGeminiCliOAuthCreds(geminiCliOAuthCredsJson.value.trim());
        geminiCliOAuthCredsJson.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Gemini CLI connected successfully.');
    } catch (err) {
        console.error('Failed to connect Gemini CLI:', err);
        error((err as Error).message || 'Failed to connect Gemini CLI.', {
            title: 'Gemini CLI Error',
        });
    } finally {
        isGeminiCliSubmitting.value = false;
    }
};

const removeGeminiCliOAuthCreds = async () => {
    isGeminiCliSubmitting.value = true;
    try {
        await disconnectGeminiCliOAuthCreds();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Gemini CLI disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect Gemini CLI:', err);
        error((err as Error).message || 'Failed to disconnect Gemini CLI.', {
            title: 'Gemini CLI Error',
        });
    } finally {
        isGeminiCliSubmitting.value = false;
    }
};

const saveOpenAICodexAuthJson = async () => {
    if (!openAICodexAuthJson.value.trim()) {
        warning('Paste OpenAI Codex auth.json content first.', { title: 'Missing auth.json' });
        return;
    }
    isOpenAICodexSubmitting.value = true;
    try {
        await connectOpenAICodexAuthJson(openAICodexAuthJson.value.trim());
        openAICodexAuthJson.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('OpenAI Codex connected successfully.');
    } catch (err) {
        console.error('Failed to connect OpenAI Codex:', err);
        error((err as Error).message || 'Failed to connect OpenAI Codex.', {
            title: 'OpenAI Codex Error',
        });
    } finally {
        isOpenAICodexSubmitting.value = false;
    }
};

const removeOpenAICodexAuthJson = async () => {
    isOpenAICodexSubmitting.value = true;
    try {
        await disconnectOpenAICodexAuthJson();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('OpenAI Codex disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect OpenAI Codex:', err);
        error((err as Error).message || 'Failed to disconnect OpenAI Codex.', {
            title: 'OpenAI Codex Error',
        });
    } finally {
        isOpenAICodexSubmitting.value = false;
    }
};

const saveOpenCodeGoApiKey = async () => {
    if (!openCodeGoApiKey.value.trim()) {
        warning('Paste an OpenCode Go API key first.', { title: 'Missing API Key' });
        return;
    }
    isOpenCodeGoSubmitting.value = true;
    try {
        await connectOpenCodeGoApiKey(openCodeGoApiKey.value.trim());
        openCodeGoApiKey.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('OpenCode Go connected successfully.');
    } catch (err) {
        console.error('Failed to connect OpenCode Go:', err);
        error((err as Error).message || 'Failed to connect OpenCode Go.', {
            title: 'OpenCode Go Error',
        });
    } finally {
        isOpenCodeGoSubmitting.value = false;
    }
};

const removeOpenCodeGoApiKey = async () => {
    isOpenCodeGoSubmitting.value = true;
    try {
        await disconnectOpenCodeGoApiKey();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('OpenCode Go disconnected successfully.');
    } catch (err) {
        console.error('Failed to disconnect OpenCode Go:', err);
        error((err as Error).message || 'Failed to disconnect OpenCode Go.', {
            title: 'OpenCode Go Error',
        });
    } finally {
        isOpenCodeGoSubmitting.value = false;
    }
};

onMounted(() => {
    refreshInferenceProviderStatuses().catch((err) => {
        console.error('Failed to fetch inference provider status:', err);
    });
});
</script>

<template>
    <div class="flex flex-col gap-4 py-6">
        <p class="text-stone-gray/60 text-sm">
            Connect alternative inference providers to unlock additional models beyond OpenRouter.
            Each provider uses its own subscription or credentials.
        </p>

        <!-- ================================================================== -->
        <!-- Claude Agent -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'claude'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('claude')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/anthropic" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">Claude Agent</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">
                            Anthropic subscription-backed models
                        </p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://claude.com/pricing"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        claudeAgentStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ claudeAgentStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'claude' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[600px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[600px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'claude'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: input + actions -->
                        <form class="flex flex-col gap-4" @submit.prevent="saveClaudeAgentToken">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >Token</label
                                >
                                <input
                                    v-model="claudeAgentToken"
                                    type="password"
                                    autocomplete="off"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 h-10 w-full
                                        rounded-lg border-2 px-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste Claude Agent token"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    type="submit"
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isClaudeAgentSubmitting"
                                >
                                    Connect
                                </button>
                                <button
                                    type="button"
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !claudeAgentStatus?.isConnected || isClaudeAgentSubmitting
                                    "
                                    @click="removeClaudeAgentToken"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </form>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Generate a long-lived token with <code>claude setup-token</code>,
                                then paste it here to enable Claude Agent subscription-backed
                                models.
                            </p>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow text-xs
                                    font-semibold transition-colors duration-200"
                                to="https://code.claude.com/docs/en/authentication"
                                external
                                target="_blank"
                            >
                                View authentication docs<UiIcon
                                    name="MdiArrowTopRightThick"
                                    class="h-4 w-4"
                                />
                            </NuxtLink>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>PDF, file, and image attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>JSON-schema structured-output</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- ================================================================== -->
        <!-- GitHub Copilot -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'github'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('github')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/github" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">GitHub Copilot</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">Copilot subscription-backed models</p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://github.com/features/copilot/plans"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        githubCopilotStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ githubCopilotStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'github' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[800px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[800px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'github'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: input + actions -->
                        <form class="flex flex-col gap-4" @submit.prevent="saveGitHubCopilotToken">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >Token</label
                                >
                                <input
                                    v-model="githubCopilotToken"
                                    type="password"
                                    autocomplete="off"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 h-10 w-full
                                        rounded-lg border-2 px-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste GitHub Copilot token"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    type="submit"
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isGitHubCopilotSubmitting"
                                >
                                    Connect
                                </button>
                                <button
                                    type="button"
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !githubCopilotStatus?.isConnected ||
                                        isGitHubCopilotSubmitting
                                    "
                                    @click="removeGitHubCopilotToken"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </form>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Paste a GitHub token to enable Copilot subscription-backed models.
                                Supported prefixes: <code>gho_</code>, <code>ghu_</code>,
                                <code>github_pat_</code>.
                            </p>
                            <div>
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Recommended setup
                                </p>
                                <ol
                                    class="text-stone-gray/60 mt-1.5 list-inside list-decimal
                                        space-y-0.5 text-xs"
                                >
                                    <li>
                                        GitHub <code>Settings</code> &rarr;
                                        <code>Developer settings</code> &rarr;
                                        <code>Fine-grained tokens</code>
                                    </li>
                                    <li>Create token for your own account</li>
                                    <li>
                                        Set <code>Copilot requests</code> to <code>Read Only</code>
                                    </li>
                                    <li>Paste the resulting <code>github_pat_...</code> token</li>
                                </ol>
                            </div>
                            <div class="flex gap-3">
                                <NuxtLink
                                    class="text-ember-glow/70 hover:text-ember-glow text-xs
                                        font-semibold transition-colors duration-200"
                                    to="https://github.com/settings/personal-access-tokens/new"
                                    external
                                    target="_blank"
                                >
                                    Create token<UiIcon
                                        name="MdiArrowTopRightThick"
                                        class="h-4 w-4"
                                    />
                                </NuxtLink>
                                <NuxtLink
                                    class="text-ember-glow/70 hover:text-ember-glow text-xs
                                        font-semibold transition-colors duration-200"
                                    to="https://docs.github.com/en/copilot/how-tos/copilot-sdk/authenticate-copilot-sdk/authenticate-copilot-sdk"
                                    external
                                    target="_blank"
                                >
                                    Auth docs<UiIcon name="MdiArrowTopRightThick" class="h-4 w-4" />
                                </NuxtLink>
                            </div>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>PDF, file, and image attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>JSON-schema structured-output</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- ================================================================== -->
        <!-- Z.AI Coding Plan -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'zai'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('zai')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/z-ai" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">Z.AI Coding Plan</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">Z.AI Coding Plan endpoint models</p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://z.ai/subscribe"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        zAiCodingPlanStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ zAiCodingPlanStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'zai' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[600px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[600px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'zai'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: input + actions -->
                        <form class="flex flex-col gap-4" @submit.prevent="saveZAiCodingPlanApiKey">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >API Key</label
                                >
                                <input
                                    v-model="zAiCodingPlanApiKey"
                                    type="password"
                                    autocomplete="off"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 h-10 w-full
                                        rounded-lg border-2 px-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste Z.AI API key"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    type="submit"
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isZAiCodingPlanSubmitting"
                                >
                                    Connect
                                </button>
                                <button
                                    type="button"
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !zAiCodingPlanStatus?.isConnected ||
                                        isZAiCodingPlanSubmitting
                                    "
                                    @click="removeZAiCodingPlanApiKey"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </form>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Paste a Z.AI API key to enable Meridian's Z.AI Coding Plan provider.
                                Requests are routed through the Coding Plan endpoint with only
                                documented models exposed.
                            </p>
                            <p class="text-golden-ochre/80 text-xs">
                                Z.AI documents Coding Plan quota as limited to supported coding
                                tools and scenarios.
                            </p>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow text-xs
                                    font-semibold transition-colors duration-200"
                                to="https://docs.z.ai/devpack/overview"
                                external
                                target="_blank"
                            >
                                View Z.AI docs<UiIcon
                                    name="MdiArrowTopRightThick"
                                    class="h-4 w-4"
                                />
                            </NuxtLink>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>PDF, file, and image attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>JSON-schema structured-output</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- ================================================================== -->
        <!-- Gemini CLI -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'gemini'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('gemini')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/google" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">Gemini CLI</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">
                            Google AI subscription via Gemini CLI
                        </p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://gemini.google/subscriptions/"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        geminiCliStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ geminiCliStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'gemini' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[600px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[600px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'gemini'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: textarea + actions -->
                        <div class="flex flex-col gap-4">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >OAuth Credentials</label
                                >
                                <textarea
                                    v-model="geminiCliOAuthCredsJson"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 min-h-28 w-full
                                        rounded-lg border-2 p-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste the full oauth_creds.json content"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isGeminiCliSubmitting"
                                    @click="saveGeminiCliOAuthCreds"
                                >
                                    Connect
                                </button>
                                <button
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !geminiCliStatus?.isConnected || isGeminiCliSubmitting
                                    "
                                    @click="removeGeminiCliOAuthCreds"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </div>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Paste the raw content of your local
                                <code>~/.gemini/oauth_creds.json</code> file. Meridian exposes
                                aliases: <code>auto</code>, <code>pro</code>, <code>flash</code>,
                                and <code>flash-lite</code>.
                            </p>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow text-xs
                                    font-semibold transition-colors duration-200"
                                to="https://geminicli.com/docs/get-started/"
                                external
                                target="_blank"
                            >
                                Get started with Gemini CLI<UiIcon
                                    name="MdiArrowTopRightThick"
                                    class="h-4 w-4"
                                />
                            </NuxtLink>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>Audio and video attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>Direct Gemini-backed image generation</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- ================================================================== -->
        <!-- OpenAI Codex -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'openai'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('openai')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/openai" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">OpenAI Codex</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">OpenAI Codex subscription models</p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://developers.openai.com/codex/pricing"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        openAICodexStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ openAICodexStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'openai' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[700px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[700px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'openai'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: textarea + actions -->
                        <div class="flex flex-col gap-4">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >Auth JSON</label
                                >
                                <textarea
                                    v-model="openAICodexAuthJson"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 min-h-28 w-full
                                        rounded-lg border-2 p-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste the full auth.json content"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isOpenAICodexSubmitting"
                                    @click="saveOpenAICodexAuthJson"
                                >
                                    Connect
                                </button>
                                <button
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !openAICodexStatus?.isConnected || isOpenAICodexSubmitting
                                    "
                                    @click="removeOpenAICodexAuthJson"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </div>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Paste the raw content of your local
                                <code>~/.codex/auth.json</code> file. If your Codex CLI uses the OS
                                keychain, set <code>cli_auth_credentials_store = "file"</code> in
                                <code>~/.codex/config.toml</code>, run Codex once, then paste the
                                resulting file.
                            </p>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow text-xs
                                    font-semibold transition-colors duration-200"
                                to="https://developers.openai.com/codex/auth"
                                external
                                target="_blank"
                            >
                                OpenAI Codex auth docs<UiIcon
                                    name="MdiArrowTopRightThick"
                                    class="h-4 w-4"
                                />
                            </NuxtLink>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>PDF and generic file attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>Direct image generation</span>
                                    </li>
                                </ul>
                            </div>
                            <p class="text-stone-gray/40 mt-1 text-[11px]">
                                Copied sessions can become invalid after token refresh. If models
                                stop listing, refresh <code>auth.json</code> from a machine where
                                <code>codex</code> is signed in.
                            </p>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- ================================================================== -->
        <!-- OpenCode Go -->
        <!-- ================================================================== -->
        <div
            class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
                transition-colors duration-200"
            :class="
                expandedProvider === 'opencode'
                    ? 'border-stone-gray/15 bg-obsidian/40'
                    : 'bg-obsidian/25'
            "
        >
            <button
                class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                    duration-200 hover:bg-white/2"
                @click="toggleProvider('opencode')"
            >
                <div
                    class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                        justify-center rounded-lg border"
                >
                    <UiIcon name="models/opencode" class="text-soft-silk h-5 w-5" />
                </div>
                <div class="min-w-0 flex-1">
                    <h3 class="text-soft-silk text-sm font-bold">OpenCode Go</h3>
                    <div class="flex items-center gap-2">
                        <p class="text-stone-gray/50 text-xs">OpenCode Go subscription models</p>
                        <NuxtLink
                            class="text-ember-glow/70 hover:text-ember-glow inline-flex items-center
                                gap-1 text-[11px] font-semibold transition-colors duration-200"
                            to="https://opencode.ai/go"
                            external
                            target="_blank"
                            @click.stop
                        >
                            Subscription<UiIcon name="MdiArrowTopRightThick" class="h-3.5 w-3.5" />
                        </NuxtLink>
                    </div>
                </div>
                <div
                    class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                        uppercase"
                    :class="
                        openCodeGoStatus?.isConnected
                            ? 'bg-green-500/10 text-green-400/90'
                            : 'bg-stone-gray/8 text-stone-gray/40'
                    "
                >
                    {{ openCodeGoStatus?.isConnected ? 'Connected' : 'Disconnected' }}
                </div>
                <UiIcon
                    name="LineMdChevronSmallUp"
                    class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                    :class="expandedProvider === 'opencode' ? 'rotate-180' : 'rotate-90'"
                />
            </button>

            <Transition
                enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
                enter-from-class="max-h-0 opacity-0"
                enter-to-class="max-h-[600px] opacity-100"
                leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
                leave-from-class="max-h-[600px] opacity-100"
                leave-to-class="max-h-0 opacity-0"
            >
                <div v-if="expandedProvider === 'opencode'" class="overflow-hidden">
                    <div class="border-stone-gray/8 mx-5 border-t" />
                    <div class="grid grid-cols-2 gap-6 px-5 py-5">
                        <!-- Left: input + actions -->
                        <form class="flex flex-col gap-4" @submit.prevent="saveOpenCodeGoApiKey">
                            <div class="flex flex-col gap-1.5">
                                <label
                                    class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                        uppercase"
                                    >API Key</label
                                >
                                <input
                                    v-model="openCodeGoApiKey"
                                    type="password"
                                    autocomplete="off"
                                    class="provider-input border-stone-gray/15 bg-obsidian/60
                                        text-stone-gray focus:border-ember-glow/60 h-10 w-full
                                        rounded-lg border-2 px-3 text-sm transition-colors
                                        duration-200 outline-none"
                                    placeholder="Paste OpenCode Go API key"
                                />
                            </div>
                            <div class="flex items-center gap-2">
                                <button
                                    type="submit"
                                    class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                        rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                        duration-200 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isOpenCodeGoSubmitting"
                                >
                                    Connect
                                </button>
                                <button
                                    type="button"
                                    class="border-stone-gray/15 text-stone-gray/70
                                        hover:bg-stone-gray/8 hover:text-soft-silk rounded-lg border
                                        px-4 py-2 text-xs font-bold transition-colors duration-200
                                        disabled:cursor-not-allowed disabled:opacity-40"
                                    :disabled="
                                        !openCodeGoStatus?.isConnected || isOpenCodeGoSubmitting
                                    "
                                    @click="removeOpenCodeGoApiKey"
                                >
                                    Disconnect
                                </button>
                            </div>
                        </form>
                        <!-- Right: description + help -->
                        <div class="flex flex-col gap-3">
                            <p class="text-stone-gray/70 text-sm leading-relaxed">
                                Paste the API key from <code>opencode.ai/auth</code> > API Keys. Meridian
                                exposes OpenCode Go's documented subscription model list, including
                                GLM, Kimi, MiMo, MiniMax, and Qwen options.
                            </p>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow text-xs
                                    font-semibold transition-colors duration-200"
                                to="https://opencode.ai/docs/go/"
                                external
                                target="_blank"
                            >
                                OpenCode Go docs<UiIcon
                                    name="MdiArrowTopRightThick"
                                    class="h-4 w-4"
                                />
                            </NuxtLink>
                            <div class="mt-1">
                                <p
                                    class="text-golden-ochre text-[11px] font-bold tracking-wider
                                        uppercase"
                                >
                                    Unsupported features
                                </p>
                                <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>PDF, generic file, and image attachments input</span>
                                    </li>
                                    <li class="flex items-start gap-1.5">
                                        <span class="text-stone-gray/30 mt-px">&#x2022;</span>
                                        <span>JSON-schema structured-output</span>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>
    </div>
</template>

<style scoped>
code {
    background-color: rgba(0, 0, 0, 0.25);
    padding: 0.15em 0.4em;
    border-radius: 0.25rem;
    font-family:
        'SF Mono',
        SF Mono,
        Consolas,
        'Liberation Mono',
        Menlo,
        Courier,
        monospace;
}
</style>
