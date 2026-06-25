<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import type { AdminUser, AdminUserListResponse } from '@/types/admin';
import type { AllUsageResponse, QueryUsageResponse, User } from '@/types/user';

type PlanType = AdminUser['plan_type'];

const SUSPENSION_DURATION_SHORTCUTS = [
    { label: '24 hours', days: 1 },
    { label: '7 days', days: 7 },
    { label: '30 days', days: 30 },
    { label: '90 days', days: 90 },
] as const;

// --- State ---
const page = ref(1);
const limit = ref(10);
const users = ref<AdminUser[]>([]);
const total = ref(0);
const isLoading = ref(false);
const usageByUserId = ref<Record<string, AllUsageResponse>>({});
const usageLoadingIds = ref<string[]>([]);
const updatingPlanUserIds = ref<string[]>([]);
const updatingSuspensionUserIds = ref<string[]>([]);
const suspensionTargetUser = ref<AdminUser | null>(null);
const suspensionReason = ref('');
const suspensionUntil = ref('');
const searchQuery = ref('');
const providerFilter = ref('');
const planFilter = ref('');
const verifiedFilter = ref('');
const adminFilter = ref('');
const suspendedFilter = ref('');
const joinedFrom = ref('');
const joinedTo = ref('');
const searchDebounce = ref<ReturnType<typeof setTimeout> | null>(null);
const showFilters = ref(false);

const { error: showToastError, success: showToastSuccess } = useToast();
const { user: currentUser } = useUserSession();
const { apiFetch } = useAPI();
const { formatFileSize } = useFormatters();
const adminUsersEntry = SETTINGS_ENTRY.adminUsers;
let usageRequestId = 0;
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)));
const hasActiveFilters = computed(
    () =>
        searchQuery.value.trim() ||
        providerFilter.value ||
        planFilter.value ||
        verifiedFilter.value ||
        adminFilter.value ||
        suspendedFilter.value ||
        joinedFrom.value ||
        joinedTo.value,
);
const activeFilterCount = computed(() => {
    let count = 0;
    if (searchQuery.value.trim()) count++;
    if (providerFilter.value) count++;
    if (planFilter.value) count++;
    if (verifiedFilter.value) count++;
    if (adminFilter.value) count++;
    if (suspendedFilter.value) count++;
    if (joinedFrom.value) count++;
    if (joinedTo.value) count++;
    return count;
});

const toggleFilters = () => {
    showFilters.value = !showFilters.value;
};

const getUsagePercentage = (used: number, total: number) => {
    if (total <= 0) return 0;
    return Math.min(Math.round((used / total) * 100), 100);
};

const formatQueryUsage = (usage: QueryUsageResponse) => {
    if (usage.total <= 0) return 'Disabled';
    return `${usage.used} / ${usage.total}`;
};

const isUsageLoading = (userId: string) => usageLoadingIds.value.includes(userId);

const isPlanUpdating = (userId: string) => updatingPlanUserIds.value.includes(userId);

const isSuspensionUpdating = (userId: string) => updatingSuspensionUserIds.value.includes(userId);

const addPlanUpdatingUser = (userId: string) => {
    updatingPlanUserIds.value = [...new Set([...updatingPlanUserIds.value, userId])];
};

const removePlanUpdatingUser = (userId: string) => {
    updatingPlanUserIds.value = updatingPlanUserIds.value.filter((id) => id !== userId);
};

const addSuspensionUpdatingUser = (userId: string) => {
    updatingSuspensionUserIds.value = [...new Set([...updatingSuspensionUserIds.value, userId])];
};

const removeSuspensionUpdatingUser = (userId: string) => {
    updatingSuspensionUserIds.value = updatingSuspensionUserIds.value.filter((id) => id !== userId);
};

const isSuspensionActive = (targetUser: AdminUser) => {
    if (!targetUser.is_suspended) return false;
    if (!targetUser.suspended_until) return true;
    return new Date(targetUser.suspended_until).getTime() > Date.now();
};

const getSuspensionLabel = (targetUser: AdminUser) => {
    if (isSuspensionActive(targetUser)) return 'Suspended';
    if (targetUser.is_suspended) return 'Expired';
    return 'Active';
};

const getSuspensionBadgeClass = (targetUser: AdminUser) => {
    if (isSuspensionActive(targetUser)) return 'bg-red-500/15 text-red-400';
    if (targetUser.is_suspended) return 'bg-golden-ochre/15 text-golden-ochre';
    return 'bg-green-500/15 text-green-400';
};

const formatSuspensionUntil = (targetUser: AdminUser) => {
    if (!targetUser.suspended_until) return 'Indefinite';
    return new Date(targetUser.suspended_until).toLocaleString();
};

const toDateTimeLocalInputValue = (date: Date) => {
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return localDate.toISOString().slice(0, 16);
};

const toDateTimeLocalValue = (value: string | null) => {
    if (!value) return '';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    return toDateTimeLocalInputValue(date);
};

const setSuspensionDuration = (days: number) => {
    const untilDate = new Date();
    untilDate.setDate(untilDate.getDate() + days);
    suspensionUntil.value = toDateTimeLocalInputValue(untilDate);
};

const clearSuspensionDuration = () => {
    suspensionUntil.value = '';
};

const fetchVisibleUserUsage = async (visibleUsers: AdminUser[]) => {
    const requestId = ++usageRequestId;
    const nextUsageByUserId: Record<string, AllUsageResponse> = {};
    let hasFailedRequest = false;

    usageByUserId.value = {};
    usageLoadingIds.value = visibleUsers.map((user) => user.id);

    await Promise.all(
        visibleUsers.map(async (user) => {
            try {
                nextUsageByUserId[user.id] = await apiFetch<AllUsageResponse>(
                    `/api/admin/users/${user.id}/usage`,
                );
            } catch (err) {
                hasFailedRequest = true;
                console.error(err);
            }
        }),
    );

    if (requestId !== usageRequestId) {
        return;
    }

    usageByUserId.value = nextUsageByUserId;
    usageLoadingIds.value = [];

    if (hasFailedRequest) {
        showToastError('Failed to fetch usage for one or more users');
    }
};

// --- Actions ---
const fetchUsers = async () => {
    if (joinedFrom.value && joinedTo.value && joinedFrom.value > joinedTo.value) {
        showToastError('Joined from date cannot be after joined to date');
        return;
    }

    isLoading.value = true;
    try {
        const params = new URLSearchParams({
            page: page.value.toString(),
            limit: limit.value.toString(),
        });

        const search = searchQuery.value.trim();
        if (search) {
            params.set('search', search);
        }
        if (providerFilter.value) {
            params.set('provider', providerFilter.value);
        }
        if (planFilter.value) {
            params.set('plan_type', planFilter.value);
        }
        if (verifiedFilter.value) {
            params.set('is_verified', verifiedFilter.value);
        }
        if (adminFilter.value) {
            params.set('is_admin', adminFilter.value);
        }
        if (suspendedFilter.value) {
            params.set('is_suspended', suspendedFilter.value);
        }
        if (joinedFrom.value) {
            params.set('joined_from', joinedFrom.value);
        }
        if (joinedTo.value) {
            params.set('joined_to', joinedTo.value);
        }

        const data = await apiFetch<AdminUserListResponse>('/api/admin/users?' + params.toString());
        users.value = data.users;
        total.value = data.total;
        void fetchVisibleUserUsage(data.users);
    } catch (err) {
        showToastError('Failed to fetch users');
        console.error(err);
        usageByUserId.value = {};
        usageLoadingIds.value = [];
    } finally {
        isLoading.value = false;
    }
};

const scheduleFetchUsers = () => {
    if (searchDebounce.value) {
        clearTimeout(searchDebounce.value);
    }

    searchDebounce.value = setTimeout(() => {
        page.value = 1;
        fetchUsers();
    }, 300);
};

const clearFilters = () => {
    searchQuery.value = '';
    providerFilter.value = '';
    planFilter.value = '';
    verifiedFilter.value = '';
    adminFilter.value = '';
    suspendedFilter.value = '';
    joinedFrom.value = '';
    joinedTo.value = '';
    page.value = 1;
    fetchUsers();
};

const deleteUser = async (userId: string, username: string) => {
    if (!confirm(`Are you sure you want to delete user "${username}"? This cannot be undone.`)) {
        return;
    }

    try {
        await apiFetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
        });

        showToastSuccess(`User ${username} deleted successfully`);

        users.value = users.value.filter((u) => u.id !== userId);
        total.value--;

        await fetchUsers();
    } catch (err: unknown) {
        const msg = (err as { data?: { detail?: string } }).data?.detail || 'Failed to delete user';
        showToastError(msg);
        console.error(err);
    }
};

const updateUserPlan = async (targetUser: AdminUser, planType: PlanType) => {
    if (targetUser.plan_type === planType) {
        return;
    }

    addPlanUpdatingUser(targetUser.id);
    try {
        await apiFetch<AdminUser>(`/api/admin/users/${targetUser.id}/plan`, {
            method: 'PATCH',
            body: JSON.stringify({ plan_type: planType }),
        });

        showToastSuccess(`${targetUser.username} moved to ${planType} plan`);
        await fetchUsers();
    } catch (err: unknown) {
        const msg = (err as { data?: { detail?: string } }).data?.detail || 'Failed to update user plan';
        showToastError(msg);
        console.error(err);
    } finally {
        removePlanUpdatingUser(targetUser.id);
    }
};

const onPlanChange = (targetUser: AdminUser, event: Event) => {
    const planType = (event.target as HTMLSelectElement).value as PlanType;
    void updateUserPlan(targetUser, planType);
};

const openSuspendDialog = (targetUser: AdminUser) => {
    suspensionTargetUser.value = targetUser;
    suspensionReason.value = targetUser.suspended_reason || '';
    suspensionUntil.value = toDateTimeLocalValue(targetUser.suspended_until);
};

const closeSuspendDialog = () => {
    suspensionTargetUser.value = null;
    suspensionReason.value = '';
    suspensionUntil.value = '';
};

const updateUserSuspension = async (
    targetUser: AdminUser,
    isSuspended: boolean,
    reason: string | null = null,
    suspendedUntil: string | null = null,
) => {
    addSuspensionUpdatingUser(targetUser.id);
    try {
        await apiFetch<AdminUser>(`/api/admin/users/${targetUser.id}/suspension`, {
            method: 'PATCH',
            body: JSON.stringify({
                is_suspended: isSuspended,
                suspended_reason: reason,
                suspended_until: suspendedUntil,
            }),
        });

        showToastSuccess(
            isSuspended ? `${targetUser.username} suspended` : `${targetUser.username} unsuspended`,
        );
        await fetchUsers();
        return true;
    } catch (err: unknown) {
        const msg = (err as { data?: { detail?: string } }).data?.detail || 'Failed to update suspension';
        showToastError(msg);
        console.error(err);
        return false;
    } finally {
        removeSuspensionUpdatingUser(targetUser.id);
    }
};

const submitSuspension = async () => {
    if (!suspensionTargetUser.value) return;

    let suspendedUntil: string | null = null;
    if (suspensionUntil.value) {
        const untilDate = new Date(suspensionUntil.value);
        if (untilDate.getTime() <= Date.now()) {
            showToastError('Suspension expiry must be in the future');
            return;
        }
        suspendedUntil = untilDate.toISOString();
    }

    const wasUpdated = await updateUserSuspension(
        suspensionTargetUser.value,
        true,
        suspensionReason.value.trim() || null,
        suspendedUntil,
    );
    if (wasUpdated) {
        closeSuspendDialog();
    }
};

const unsuspendUser = async (targetUser: AdminUser) => {
    await updateUserSuspension(targetUser, false);
};

const nextPage = () => {
    if (page.value * limit.value < total.value) {
        page.value++;
        fetchUsers();
    }
};

const prevPage = () => {
    if (page.value > 1) {
        page.value--;
        fetchUsers();
    }
};

// --- Watchers ---
watch(
    [
        searchQuery,
        providerFilter,
        planFilter,
        verifiedFilter,
        adminFilter,
        suspendedFilter,
        joinedFrom,
        joinedTo,
    ],
    scheduleFetchUsers,
);

// --- Lifecycle ---
onMounted(() => {
    fetchUsers();
});

onBeforeUnmount(() => {
    if (searchDebounce.value) {
        clearTimeout(searchDebounce.value);
    }
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="mt-2 flex items-center justify-between">
            <h3 class="text-soft-silk text-lg font-semibold">{{ adminUsersEntry.title }}</h3>
            <div class="text-stone-gray text-sm">Total Users: {{ total }}</div>
        </div>

        <div class="flex flex-wrap items-center gap-3">
            <button
                class="border-stone-gray/20 bg-stone-gray/5 hover:bg-stone-gray/10 text-soft-silk
                    flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium
                    transition-colors"
                :aria-expanded="showFilters"
                @click="toggleFilters"
            >
                <UiIcon name="MaterialSymbolsTuneRounded" class="h-4 w-4" />
                <span>Filters</span>
                <span
                    v-if="activeFilterCount > 0"
                    class="bg-ember-glow/20 text-ember-glow rounded-full px-1.5 text-[10px]
                        font-bold leading-4"
                >
                    {{ activeFilterCount }}
                </span>
                <UiIcon
                    :name="showFilters ? 'LineMdChevronSmallUp' : 'FlowbiteChevronDownOutline'"
                    class="h-3.5 w-3.5 transition-transform"
                />
            </button>

            <div class="relative flex-1">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/50 pointer-events-none absolute left-2.5 top-1/2 h-4 w-4
                        -translate-y-1/2"
                />
                <input
                    v-model="searchQuery"
                    type="search"
                    placeholder="Search username or email..."
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk placeholder:text-stone-gray/40
                        focus:border-stone-gray/50 h-9 w-full rounded-md border py-1.5 pl-8 pr-3
                        text-sm outline-none transition-colors"
                />
            </div>

            <button
                v-if="hasActiveFilters"
                class="text-stone-gray/70 hover:text-soft-silk text-sm transition-colors"
                @click="clearFilters"
            >
                Clear
            </button>
        </div>

        <div
            v-show="showFilters"
            class="border-stone-gray/10 grid gap-2 rounded-lg border bg-black/10 p-3 md:grid-cols-4"
        >
            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Provider</span>
                <select
                    v-model="providerFilter"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                >
                    <option value="">All</option>
                    <option value="userpass">Email/password</option>
                    <option value="github">GitHub</option>
                    <option value="google">Google</option>
                </select>
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Plan</span>
                <select
                    v-model="planFilter"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                >
                    <option value="">All</option>
                    <option value="free">Free</option>
                    <option value="premium">Premium</option>
                </select>
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Verified</span>
                <select
                    v-model="verifiedFilter"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                >
                    <option value="">Any</option>
                    <option value="true">Verified</option>
                    <option value="false">Unverified</option>
                </select>
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Role</span>
                <select
                    v-model="adminFilter"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                >
                    <option value="">Any</option>
                    <option value="true">Admins</option>
                    <option value="false">Non-admins</option>
                </select>
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Status</span>
                <select
                    v-model="suspendedFilter"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                >
                    <option value="">Any</option>
                    <option value="false">Active</option>
                    <option value="true">Suspended</option>
                </select>
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Joined from</span>
                <input
                    v-model="joinedFrom"
                    type="date"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                />
            </label>

            <label class="flex flex-col gap-1 text-xs">
                <span class="text-stone-gray/70">Joined to</span>
                <input
                    v-model="joinedTo"
                    type="date"
                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-9 rounded-md border
                        px-2 text-sm outline-none transition-colors focus:border-stone-gray/50"
                />
            </label>
        </div>

        <div class="border-stone-gray/10 overflow-x-auto rounded-lg border">
            <table class="w-full min-w-[1120px] table-auto text-left text-sm">
                <thead class="bg-stone-gray/5 text-stone-gray/80 font-medium uppercase">
                    <tr>
                        <th class="px-4 py-3">User</th>
                        <th class="px-4 py-3">Provider</th>
                        <th class="px-4 py-3">Plan</th>
                        <th class="px-4 py-3">Usage</th>
                        <th class="px-4 py-3">Verified</th>
                        <th class="px-4 py-3">Status</th>
                        <th class="px-4 py-3">Joined</th>
                        <th class="px-4 py-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-stone-gray/10 text-stone-gray/90 divide-y">
                    <tr v-if="isLoading">
                        <td colspan="8" class="px-4 py-8 text-center">Loading users...</td>
                    </tr>
                    <tr v-else-if="users.length === 0">
                        <td colspan="8" class="px-4 py-8 text-center">No users found.</td>
                    </tr>
                    <tr
                        v-for="u in users"
                        :key="u.id"
                        class="hover:bg-stone-gray/5 transition-colors"
                    >
                        <td class="px-4 py-3">
                            <div class="flex items-center gap-3">
                                <div
                                    class="bg-stone-gray/20 flex h-8 w-8 items-center justify-center
                                        rounded-full"
                                >
                                    <UiIcon name="MaterialSymbolsAccountCircle" class="h-5 w-5" />
                                </div>
                                <div class="flex flex-col">
                                    <span class="font-medium text-white">
                                        {{ u.username }}
                                        <span
                                            v-if="u.is_admin"
                                            class="bg-ember-glow/20 text-ember-glow ml-2 rounded
                                                px-1.5 py-0.5 text-[10px] font-bold tracking-wider
                                                uppercase"
                                        >
                                            Admin
                                        </span>
                                        <span
                                            v-if="isSuspensionActive(u)"
                                            class="ml-2 rounded bg-red-500/15 px-1.5 py-0.5 text-[10px]
                                                font-bold tracking-wider text-red-400 uppercase"
                                        >
                                            Suspended
                                        </span>
                                    </span>
                                    <span class="text-stone-gray/60 text-xs">{{ u.email }}</span>
                                </div>
                            </div>
                        </td>
                        <td class="px-4 py-3 capitalize">
                            {{ u.oauth_provider || 'Email' }}
                        </td>
                        <td class="px-4 py-3">
                            <div class="flex flex-col gap-2">
                                <UiUtilsPlanLevelChip :level="u.plan_type" />
                                <select
                                    :value="u.plan_type"
                                    class="border-stone-gray/20 bg-eerie-black text-soft-silk h-8 rounded-md
                                        border px-2 text-xs outline-none transition-colors
                                        focus:border-stone-gray/50 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    :disabled="isPlanUpdating(u.id)"
                                    @change="onPlanChange(u, $event)"
                                >
                                    <option value="free">Free</option>
                                    <option value="premium">Premium</option>
                                </select>
                            </div>
                        </td>
                        <td class="px-4 py-3">
                            <div v-if="isUsageLoading(u.id)" class="text-stone-gray/60 text-xs">
                                Loading usage...
                            </div>
                            <div
                                v-else-if="usageByUserId[u.id]"
                                class="text-stone-gray/70 flex min-w-44 flex-col gap-1 text-xs"
                            >
                                <div>
                                    <div class="flex items-center justify-between gap-3">
                                        <span>Web</span>
                                        <span>{{ formatQueryUsage(usageByUserId[u.id].web_search) }}</span>
                                    </div>
                                    <div class="bg-stone-gray/15 mt-1 h-1.5 overflow-hidden rounded-full">
                                        <div
                                            class="bg-ember-glow h-full rounded-full transition-all"
                                            :style="{
                                                width: `${getUsagePercentage(
                                                    usageByUserId[u.id].web_search.used,
                                                    usageByUserId[u.id].web_search.total,
                                                )}%`,
                                            }"
                                        ></div>
                                    </div>
                                </div>

                                <div>
                                    <div class="flex items-center justify-between gap-3">
                                        <span>Links</span>
                                        <span>{{ formatQueryUsage(usageByUserId[u.id].link_extraction) }}</span>
                                    </div>
                                    <div class="bg-stone-gray/15 mt-1 h-1.5 overflow-hidden rounded-full">
                                        <div
                                            class="bg-golden-ochre h-full rounded-full transition-all"
                                            :style="{
                                                width: `${getUsagePercentage(
                                                    usageByUserId[u.id].link_extraction.used,
                                                    usageByUserId[u.id].link_extraction.total,
                                                )}%`,
                                            }"
                                        ></div>
                                    </div>
                                </div>

                                <div>
                                    <div class="flex items-center justify-between gap-3">
                                        <span>Storage</span>
                                        <span>
                                            {{ formatFileSize(usageByUserId[u.id].storage.used_bytes) }} /
                                            {{ formatFileSize(usageByUserId[u.id].storage.limit_bytes) }}
                                        </span>
                                    </div>
                                    <div class="bg-stone-gray/15 mt-1 h-1.5 overflow-hidden rounded-full">
                                        <div
                                            class="bg-sky-400 h-full rounded-full transition-all"
                                            :style="{
                                                width: `${Math.min(
                                                    Math.round(usageByUserId[u.id].storage.percentage),
                                                    100,
                                                )}%`,
                                            }"
                                        ></div>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="text-stone-gray/60 text-xs">Usage unavailable</div>
                        </td>
                        <td class="px-4 py-3">
                            <UiIcon
                                v-if="u.is_verified"
                                name="MaterialSymbolsCheckSmallRounded"
                                class="h-5 w-5 text-green-500"
                            />
                            <UiIcon
                                v-else
                                name="MaterialSymbolsClose"
                                class="h-5 w-5 text-red-500"
                            />
                        </td>
                        <td class="px-4 py-3">
                            <div class="flex max-w-40 flex-col gap-1">
                                <span
                                    class="w-fit rounded px-2 py-0.5 text-xs font-medium"
                                    :class="getSuspensionBadgeClass(u)"
                                >
                                    {{ getSuspensionLabel(u) }}
                                </span>
                                <span
                                    v-if="u.is_suspended"
                                    class="text-stone-gray/60 truncate text-xs"
                                    :title="u.suspended_reason || undefined"
                                >
                                    {{ formatSuspensionUntil(u) }}
                                </span>
                            </div>
                        </td>
                        <td class="px-4 py-3">
                            <NuxtTime :datetime="u.created_at" format="MMM D, YYYY" />
                        </td>
                        <td class="px-4 py-3 text-right">
                            <div class="flex justify-end gap-1">
                                <button
                                    v-if="u.id !== (currentUser as User)?.id && isSuspensionActive(u)"
                                    class="text-stone-gray/60 rounded p-1.5 transition-colors
                                        hover:bg-green-500/10 hover:text-green-400 disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    title="Unsuspend User"
                                    :disabled="isSuspensionUpdating(u.id)"
                                    @click="unsuspendUser(u)"
                                >
                                    <UiIcon name="MaterialSymbolsLockOpenRounded" class="h-5 w-5" />
                                </button>
                                <button
                                    v-else-if="u.id !== (currentUser as User)?.id"
                                    class="text-stone-gray/60 rounded p-1.5 transition-colors
                                        hover:bg-golden-ochre/10 hover:text-golden-ochre disabled:cursor-not-allowed
                                        disabled:opacity-50"
                                    title="Suspend User"
                                    :disabled="isSuspensionUpdating(u.id)"
                                    @click="openSuspendDialog(u)"
                                >
                                    <UiIcon name="MaterialSymbolsBlockOutline" class="h-5 w-5" />
                                </button>
                                <button
                                    v-if="u.id !== (currentUser as User)?.id"
                                    class="text-stone-gray/60 rounded p-1.5 transition-colors
                                        hover:bg-red-500/10 hover:text-red-500"
                                    title="Delete User"
                                    @click="deleteUser(u.id, u.username)"
                                >
                                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                                </button>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <UiUtilsBaseModal
            v-if="suspensionTargetUser"
            :model-value="Boolean(suspensionTargetUser)"
            :title="`Suspend ${suspensionTargetUser.username}`"
            description="Suspended users cannot log in, refresh sessions, or access protected API and WebSocket routes."
            icon="MaterialSymbolsBlockOutline"
            variant="danger"
            size="sm"
            @close="closeSuspendDialog"
        >
            <label class="mb-3 flex flex-col gap-1 text-sm">
                <span class="text-stone-gray/70">Reason</span>
                <textarea
                    v-model="suspensionReason"
                    rows="3"
                    maxlength="500"
                    placeholder="Optional note shown in the login/access error"
                    class="border-stone-gray/20 bg-obsidian/60 text-soft-silk placeholder:text-stone-gray/40
                        focus:border-ember-glow/50 rounded-lg border px-3 py-2 text-sm outline-none
                        transition-colors"
                ></textarea>
            </label>

            <label class="flex flex-col gap-1 text-sm">
                <span class="text-stone-gray/70">Suspend until</span>
                <input
                    v-model="suspensionUntil"
                    type="datetime-local"
                    class="border-stone-gray/20 bg-obsidian/60 text-soft-silk focus:border-ember-glow/50
                        h-10 rounded-lg border px-3 text-sm outline-none transition-colors"
                />
                <span class="text-stone-gray/50 text-xs">Leave empty for an indefinite suspension.</span>
            </label>

            <div class="mt-3 flex flex-wrap gap-2">
                <button
                    v-for="shortcut in SUSPENSION_DURATION_SHORTCUTS"
                    :key="shortcut.label"
                    type="button"
                    class="border-stone-gray/20 bg-stone-gray/5 text-stone-gray/80 hover:bg-stone-gray/10
                        hover:text-soft-silk rounded-lg border px-2.5 py-1.5 text-xs font-medium
                        transition-colors"
                    @click="setSuspensionDuration(shortcut.days)"
                >
                    {{ shortcut.label }}
                </button>
                <button
                    type="button"
                    class="border-stone-gray/20 bg-stone-gray/5 text-stone-gray/80 hover:bg-stone-gray/10
                        hover:text-soft-silk rounded-lg border px-2.5 py-1.5 text-xs font-medium
                        transition-colors"
                    @click="clearSuspensionDuration"
                >
                    Indefinite
                </button>
            </div>

            <template #footer>
                <button
                    class="text-stone-gray hover:text-soft-silk rounded-lg px-4 py-2 text-sm transition-colors"
                    @click="closeSuspendDialog"
                >
                    Cancel
                </button>
                <button
                    class="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm
                        font-bold text-red-400 transition-colors hover:bg-red-500/20
                        disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="isSuspensionUpdating(suspensionTargetUser.id)"
                    @click="submitSuspension"
                >
                    Suspend user
                </button>
            </template>
        </UiUtilsBaseModal>

        <!-- Pagination -->
        <div class="border-stone-gray/10 flex items-center justify-between border-t pt-4">
            <span class="text-stone-gray/60 text-sm">
                Page {{ page }} of {{ totalPages }}
            </span>
            <div class="flex gap-2">
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray rounded px-3
                        py-1.5 text-sm transition-colors disabled:cursor-not-allowed
                        disabled:opacity-50"
                    :disabled="page === 1 || isLoading"
                    @click="prevPage"
                >
                    Previous
                </button>
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray rounded px-3
                        py-1.5 text-sm transition-colors disabled:cursor-not-allowed
                        disabled:opacity-50"
                    :disabled="page * limit >= total || isLoading"
                    @click="nextPage"
                >
                    Next
                </button>
            </div>
        </div>
    </div>
</template>
