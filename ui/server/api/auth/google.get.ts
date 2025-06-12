import { SyncUserResponse } from '@/types/user';

export default defineOAuthGoogleEventHandler({
    config: {},
    async onSuccess(event, { user, tokens }) {
        const API_BASE_URL = useRuntimeConfig().public.apiBaseUrl;

        try {
            const apiUser = (await $fetch(`${API_BASE_URL}/auth/sync-user/google`, {
                method: 'POST',
                body: {
                    oauthId: user.sub,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.picture,
                },
            })) as SyncUserResponse;

            await setUserSession(event, {
                user: {
                    id: apiUser.user.id,
                    oauthId: user.sub,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.picture,
                    provider: 'google',
                },
            });

            return sendRedirect(event, '/');
        } catch (error) {
            console.error('Error syncing user with backend:', error);
            return sendRedirect(event, '/auth/login?error=backend-sync-failed');
        }
    },
    onError(event, error) {
        console.error('Google OAuth error:', error);
        return sendRedirect(event, '/auth/login?error=oauth-failed');
    },
});
