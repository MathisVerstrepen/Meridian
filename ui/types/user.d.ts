export interface User {
    id: string;
    oauthId: string;
    email: string;
    name: string;
    avatarUrl: string;
    provider: 'github' | 'google';
}

export interface UserRead {
    id: string;
    username: string;
    email?: string | null;
    avatarUrl?: string | null;
    createdAt: string;
}

export interface SyncUserResponse {
    status: string;
    user: UserRead;
}
