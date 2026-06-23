import type { H3Event } from 'h3';

interface TokenResponse {
    accessToken: string;
    refreshToken?: string;
}

const REFRESH_COOKIE_PATH = '/api/auth/refresh';
const refreshPromises = new Map<string, Promise<TokenResponse>>();

const FORWARDED_REQUEST_HEADERS = [
    'accept',
    'range',
    'if-none-match',
    'if-modified-since',
    'if-range',
] as const;

const FORWARDED_RESPONSE_HEADERS = [
    'accept-ranges',
    'content-disposition',
    'content-range',
    'content-type',
    'etag',
    'last-modified',
] as const;

const buildTargetUrl = (apiBaseUrl: string, fileId: string, query: ReturnType<typeof getQuery>) => {
    const baseUrl = apiBaseUrl.endsWith('/') ? apiBaseUrl : `${apiBaseUrl}/`;
    const targetUrl = new URL(`files/view/${encodeURIComponent(fileId)}`, baseUrl);

    Object.entries(query).forEach(([key, value]) => {
        if (Array.isArray(value)) {
            value.forEach((item) => targetUrl.searchParams.append(key, String(item)));
            return;
        }

        if (value !== undefined && value !== null) {
            targetUrl.searchParams.set(key, String(value));
        }
    });

    return targetUrl.toString();
};

const buildRequestHeaders = (event: H3Event, accessToken: string) => {
    const headers: Record<string, string> = {
        Authorization: `Bearer ${accessToken}`,
    };

    FORWARDED_REQUEST_HEADERS.forEach((headerName) => {
        const value = getHeader(event, headerName);
        if (value) {
            headers[headerName] = value;
        }
    });

    return headers;
};

const fetchFile = (event: H3Event, targetUrl: string, accessToken: string) => {
    return fetch(targetUrl, {
        headers: buildRequestHeaders(event, accessToken),
    });
};

const setTokenCookies = (event: H3Event, tokenResponse: TokenResponse) => {
    setCookie(event, 'auth_token', tokenResponse.accessToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict',
        path: '/',
        maxAge: 60 * 15,
    });

    if (tokenResponse.refreshToken) {
        setCookie(event, 'refresh_token', tokenResponse.refreshToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            path: REFRESH_COOKIE_PATH,
            maxAge: 60 * 60 * 24 * 30,
        });
    }
};

const clearTokenCookies = (event: H3Event) => {
    setCookie(event, 'auth_token', '', { maxAge: -1, path: '/' });
    setCookie(event, 'refresh_token', '', { maxAge: -1, path: REFRESH_COOKIE_PATH });
};

const refreshAccessToken = async (event: H3Event, refreshToken: string) => {
    const existingRefresh = refreshPromises.get(refreshToken);
    if (existingRefresh) {
        const tokenResponse = await existingRefresh;
        setTokenCookies(event, tokenResponse);
        return tokenResponse.accessToken;
    }

    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const refreshPromise = $fetch<TokenResponse>(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        body: { refreshToken },
    });

    refreshPromises.set(refreshToken, refreshPromise);

    try {
        const tokenResponse = await refreshPromise;
        setTokenCookies(event, tokenResponse);
        return tokenResponse.accessToken;
    } catch {
        clearTokenCookies(event);
        throw createError({
            statusCode: 401,
            message: 'Session expired. Please log in again.',
        });
    } finally {
        refreshPromises.delete(refreshToken);
    }
};

const sendFileResponse = (
    event: H3Event,
    response: Awaited<ReturnType<typeof fetchFile>>,
    refreshedToken: boolean,
) => {
    setResponseStatus(event, response.status, response.statusText);

    FORWARDED_RESPONSE_HEADERS.forEach((headerName) => {
        const value = response.headers.get(headerName);
        if (value) {
            setHeader(event, headerName, value);
        }
    });

    if (response.status >= 400 || refreshedToken) {
        setHeader(event, 'cache-control', 'private, no-store');
    } else {
        const cacheControl = response.headers.get('cache-control');
        setHeader(event, 'cache-control', cacheControl?.replace(/\bpublic\b/i, 'private') || 'private');
    }

    setHeader(event, 'vary', 'Cookie');

    if (!response.body) {
        return null;
    }

    return response.body;
};

export default defineEventHandler(async (event) => {
    const fileId = getRouterParam(event, 'fileId');
    if (!fileId) {
        throw createError({ statusCode: 400, message: 'File id is required' });
    }

    const API_BASE_URL = useRuntimeConfig().apiInternalBaseUrl;
    const targetUrl = buildTargetUrl(API_BASE_URL, fileId, getQuery(event));
    const refreshToken = getCookie(event, 'refresh_token');
    let accessToken = getCookie(event, 'auth_token');

    if (!accessToken) {
        if (!refreshToken) {
            throw createError({ statusCode: 401, message: 'Unauthorized' });
        }
        accessToken = await refreshAccessToken(event, refreshToken);
        const response = await fetchFile(event, targetUrl, accessToken);
        return sendFileResponse(event, response, true);
    }

    let response = await fetchFile(event, targetUrl, accessToken);
    if (response.status !== 401) {
        return sendFileResponse(event, response, false);
    }

    if (!refreshToken) {
        return sendFileResponse(event, response, false);
    }

    accessToken = await refreshAccessToken(event, refreshToken);
    response = await fetchFile(event, targetUrl, accessToken);

    return sendFileResponse(event, response, true);
});
