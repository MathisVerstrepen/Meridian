export default defineNuxtRouteMiddleware(async () => {
    const { loggedIn, ready, fetch: fetchSession } = useUserSession();

    // Only run the session check logic if the session isn't initialized yet.
    if (import.meta.client && !ready.value) {
        // Try to restore session from the cookie
        await fetchSession();

        // If still not logged in, attempt to use the refresh token
        if (!loggedIn.value) {
            try {
                await $fetch('/api/auth/refresh', { method: 'POST' });
                // If refresh succeeds, we must re-fetch the session to populate the user data
                await fetchSession();
            } catch {
                console.log('No valid refresh token found.');
            }
        }
    }

    // If the user is not logged in after the one-time check, they are redirected.
    if (!loggedIn.value) {
        return navigateTo('/auth/login');
    }
});
