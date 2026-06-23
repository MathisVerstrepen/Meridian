<script lang="ts" setup>
const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

const googleDriveStore = useGoogleDriveStore();
const { isGoogleDriveConnected, googleDriveEmail } = storeToRefs(googleDriveStore);
const { checkGoogleDriveStatus } = googleDriveStore;
const { connectGoogleDrive, disconnectGoogleDrive } = useAPI();
const { success, error: toastError } = useToast();

const isLoadingConnection = ref(true);

function connectToGoogleDrive() {
    sessionStorage.setItem('preOauthUrl', window.history.state.back || '/');
    window.location.href = `${API_BASE_URL}/auth/google-drive/login`;
}

async function disconnectFromGoogleDrive() {
    try {
        isLoadingConnection.value = true;
        await disconnectGoogleDrive();
        await checkGoogleDriveStatus();
        success('Successfully disconnected Google Drive.');
    } catch (error) {
        console.error('Failed to disconnect Google Drive:', error);
        toastError('Failed to disconnect Google Drive.');
    } finally {
        isLoadingConnection.value = false;
    }
}

onMounted(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    if (code) {
        try {
            await connectGoogleDrive(code);
            await checkGoogleDriveStatus();
            success('Successfully connected Google Drive.');
        } catch (error) {
            console.error('Google Drive connection error:', error);
            toastError('Failed to connect Google Drive.');
        } finally {
            window.history.replaceState({}, document.title, window.location.pathname);
            isLoadingConnection.value = false;
        }
        return;
    }

    await checkGoogleDriveStatus();
    isLoadingConnection.value = false;
});
</script>

<template>
    <div class="flex items-center justify-between gap-6 py-6">
        <div class="max-w-2xl">
            <h3 class="text-soft-silk font-semibold">Google Drive Connection</h3>
            <p class="text-stone-gray/80 mt-1 text-sm">
                Browse and select Drive files as external references. Meridian only stores metadata until a
                file is previewed or used in a request.
            </p>
            <p class="text-golden-ochre mt-2 text-xs">
                Uses the sensitive Google scope <code>drive.readonly</code> to access all readable Drive files.
                Production OAuth apps must complete Google verification.
            </p>
        </div>

        <div class="flex shrink-0 items-center gap-3">
            <div
                v-if="isLoadingConnection"
                class="bg-stone-gray/10 h-9 w-32 animate-pulse rounded-lg"
            />
            <template v-else-if="isGoogleDriveConnected">
                <div
                    class="border-olive-grove/30 bg-olive-grove/10 text-olive-grove rounded-lg border px-3 py-1.5
                        text-sm font-medium"
                >
                    Connected<span v-if="googleDriveEmail"> as {{ googleDriveEmail }}</span>
                </div>
                <button
                    class="border-terracotta-clay-dark/40 text-terracotta-clay-dark hover:bg-terracotta-clay-dark/10
                        rounded-lg border px-4 py-2 text-sm font-medium transition-colors"
                    @click="disconnectFromGoogleDrive"
                >
                    Disconnect
                </button>
            </template>
            <button
                v-else
                class="bg-ember-glow/10 text-ember-glow hover:bg-ember-glow/20 flex items-center gap-2 rounded-lg
                    px-4 py-2 text-sm font-medium transition-colors"
                @click="connectToGoogleDrive"
            >
                <UiIcon name="CiGoogle" class="h-4 w-4" />
                Connect Google Drive
            </button>
        </div>
    </div>
</template>
