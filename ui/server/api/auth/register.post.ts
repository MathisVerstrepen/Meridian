import type { ApiUserProfile } from '~/types/user';

interface TokenResponse {
    accessToken: string;
    refreshToken?: string;
}

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { username, email, password } = await readBody(event);

    if (!username || !email || !password) {
        throw createError({
            statusCode: 400,
            message: 'Username, email, and password are required',
        });
    }

    try {
        // Register and get tokens from FastAPI
        const tokenResponse = await $fetch<TokenResponse>(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            body: { username, email, password },
        });

        if (!tokenResponse || !tokenResponse.accessToken) {
            throw new Error('Invalid token response from backend');
        }

        // Set Access Token Cookie
        setCookie(event, 'auth_token', tokenResponse.accessToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            path: '/',
            maxAge: 60 * 15, // 15 minutes
        });

        // Set Refresh Token Cookie (if present)
        if (tokenResponse.refreshToken) {
            setCookie(event, 'refresh_token', tokenResponse.refreshToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'strict',
                path: '/api/auth/refresh',
                maxAge: 60 * 60 * 24 * 30, // 30 days
            });
        }

        // Fetch the user profile using the new access token to hydrate the session immediately
        const userProfile = await $fetch<ApiUserProfile>(`${API_BASE_URL}/users/me`, {
            headers: {
                Authorization: `Bearer ${tokenResponse.accessToken}`,
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
            },
        });

        return { status: 'registered' };
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { detail?: string } };
        throw createError({
            statusCode: err.response?.status || 500,
            message: err.data?.detail || 'An unexpected error occurred during registration.',
        });
    }
});
