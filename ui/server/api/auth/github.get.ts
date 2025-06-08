const API_BASE_URL = 'http://localhost:8000';

export default defineOAuthGitHubEventHandler({
    config: {
        emailRequired: true,
    },
    async onSuccess(event, { user, tokens }) {
        try {
            await $fetch(`${API_BASE_URL}/auth/sync-user`, {
                method: 'POST',
                body: {
                    githubId: user.id,
                    email: user.email,
                    name: user.name,
                    avatarUrl: user.avatar_url,
                },
            });

            await setUserSession(event, {
                user: {
                    githubId: user.id,
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
