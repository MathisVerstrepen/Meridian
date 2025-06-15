<script lang="ts" setup>
import type { User } from '@/types/user';

// --- Stores ---
const settingsStore = useSettingsStore();

// --- Composables ---
const { user, clear } = useUserSession();

const disconnect = async () => {
    try {
        localStorage.removeItem('access_token');
        clear().then(() => {
            console.log('User session cleared successfully.');
            window.location.reload();
        });
    } catch (error) {
        console.error('Error disconnecting:', error);
    }
};

onMounted(() => {
    if (user.value) {
        console.log('User session is active:', user.value);
    } else {
        console.warn('No user session found.');
    }
});
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <div
            class="bg-obsidian/75 border-stone-gray/10 col-span-2 flex justify-between gap-4 rounded-2xl border-2 px-5
                py-4 shadow-lg backdrop-blur-md"
        >
            <div class="flex items-center gap-4">
                <img
                    :src="(user as User).avatarUrl"
                    :srcset="(user as User).avatarUrl"
                    class="bg-obsidian h-10 w-10 rounded-full object-cover"
                    loading="lazy"
                    :width="40"
                    :height="40"
                />
                <div class="flex flex-col">
                    <div class="relative flex items-center">
                        <span class="text-stone-gray mr-2 font-bold">{{
                            (user as User).name
                        }}</span>
                        <span
                            class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-0.5 text-xs font-bold"
                            >{{ (user as User).provider }}</span
                        >
                    </div>
                    <span class="text-stone-gray/50 text-xs">{{ (user as User).email }}</span>
                </div>
            </div>

            <button
                class="bg-terracotta-clay-dark hover:bg-terracotta-clay-dark/80 focus:shadow-outline text-soft-silk w-fit
                    rounded-lg px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                    focus:outline-none"
                @click="disconnect"
            >
                Disconnect Account
            </button>
        </div>

        <label class="flex gap-2 self-center" for="general-open-chat-view-on-new-canvas">
            <NuxtLink
                class="text-stone-gray font-bold"
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
            type="text"
            class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-10 w-full
                max-w-[42rem] rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none
                focus:border-2"
            placeholder="sk-or-v1-..."
            @input="
                (event: Event) => {
                    console.log('Input changed:', (event.target as HTMLInputElement).value);
                    settingsStore.setOpenRouterApiKey(
                        (event.target as HTMLInputElement).value,
                        user?.id || '',
                    );
                }
            "
        />
    </div>
</template>

<style scoped></style>
