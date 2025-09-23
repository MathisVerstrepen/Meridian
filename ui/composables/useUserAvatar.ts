import type { User } from '@/types/user';

/**
 * A composable to manage fetching and caching the user's avatar.
 * It ensures the avatar is fetched only once and the result is shared globally.
 */
export const useUserAvatar = () => {
    const avatarSrc = useState<string | null>('user-avatar-src', () => null);

    const { user } = useUserSession();
    const { fetchWithRefresh } = useAPI();
    const requestUrl = useRequestURL();

    /**
     * Fetches the avatar, converts it to a blob URL, and stores it in the shared state.
     * It intelligently avoids re-fetching if the avatar is already loaded.
     * @param options - Optional parameters.
     * @param options.force - If true, forces a re-fetch even if cached.
     */
    const loadAvatar = async (options: { force?: boolean } = {}) => {
        // Blob creation is a client-side only operation.
        if (!import.meta.client) {
            return;
        }

        const userAvatarUrl = (user.value as User)?.avatarUrl;

        // If user has no avatar, clear the cached src and exit.
        if (!userAvatarUrl) {
            if (avatarSrc.value && avatarSrc.value.startsWith('blob:')) {
                URL.revokeObjectURL(avatarSrc.value);
            }
            avatarSrc.value = '';
            return;
        }

        // If the URL is external, just use it directly.
        if (userAvatarUrl.startsWith('http')) {
            avatarSrc.value = userAvatarUrl;
            return;
        }

        // --- Caching Logic ---
        // If we are not forcing a reload and we already have a blob URL, do nothing.
        if (!options.force && avatarSrc.value && avatarSrc.value.startsWith('blob:')) {
            return;
        }

        // --- Fetching Logic ---
        const performRequest = async (): Promise<Blob> => {
            const fullUrl = new URL('/api/user/avatar', requestUrl.origin).href;
            const response = await fetch(fullUrl);

            if (response.status === 401) {
                const error = new Error('Unauthorized');
                const typedError = error as Error & { response?: { status: number } };
                typedError.response = { status: 401 };
                throw error;
            }
            if (!response.ok) {
                throw new Error(`Failed to fetch avatar: ${response.statusText}`);
            }
            return response.blob();
        };

        try {
            const blob = await fetchWithRefresh(performRequest, 'Avatar Error');

            // Clean up the old blob URL before creating a new one to prevent memory leaks.
            if (avatarSrc.value && avatarSrc.value.startsWith('blob:')) {
                URL.revokeObjectURL(avatarSrc.value);
            }

            avatarSrc.value = URL.createObjectURL(blob);
        } catch (error) {
            console.error('Could not load user avatar:', error);
            avatarSrc.value = '';
        }
    };

    // Automatically load the avatar when the user's avatar URL changes.
    watch(
        () => (user.value as User)?.avatarUrl,
        () => {
            loadAvatar({ force: true });
        },
    );

    return {
        avatarSrc,
        loadAvatar,
    };
};
