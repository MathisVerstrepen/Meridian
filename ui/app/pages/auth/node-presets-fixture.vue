<script setup lang="ts">
import type { User } from '@/types/user';
import { NODE_PRESETS_FIXTURE_ROUTE } from '~~/e2e/fixtures/nodePresetsFixture';

definePageMeta({ layout: false });
if (!import.meta.dev) throw createError({ statusCode: 404, statusMessage: 'Not Found' });

const settingsStore = useSettingsStore();
const { getUserSettings } = useAPI();
const { user, session } = useUserSession();
const fixtureReady = ref(false);
const lastSaveSucceeded = ref<boolean | null>(null);

const fixtureUser = (plan: 'free' | 'premium'): User => ({
    id: 'fixture-user',
    oauthId: 'fixture-oauth',
    email: 'fixture@example.com',
    name: 'Fixture User',
    avatarUrl: '',
    provider: 'userpass',
    plan_type: plan,
    is_admin: false,
    is_verified: true,
    has_seen_welcome: true,
});

const setPlan = (plan: 'free' | 'premium') => {
    session.value = { id: 'node-presets-fixture-session', user: fixtureUser(plan) };
};
const save = async () => {
    lastSaveSucceeded.value = await settingsStore.triggerSettingsUpdate();
};
const state = computed(() => ({
    route: NODE_PRESETS_FIXTURE_ROUTE,
    ready: fixtureReady.value,
    plan: (user.value as User | null)?.plan_type ?? null,
    hasChanged: settingsStore.hasChanged,
    saveBlocked: settingsStore.nodePresetSaveBlocked,
    lastSaveSucceeded: lastSaveSucceeded.value,
    nodePresets: settingsStore.nodePresetSettings,
}));

onMounted(async () => {
    setPlan('premium');
    settingsStore.setUserSettings(await getUserSettings());
    await nextTick();
    fixtureReady.value = true;
});
</script>

<template>
    <main
        data-testid="node-presets-fixture-page"
        :data-fixture-ready="fixtureReady"
        class="bg-obsidian text-soft-silk h-screen min-h-0 w-full overflow-y-auto p-4 lg:flex lg:flex-col lg:overflow-hidden"
    >
        <div class="mb-3 flex flex-wrap items-center gap-2 lg:shrink-0">
            <button data-testid="save-node-presets" :disabled="settingsStore.nodePresetSaveBlocked" @click="save">
                Save Changes
            </button>
            <button data-testid="set-free-plan" @click="setPlan('free')">Free plan</button>
            <button data-testid="set-premium-plan" @click="setPlan('premium')">Premium plan</button>
        </div>
        <pre data-testid="node-presets-fixture-state" class="sr-only">{{ JSON.stringify(state) }}</pre>
        <div class="lg:min-h-0 lg:flex-1 lg:overflow-hidden">
            <UiSettingsSectionNodePresets />
        </div>
    </main>
</template>
