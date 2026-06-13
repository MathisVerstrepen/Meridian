export interface User {
    id: string;
    oauthId: string;
    email: string;
    name: string;
    avatarUrl: string;
    provider: 'github' | 'google' | 'userpass';
    plan_type: 'free' | 'premium';
    is_admin: boolean;
    is_verified: boolean;
    has_seen_welcome: boolean;
}

export interface ApiUserProfile {
    id: string;
    username: string;
    email?: string | null;
    avatar_url?: string | null;
    oauth_provider: 'github' | 'google' | 'userpass';
    createdAt: string;
    plan_type: 'free' | 'premium';
    is_admin: boolean;
    is_verified: boolean;
    has_seen_welcome: boolean;
}

export interface OAuthSyncResponse {
    accessToken: string;
    refreshToken: string;
    user: ApiUserProfile;
}

export interface QueryUsageResponse {
    used: number;
    total: number;
    billing_period_end: string;
}

export interface StorageUsageBreakdownItem {
    category: string;
    used_bytes: number;
    file_count: number;
}

export interface StorageUsageResponse {
    used_bytes: number;
    limit_bytes: number;
    percentage: number;
    breakdown: StorageUsageBreakdownItem[];
}

export interface AllUsageResponse {
    web_search: QueryUsageResponse;
    link_extraction: QueryUsageResponse;
    storage: StorageUsageResponse;
}
