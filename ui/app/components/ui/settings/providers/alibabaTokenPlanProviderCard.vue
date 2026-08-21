<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import type { InferenceProviderStatus } from '@/types/model';

defineProps<{
    expanded: boolean;
}>();

const emit = defineEmits<{
    toggle: [];
}>();

const entry = SETTINGS_ENTRY.providersAlibabaTokenPlan;
const apiKey = ref('');
const formError = ref('');
const isSubmitting = ref(false);

const modelStore = useModelStore();
const settingsStore = useSettingsStore();
const { modelsDropdownSettings } = storeToRefs(settingsStore);
const { setModels, sortModels, triggerFilter } = modelStore;
const { success, error } = useToast();
const { getProviderStatus, refreshInferenceProviderStatuses } = useInferenceProviderStatuses();
const {
    connectAlibabaTokenPlanApiKey,
    disconnectAlibabaTokenPlanApiKey,
    getAvailableModels,
} = useAPI();

const providerStatus = computed<InferenceProviderStatus | null>(() =>
    getProviderStatus('alibaba_token_plan'),
);

const refreshAvailableModels = async () => {
    const modelList = await getAvailableModels();
    setModels(modelList.data);
    sortModels(modelsDropdownSettings.value.sortBy);
    triggerFilter();
};

const safeErrorMessage = <Caught>(caught: Caught, fallback: string) => {
    const rawMessage = caught instanceof Error ? caught.message.trim() : '';
    const key = apiKey.value.trim();
    const message = rawMessage || fallback;
    return key ? message.split(key).join('[redacted]') : message;
};

const connect = async () => {
    const key = apiKey.value.trim();
    formError.value = '';

    if (!key) {
        formError.value = 'Enter an Alibaba Personal Token Plan API key.';
        return;
    }
    if (!key.startsWith('sk-sp-')) {
        formError.value = 'Personal Token Plan keys must start with sk-sp-.';
        return;
    }

    isSubmitting.value = true;
    try {
        await connectAlibabaTokenPlanApiKey(key);
        apiKey.value = '';
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Alibaba Cloud Token Plan connected successfully.');
    } catch (caught: unknown) {
        formError.value = safeErrorMessage(
            caught,
            'Failed to connect Alibaba Cloud Token Plan.',
        );
        error(formError.value, { title: 'Alibaba Cloud Token Plan Error' });
    } finally {
        isSubmitting.value = false;
    }
};

const disconnect = async () => {
    formError.value = '';
    isSubmitting.value = true;
    try {
        await disconnectAlibabaTokenPlanApiKey();
        await Promise.all([refreshInferenceProviderStatuses(), refreshAvailableModels()]);
        success('Alibaba Cloud Token Plan disconnected successfully.');
    } catch (caught: unknown) {
        formError.value = safeErrorMessage(
            caught,
            'Failed to disconnect Alibaba Cloud Token Plan.',
        );
        error(formError.value, { title: 'Alibaba Cloud Token Plan Error' });
    } finally {
        isSubmitting.value = false;
    }
};
</script>

<template>
    <div
        class="provider-card border-stone-gray/8 overflow-hidden rounded-xl border-2
            transition-colors duration-200"
        :class="expanded ? 'border-stone-gray/15 bg-obsidian/40' : 'bg-obsidian/25'"
        data-testid="alibaba-token-plan-card"
    >
        <button
            type="button"
            class="group flex w-full items-center gap-4 px-5 py-4 text-left transition-colors
                duration-200 hover:bg-white/2"
            :aria-expanded="expanded"
            @click="emit('toggle')"
        >
            <div
                class="bg-obsidian border-stone-gray/10 flex h-10 w-10 shrink-0 items-center
                    justify-center rounded-lg border"
            >
                <UiIcon name="models/qwen" class="text-soft-silk h-5 w-5" />
            </div>
            <div class="min-w-0 flex-1">
                <h3 class="text-soft-silk text-sm font-bold">{{ entry.title }}</h3>
                <p class="text-stone-gray/50 text-xs">{{ entry.description }}</p>
            </div>
            <div
                class="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold tracking-wide
                    uppercase"
                :class="
                    providerStatus?.isConnected
                        ? 'bg-green-500/10 text-green-400/90'
                        : 'bg-stone-gray/8 text-stone-gray/40'
                "
                data-testid="alibaba-token-plan-status"
            >
                {{ providerStatus?.isConnected ? 'Connected' : 'Disconnected' }}
            </div>
            <UiIcon
                name="LineMdChevronSmallUp"
                class="text-stone-gray/30 h-5 w-5 shrink-0 transition-transform duration-300"
                :class="expanded ? 'rotate-180' : 'rotate-90'"
            />
        </button>

        <Transition
            enter-active-class="transition-[max-height,opacity] duration-300 ease-out"
            enter-from-class="max-h-0 opacity-0"
            enter-to-class="max-h-[900px] opacity-100"
            leave-active-class="transition-[max-height,opacity] duration-200 ease-in"
            leave-from-class="max-h-[900px] opacity-100"
            leave-to-class="max-h-0 opacity-0"
        >
            <div v-if="expanded" class="overflow-hidden">
                <div class="border-stone-gray/8 mx-5 border-t" />
                <div class="grid grid-cols-1 gap-6 px-5 py-5 lg:grid-cols-2">
                    <form class="flex flex-col gap-4" @submit.prevent="connect">
                        <div class="flex flex-col gap-1.5">
                            <label
                                for="alibaba-token-plan-api-key"
                                class="text-stone-gray/60 text-xs font-semibold tracking-wider
                                    uppercase"
                            >
                                Personal API Key
                            </label>
                            <input
                                id="alibaba-token-plan-api-key"
                                v-model="apiKey"
                                type="password"
                                autocomplete="off"
                                class="provider-input border-stone-gray/15 bg-obsidian/60
                                    text-stone-gray focus:border-ember-glow/60 h-10 w-full rounded-lg
                                    border-2 px-3 text-sm transition-colors duration-200 outline-none
                                    disabled:cursor-not-allowed disabled:opacity-50"
                                placeholder="sk-sp-..."
                                :disabled="isSubmitting || providerStatus?.isConnected"
                                @input="formError = ''"
                            />
                            <p v-if="formError" class="text-red-400/90 text-xs" role="alert">
                                {{ formError }}
                            </p>
                        </div>
                        <div class="flex flex-wrap items-center gap-2">
                            <button
                                type="submit"
                                class="bg-ember-glow/80 hover:bg-ember-glow/60 text-soft-silk
                                    rounded-lg px-4 py-2 text-xs font-bold transition-colors
                                    duration-200 disabled:cursor-not-allowed disabled:opacity-50"
                                :disabled="isSubmitting || providerStatus?.isConnected"
                            >
                                {{ isSubmitting ? 'Working...' : 'Connect' }}
                            </button>
                            <button
                                type="button"
                                class="border-stone-gray/15 text-stone-gray/70 hover:bg-stone-gray/8
                                    hover:text-soft-silk rounded-lg border px-4 py-2 text-xs font-bold
                                    transition-colors duration-200 disabled:cursor-not-allowed
                                    disabled:opacity-40"
                                :disabled="!providerStatus?.isConnected || isSubmitting"
                                @click="disconnect"
                            >
                                {{ isSubmitting ? 'Working...' : 'Disconnect' }}
                            </button>
                        </div>
                    </form>

                    <div class="flex flex-col gap-3">
                        <div
                            class="border-golden-ochre/25 bg-golden-ochre/8 rounded-lg border px-3
                                py-2.5"
                            data-testid="alibaba-token-plan-warning"
                        >
                            <p class="text-golden-ochre text-xs font-bold">Personal plan warning</p>
                            <p class="text-golden-ochre/85 mt-1 text-xs leading-relaxed">
                                Alibaba prohibits Personal Token Plan API use from custom application
                                backends and may suspend the subscription or ban the key. Connecting
                                Meridian does not remove this risk. Key validation sends a small
                                request that consumes plan tokens.
                            </p>
                        </div>

                        <p class="text-stone-gray/70 text-sm leading-relaxed">
                            Dynamically discovered image and HappyHorse video models are available in
                            Image Playground and configured chat generation tools. Image models use
                            square 1K/2K output with up to three references; supported HappyHorse
                            operations apply their own reference and frame controls.
                        </p>

                        <div>
                            <p
                                class="text-golden-ochre text-[11px] font-bold tracking-wider
                                    uppercase"
                            >
                                Unsupported features
                            </p>
                            <ul class="text-stone-gray/50 mt-1.5 space-y-1 text-xs">
                                <li>PDF and generic file attachments</li>
                                <li>JSON-schema structured-output helpers</li>
                                <li>Mask/selection Image Edit and video editing</li>
                                <li>Non-HappyHorse video models and provider audio controls</li>
                                <li>Driving audio, reference video or voice, and provider task cancellation</li>
                                <li>Alibaba native and Harness tools</li>
                            </ul>
                        </div>

                        <div class="flex flex-wrap gap-x-4 gap-y-2">
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow inline-flex
                                    items-center gap-1 text-xs font-semibold transition-colors
                                    duration-200"
                                to="https://www.alibabacloud.com/help/en/model-studio/token-plan-personal-quick-start"
                                external
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Personal quick start
                                <UiIcon name="MdiArrowTopRightThick" class="h-4 w-4" />
                            </NuxtLink>
                            <NuxtLink
                                class="text-ember-glow/70 hover:text-ember-glow inline-flex
                                    items-center gap-1 text-xs font-semibold transition-colors
                                    duration-200"
                                to="https://help.aliyun.com/en/model-studio/token-plan-personal-overview"
                                external
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Personal plan overview
                                <UiIcon name="MdiArrowTopRightThick" class="h-4 w-4" />
                            </NuxtLink>
                        </div>
                    </div>
                </div>
            </div>
        </Transition>
    </div>
</template>
