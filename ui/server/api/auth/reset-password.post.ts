export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const token = getCookie(event, 'auth_token');
    const body = await readBody(event);

    if (!body.oldPassword || !body.newPassword) {
        throw createError({
            statusCode: 400,
            message: 'Old password and new password are required',
        });
    }

    if (!token) {
        throw createError({ statusCode: 401, message: 'Unauthorized' });
    }

    try {
        await $fetch(`${API_BASE_URL}/auth/reset-password`, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${token}`,
            },
            body: body,
        });

        return { status: 'ok' };
    } catch (error: any) {
        throw createError({
            statusCode: error.response?.status || 500,
            message: error.data?.detail || 'Failed to reset password',
        });
    }
});
