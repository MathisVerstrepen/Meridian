export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { email } = await readBody(event);

    if (!email) {
        throw createError({
            statusCode: 400,
            message: 'Email is required',
        });
    }

    try {
        await $fetch(`${API_BASE_URL}/auth/resend-verification`, {
            method: 'POST',
            body: { email },
        });

        return { status: 'sent' };
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { detail?: string } };
        throw createError({
            statusCode: err.response?.status || 500,
            message: err.data?.detail || 'Failed to resend verification email.',
        });
    }
});
