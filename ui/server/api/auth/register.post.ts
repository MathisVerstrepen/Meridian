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
        // Register and trigger email sending
        await $fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            body: { username, email, password },
        });

        // We do not set cookies here anymore, as the user is not verified yet.
        return { status: 'pending', message: 'Verification code sent' };
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { detail?: string } };
        throw createError({
            statusCode: err.response?.status || 500,
            message: err.data?.detail || 'An unexpected error occurred during registration.',
        });
    }
});
