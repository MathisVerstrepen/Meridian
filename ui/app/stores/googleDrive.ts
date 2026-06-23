import { defineStore } from 'pinia';

const { getGoogleDriveStatus } = useAPI();

export const useGoogleDriveStore = defineStore('GoogleDrive', () => {
    const isGoogleDriveConnected = ref(false);
    const googleDriveEmail = ref<string | null>(null);

    const checkGoogleDriveStatus = async () => {
        try {
            const data = await getGoogleDriveStatus();
            isGoogleDriveConnected.value = data.isConnected;
            googleDriveEmail.value = data.email ?? null;
        } catch (error) {
            console.error('Failed to check Google Drive status:', error);
            isGoogleDriveConnected.value = false;
            googleDriveEmail.value = null;
        }
    };

    return {
        isGoogleDriveConnected,
        googleDriveEmail,
        checkGoogleDriveStatus,
    };
});
