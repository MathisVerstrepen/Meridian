export interface AdminUser {
    id: string;
    username: string;
    email: string | null;
    avatar_url: string | null;
    oauth_provider: string | null;
    plan_type: 'free' | 'premium';
    is_verified: boolean;
    is_admin: boolean;
    created_at: string;
}

export interface AdminUserListResponse {
    users: AdminUser[];
    total: number;
    page: number;
    pageSize: number;
}
