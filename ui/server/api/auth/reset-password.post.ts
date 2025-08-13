export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const { oldPassword, newPassword, token } = await readBody(event);

    if (!oldPassword || !newPassword) {
        throw createError({
            statusCode: 400,
            message: 'Old password and new password are required',
        });
    }

    try {
        const apiResponse = await $fetch(`${API_BASE_URL}/auth/reset-password`, {
            method: 'POST',
            body: { oldPassword, newPassword },
            headers: {
                'Content-Type': 'application/json',
                Accept: 'application/json',
                Authorization: `Bearer ${token}`,
            },
        });

        return apiResponse;
    } catch (error: any) {
        console.log(error);
        throw createError({
            statusCode: error.response?.status || 500,
            message: error.data?.detail || 'Failed to reset password',
        });
    }
});
