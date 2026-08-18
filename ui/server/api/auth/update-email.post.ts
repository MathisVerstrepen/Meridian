export default defineEventHandler(async (event) => {
    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const body = await readBody(event);

    if (!body.username || !body.password || !body.email) {
        throw createError({
            statusCode: 400,
            message: 'Username, password, and email are required',
        });
    }

    try {
        await $fetch(`${API_BASE_URL}/auth/update-unverified-email`, {
            method: 'POST',
            body: body,
        });

        return { status: 'ok' };
    } catch (error: unknown) {
        throw createError({
            statusCode: runtimeErrorStatus(error) ?? 500,
            message: runtimeErrorDetail(error) ?? 'Failed to update email',
        });
    }
});
