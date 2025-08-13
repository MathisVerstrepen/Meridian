export interface User {
    id: string;
    oauthId: string;
    email: string;
    name: string;
    avatarUrl: string;
    provider: 'github' | 'google';
}

export interface ApiUserProfile {
    id: string;
    username: string;
    email?: string | null;
    avatar_url?: string | null;
    createdAt: string;
}

export interface OAuthSyncResponse {
    accessToken: string;
    refreshToken: string;
    user: ApiUserProfile;
}
