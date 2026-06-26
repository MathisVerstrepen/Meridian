export interface AdminUser {
    id: string;
    username: string;
    email: string | null;
    avatar_url: string | null;
    oauth_provider: string | null;
    plan_type: 'free' | 'premium';
    is_verified: boolean;
    is_admin: boolean;
    is_suspended: boolean;
    suspended_reason: string | null;
    suspended_until: string | null;
    created_at: string;
}

export interface AdminUserListResponse {
    users: AdminUser[];
    total: number;
    page: number;
    pageSize: number;
}

export interface AdminMediaGenerationUsage {
    total: number;
    recent_total: number;
    pending: number;
    processing: number;
    retrying: number;
    completed: number;
    failed: number;
    cancelled: number;
}

export interface AdminUserUsageStats {
    total: number;
    active: number;
    active_days: number;
    new_users: number;
    verified: number;
    unverified: number;
    admins: number;
    suspended: number;
    free_plan: number;
    premium_plan: number;
}

export interface AdminGraphUsageStats {
    total: number;
    active: number;
    active_days: number;
    created: number;
    pinned: number;
    temporary: number;
}

export interface AdminQueryUsageStats {
    web_search_used: number;
    link_extraction_used: number;
    users_with_web_search_usage: number;
    users_with_link_extraction_usage: number;
}

export interface AdminStorageUsageStats {
    used_bytes: number;
    users_with_storage: number;
}

export interface AdminUsageDashboardResponse {
    total_users: number;
    active_users: number;
    active_days: number;
    graph_count: number;
    users: AdminUserUsageStats;
    graphs: AdminGraphUsageStats;
    query_usage: AdminQueryUsageStats;
    storage: AdminStorageUsageStats;
    image_generation: AdminMediaGenerationUsage;
    video_generation: AdminMediaGenerationUsage;
}
