export default defineNuxtRouteMiddleware(async (to, from) => {
    const { loggedIn, fetch: fetchSession } = useUserSession();

    if (process.client) {
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
