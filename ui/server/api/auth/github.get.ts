import { SyncUserResponse } from '@/types/user';

export default defineOAuthGitHubEventHandler({
    config: {
        emailRequired: true,
    },
    async onSuccess(event, { user, tokens }) {
        const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;

        try {
            const apiUser = (await $fetch(`${API_BASE_URL}/auth/sync-user/github`, {
                method: 'POST',
                body: {
                    oauthId: user.id,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.avatar_url,
                },
            })) as SyncUserResponse;

            if (!apiUser || !apiUser.user || !apiUser.token) {
                console.error('Failed to sync user with backend:', apiUser);
                return sendRedirect(event, '/auth/login?error=sync-failed');
            }

            setCookie(event, 'auth_token', apiUser.token, {
                httpOnly: false,
                secure: process.env.NODE_ENV === 'production',
                path: '/',
                maxAge: 60 * 15,
            });

            await setUserSession(event, {
                user: {
                    id: apiUser.user.id,
                    oauthId: user.id,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.avatar_url,
                    provider: 'github',
                },
            });

            return sendRedirect(event, '/');
        } catch (error) {
            console.error('Error syncing user with backend:', error);
            return sendRedirect(event, '/auth/login?error=backend-sync-failed');
        }
    },
    onError(event, error) {
        console.error('GitHub OAuth error:', error);
        return sendRedirect(event, '/auth/login?error=oauth-failed');
    },
});
