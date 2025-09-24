import type { ApiUserProfile } from '~/types/user';


export default defineNitroPlugin(() => {
    sessionHooks.hook('fetch', async (session, event) => {
        console.log('Session fetch hook: Fetching user data from backend.');

        // This hook is called whenever the session is fetched (e.g., on page load or via `fetch()`).
        // If a user is logged in, we sync their profile with the latest data from our main backend API.
        if (!session?.user) {
            return;
        }

        const API_BASE_URL = useRuntimeConfig(event).apiInternalBaseUrl;
        const token = getCookie(event, 'auth_token');

        if (!token) {
            return;
        }

        try {
            // Fetch the latest user profile from the FastAPI backend
            const userProfile = await $fetch<ApiUserProfile>(`${API_BASE_URL}/users/me`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            // Update the session with the fresh data.
            // This ensures that changes like profile picture updates are reflected everywhere.
            session.user = {
                ...session.user,
                id: userProfile.id,
                email: userProfile.email,
                name: userProfile.username,
                avatarUrl: userProfile.avatar_url,
                provider: userProfile.oauth_provider,
                plan_type: userProfile.plan_type,
                is_admin: userProfile.is_admin,
            };
        } catch (error) {
            console.error('Session fetch hook: Failed to refresh user data from backend.', error);
        }
    });
});
