import type { OAuthSyncResponse } from '~/types/user';

export default defineOAuthGitHubEventHandler({
    config: {
        emailRequired: true,
    },
    async onSuccess(event, { user }) {
        const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;

        try {
            const apiUser = await $fetch<OAuthSyncResponse>(
                `${API_BASE_URL}/auth/sync-user/github`,
                {
                    method: 'POST',
                    body: {
                        oauthId: user.id,
                        email: user.email,
                        name: user.name,
                        avatarUrl: user.avatar_url,
                    },
                },
            );

            if (!apiUser || !apiUser.accessToken || !apiUser.refreshToken || !apiUser.user) {
                console.error('Failed to sync user with backend:', apiUser);
                return sendRedirect(event, '/auth/login?error=sync-failed');
            }

            // Set the short-lived, HttpOnly access token cookie
            setCookie(event, 'auth_token', apiUser.accessToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'strict',
                path: '/',
                maxAge: 60 * 15, // 15 minutes
            });

            // Set the long-lived, HttpOnly refresh token cookie
            setCookie(event, 'refresh_token', apiUser.refreshToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'strict',
                path: '/api/auth/refresh',
                maxAge: 60 * 60 * 24 * 30, // 30 days
            });

            await setUserSession(event, {
                user: {
                    id: apiUser.user.id,
                    email: apiUser.user.email,
                    name: apiUser.user.username,
                    avatarUrl: apiUser.user.avatar_url,
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
