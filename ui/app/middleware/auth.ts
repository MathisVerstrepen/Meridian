import type { User } from '@/types/user';

export default defineNuxtRouteMiddleware(async () => {
    const { loggedIn, ready, user, clear, fetch: fetchSession } = useUserSession();

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

    // Force update/verification for legacy accounts with missing email or unverified status
    if (user.value && (user.value as User).provider === 'userpass') {
        if (!(user.value as User).email || !(user.value as User).is_verified) {
            const reason = !(user.value as User).email ? 'missing' : 'unverified';
            const username = (user.value as User).name;

            // Clear the session to force them to re-authenticate at the update page
            await clear();

            return navigateTo({
                path: '/auth/update-email',
                query: { username, reason },
            });
        }
    }
});
