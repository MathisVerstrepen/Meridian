const API_BASE_URL = 'http://localhost:8000';

export default defineOAuthGoogleEventHandler({
    config: {},
    async onSuccess(event, { user, tokens }) {
        try {
            console.log('Google OAuth user:', user);
            await $fetch(`${API_BASE_URL}/auth/sync-user/google`, {
                method: 'POST',
                body: {
                    oauthId: user.sub,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.picture,
                },
            });

            await setUserSession(event, {
                user: {
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
