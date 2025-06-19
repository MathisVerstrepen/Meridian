import { SyncUserResponse } from '@/types/user';

export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { username, password } = await readBody(event);

    if (!username || !password) {
        throw createError({
            statusCode: 400,
            message: 'Username and password are required',
        });
    }

    try {
        const apiUser = (await $fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            body: { username, password },
        })) as SyncUserResponse;

        if (!apiUser || !apiUser.user || !apiUser.token) {
            throw new Error('Invalid response from backend');
        }

        setCookie(event, 'auth_token', apiUser.token, {
            httpOnly: false,
            secure: process.env.NODE_ENV === 'production',
            path: '/',
            maxAge: 60 * 15, // 15 minutes
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

        return { token: apiUser.token };
    } catch (error: any) {
        throw createError({
            statusCode: error.response?.status || 500,
            message: error.data?.detail || 'Invalid username or password',
        });
    }
});