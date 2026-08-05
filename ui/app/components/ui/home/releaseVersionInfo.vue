<script lang="ts" setup>
import {
    compareReleaseVersions,
    parseReleaseVersion,
    type ReleaseChangelog,
} from '@/utils/releaseVersions';

const STORAGE_KEY = 'meridian-last-seen-release';

const props = defineProps<{
    currentVersion: string;
}>();

const changelogs = useAppConfig().releaseChangelogs as ReleaseChangelog[];
const isOpen = ref(false);
const hasUnreadRelease = ref(false);
const selectedChangelog = ref<ReleaseChangelog | null>(changelogs[0] ?? null);

const readStoredVersion = (): string | null => {
    try {
        return window.localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
};

const writeStoredVersion = (version: string): void => {
    try {
        window.localStorage.setItem(STORAGE_KEY, version);
    } catch {
        // Release-note persistence is noncritical and may be blocked by browser privacy settings.
    }
};

const markCurrentReleaseSeen = (): void => {
    if (!parseReleaseVersion(props.currentVersion)) return;

    hasUnreadRelease.value = false;
    const storedVersion = readStoredVersion();
    const versionToStore =
        storedVersion &&
        parseReleaseVersion(storedVersion) &&
        compareReleaseVersions(storedVersion, props.currentVersion) > 0
            ? storedVersion
            : props.currentVersion;
    writeStoredVersion(versionToStore);
};

const openReleaseNotes = (): void => {
    selectedChangelog.value = changelogs[0] ?? null;
    isOpen.value = true;
    markCurrentReleaseSeen();
};

onMounted(() => {
    if (!parseReleaseVersion(props.currentVersion)) return;

    const storedVersion = readStoredVersion();
    hasUnreadRelease.value =
        !storedVersion ||
        !parseReleaseVersion(storedVersion) ||
        compareReleaseVersions(props.currentVersion, storedVersion) > 0;
});
</script>

<template>
    <button
        type="button"
        class="hover:text-stone-gray/60 focus-visible:ring-ember-glow/60 relative cursor-pointer
            rounded-md px-1 py-0.5 transition-colors outline-none focus-visible:ring-2
            focus-visible:ring-offset-2 focus-visible:ring-offset-obsidian"
        aria-haspopup="dialog"
        :aria-label="`Version ${currentVersion}${hasUnreadRelease ? ', update available' : ''}`"
        @click="openReleaseNotes"
    >
        Version {{ currentVersion }}
        <span
            v-if="hasUnreadRelease"
            data-testid="release-unread-indicator"
            class="bg-ember-glow absolute -top-0.5 -right-1 h-2 w-2 rounded-full
                shadow-[0_0_6px_var(--color-ember-glow)]"
            aria-hidden="true"
        ></span>
    </button>

    <UiUtilsBaseModal
        v-model="isOpen"
        title="Release notes"
        size="xl"
        panel-class="flex h-[85vh] max-h-[48rem] flex-col"
        body-class="flex min-h-0 flex-1 flex-col p-0 md:flex-row"
    >
        <nav
            class="border-stone-gray/10 flex max-h-44 shrink-0 flex-col border-b md:max-h-none
                md:w-56 md:border-r md:border-b-0"
            aria-label="Release versions"
        >
            <div class="dark-scrollbar min-h-0 flex-1 overflow-y-auto p-3">
                <ul class="space-y-1">
                    <li v-for="changelog in changelogs" :key="changelog.version">
                        <button
                            type="button"
                            data-release-version
                            class="focus-visible:ring-ember-glow/60 w-full cursor-pointer rounded-lg
                                px-3 py-2 text-left text-sm font-medium transition-colors outline-none
                                focus-visible:ring-2"
                            :class="
                                selectedChangelog?.version === changelog.version
                                    ? 'bg-ember-glow/10 text-ember-glow'
                                    : 'text-stone-gray/70 hover:bg-stone-gray/10 hover:text-soft-silk'
                            "
                            :aria-current="
                                selectedChangelog?.version === changelog.version
                                    ? 'true'
                                    : undefined
                            "
                            @click="selectedChangelog = changelog"
                        >
                            {{ changelog.version }}
                        </button>
                    </li>
                </ul>
            </div>
        </nav>

        <div class="dark-scrollbar min-h-0 flex-1 overflow-y-auto p-5 sm:p-7">
            <article
                v-if="selectedChangelog"
                :key="selectedChangelog.version"
                data-testid="release-changelog-content"
                class="prose prose-invert prose-sm max-w-none prose-headings:text-soft-silk
                    prose-a:text-ember-glow prose-code:text-soft-silk prose-strong:text-soft-silk"
                v-html="selectedChangelog.html"
            ></article>
        </div>
    </UiUtilsBaseModal>
</template>
