import type { ApiUserProfile } from '~/types/user';

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const token = getCookie(event, 'auth_token');

    try {
        await $fetch(`${API_BASE_URL}/user/ack-welcome`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        const userProfile = await $fetch<ApiUserProfile>(`${API_BASE_URL}/users/me`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });

        await setUserSession(event, {
            user: {
                id: userProfile.id,
                email: userProfile.email,
                name: userProfile.username,
                avatarUrl: userProfile.avatar_url,
                provider: 'userpass',
                plan_type: userProfile.plan_type,
                is_admin: userProfile.is_admin,
                is_verified: userProfile.is_verified,
                has_seen_welcome: userProfile.has_seen_welcome,
            },
        });

        return { status: 'authenticated' };
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { detail?: string } };
        throw createError({
            statusCode: err.response?.status || 500,
            message: err.data?.detail || 'An error occurred while acknowledging welcome',
        });
    }
});
