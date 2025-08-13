interface ApiUserProfile {
    id: string;
    email: string;
    username: string;
    avatar_url: string | null;
}

interface TokenResponse {
    accessToken: string;
    refreshToken?: string;
}

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { username, password, rememberMe } = await readBody(event);

    if (!username || !password) {
        throw createError({ statusCode: 400, message: 'Username and password are required' });
    }

    try {
        // Authenticate and get tokens from FastAPI
        const tokenResponse = await $fetch<TokenResponse>(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            body: { username, password, rememberMe },
        });

        if (!tokenResponse || !tokenResponse.accessToken) {
            throw new Error('Invalid token response from backend');
        }

        setCookie(event, 'auth_token', tokenResponse.accessToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            path: '/',
            maxAge: 60 * 15, // 15 minutes
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

        // Fetch the user profile using the new access token
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
            },
        });

        return { status: 'authenticated' };
    } catch (error: any) {
        throw createError({
            statusCode: error.response?.status || 500,
            message: error.data?.detail || 'An unexpected error occurred during login.',
        });
    }
});
