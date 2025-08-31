export default defineNuxtRouteMiddleware(async () => {
    const { loggedIn, fetch: fetchSession } = useUserSession();

    if (import.meta.client) {
        // Try to restore session or refresh token
        await fetchSession();

        // If still not logged in, try refresh token
        if (!loggedIn.value) {
            try {
                await $fetch('/api/auth/refresh', { method: 'POST' });
                await fetchSession(); // Re-fetch after refresh
            } catch (error) {
                console.log('Refresh token failed:', error);
            }
        }
    }

    if (!loggedIn.value) {
        return navigateTo('/auth/login');
    }
});
