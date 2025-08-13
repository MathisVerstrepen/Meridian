interface TokenResponse {
    accessToken: string;
    refreshToken?: string;
}

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const refreshToken = getCookie(event, 'refresh_token');

    if (!refreshToken) {
        throw createError({
            statusCode: 401,
            message: 'No refresh token found',
        });
    }

    try {
        const tokenResponse = await $fetch<TokenResponse>(`${API_BASE_URL}/auth/refresh`, {
            method: 'POST',
            body: { refreshToken },
        });

        // Set the new tokens as cookies
        setCookie(event, 'auth_token', tokenResponse.accessToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            path: '/',
            maxAge: 60 * 15, // 15 min
        });

        if (tokenResponse.refreshToken) {
            setCookie(event, 'refresh_token', tokenResponse.refreshToken, {
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production',
                sameSite: 'strict',
                path: '/api/auth/refresh',
                maxAge: 60 * 60 * 24 * 30, // 30 days
            });
        }

        return { status: 'refreshed' };
    } catch (error: any) {
        // If refresh fails, clear the cookies to force re-login
        setCookie(event, 'auth_token', '', { maxAge: -1, path: '/' });
        setCookie(event, 'refresh_token', '', { maxAge: -1, path: '/api/auth/refresh' });
        throw createError({
            statusCode: 401,
            message: 'Session expired. Please log in again.',
        });
    }
});
