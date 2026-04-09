import type { OAuthSyncResponse } from '~/types/user';

export default defineOAuthGoogleEventHandler({
    config: {},
    async onSuccess(event, { tokens }) {
        const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;

        if (!tokens.id_token) {
            console.error('Google OAuth callback did not return an ID token.');
            return sendRedirect(event, '/auth/login?error=oauth-failed');
        }

        try {
            const apiUser = await $fetch<OAuthSyncResponse>(
                `${API_BASE_URL}/auth/sync-user/google`,
                {
                    method: 'POST',
                    body: {
                        accessToken: tokens.access_token,
                        idToken: tokens.id_token,
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
                    provider: 'google',
                    plan_type: apiUser.user.plan_type,
                    is_admin: apiUser.user.is_admin,
                    is_verified: apiUser.user.is_verified,
                    has_seen_welcome: apiUser.user.has_seen_welcome,
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
