import { SyncUserResponse } from '@/types/user';

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { username, password, rememberMe } = await readBody(event);

    if (!username || !password) {
        throw createError({
            statusCode: 400,
            message: 'Username and password are required',
        });
    }

    try {
        const apiUser = (await $fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            body: { username, password, rememberMe },
        })) as SyncUserResponse;

        if (!apiUser || !apiUser.user || !apiUser.token) {
            throw new Error('Invalid response from backend');
        }

        // Define cookie expiration based on "Remember Me"
        const accessTokenMaxAge = 60 * 22 * 60; // 22 hours in seconds
        const rememberMeMaxAge = 60 * 60 * 24 * 30; // 30 days in seconds

        setCookie(event, 'auth_token', apiUser.token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            path: '/',
            maxAge: rememberMe ? rememberMeMaxAge : accessTokenMaxAge,
        });

        // Create the user session using Nuxt Auth Utils
        await setUserSession(event, {
            user: {
                id: apiUser.user.id,
                email: apiUser.user.email,
                name: apiUser.user.username,
                avatarUrl: null,
                provider: 'userpass',
            },
        });

        return { status: 'authenticated' };
    } catch (error: any) {
        throw createError({
            statusCode: error.response?.status || 500,
            message: error.data?.detail || 'Invalid username or password',
        });
    }
});
