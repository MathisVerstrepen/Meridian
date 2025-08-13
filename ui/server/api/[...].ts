import { proxyRequest } from 'h3';

export default defineEventHandler(async (event) => {
    // 1. Get the auth token from the secure HttpOnly cookie.
    const token = getCookie(event, 'auth_token');

    // 2. If the token doesn't exist, block the request.
    if (!token) {
        throw createError({
            statusCode: 401,
            message: 'Unauthorized',
        });
    }

    // 3. Get the path for the backend API.
    const path = event.path.replace(/^\/api\//, '');

    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const targetUrl = `${API_BASE_URL}/${path}`;

    // 4. Securely proxy the request.
    return proxyRequest(event, targetUrl, {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });
});
