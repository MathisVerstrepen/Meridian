<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import type { AdminUser, AdminUserListResponse } from '@/types/admin';
import type { User } from '@/types/user';

// --- State ---
const page = ref(1);
const limit = ref(10);
const users = ref<AdminUser[]>([]);
const total = ref(0);
const isLoading = ref(false);
const searchQuery = ref('');
const providerFilter = ref('');
const planFilter = ref('');
const verifiedFilter = ref('');
const adminFilter = ref('');
const joinedFrom = ref('');
const joinedTo = ref('');
const searchDebounce = ref<ReturnType<typeof setTimeout> | null>(null);
const showFilters = ref(false);

const { error: showToastError, success: showToastSuccess } = useToast();
const { user: currentUser } = useUserSession();
const { apiFetch } = useAPI();
const adminUsersEntry = SETTINGS_ENTRY.adminUsers;
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / limit.value)));
const hasActiveFilters = computed(
    () =>
        searchQuery.value.trim() ||
        providerFilter.value ||
        planFilter.value ||
        verifiedFilter.value ||
        adminFilter.value ||
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
    if (joinedFrom.value) count++;
    if (joinedTo.value) count++;
    return count;
});

const toggleFilters = () => {
    showFilters.value = !showFilters.value;
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
        if (joinedFrom.value) {
            params.set('joined_from', joinedFrom.value);
        }
        if (joinedTo.value) {
            params.set('joined_to', joinedTo.value);
        }

        const data = await apiFetch<AdminUserListResponse>('/api/admin/users?' + params.toString());
        users.value = data.users;
        total.value = data.total;
    } catch (err) {
        showToastError('Failed to fetch users');
        console.error(err);
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
    [searchQuery, providerFilter, planFilter, verifiedFilter, adminFilter, joinedFrom, joinedTo],
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
            <table class="w-full min-w-full table-auto text-left text-sm">
                <thead class="bg-stone-gray/5 text-stone-gray/80 font-medium uppercase">
                    <tr>
                        <th class="px-4 py-3">User</th>
                        <th class="px-4 py-3">Provider</th>
                        <th class="px-4 py-3">Plan</th>
                        <th class="px-4 py-3">Verified</th>
                        <th class="px-4 py-3">Joined</th>
                        <th class="px-4 py-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-stone-gray/10 text-stone-gray/90 divide-y">
                    <tr v-if="isLoading">
                        <td colspan="6" class="px-4 py-8 text-center">Loading users...</td>
                    </tr>
                    <tr v-else-if="users.length === 0">
                        <td colspan="6" class="px-4 py-8 text-center">No users found.</td>
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
                                    </span>
                                    <span class="text-stone-gray/60 text-xs">{{ u.email }}</span>
                                </div>
                            </div>
                        </td>
                        <td class="px-4 py-3 capitalize">
                            {{ u.oauth_provider || 'Email' }}
                        </td>
                        <td class="px-4 py-3 capitalize">
                            {{ u.plan_type }}
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
                            <NuxtTime :datetime="u.created_at" format="MMM D, YYYY" />
                        </td>
                        <td class="px-4 py-3 text-right">
                            <button
                                v-if="u.id !== (currentUser as User)?.id"
                                class="text-stone-gray/60 rounded p-1.5 transition-colors
                                    hover:bg-red-500/10 hover:text-red-500"
                                title="Delete User"
                                @click="deleteUser(u.id, u.username)"
                            >
                                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                            </button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

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
