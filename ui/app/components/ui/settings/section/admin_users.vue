<script lang="ts" setup>
import type { AdminUser, AdminUserListResponse } from '@/types/admin';
import type { User } from '@/types/user';

// --- State ---
const page = ref(1);
const limit = ref(10);
const users = ref<AdminUser[]>([]);
const total = ref(0);
const isLoading = ref(false);

const { error: showToastError, success: showToastSuccess } = useToast();
const { user: currentUser } = useUserSession();
const { apiFetch } = useAPI();

// --- Actions ---
const fetchUsers = async () => {
    isLoading.value = true;
    try {
        const params = new URLSearchParams({
            page: page.value.toString(),
            limit: limit.value.toString(),
        });
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
    }
};

const prevPage = () => {
    if (page.value > 1) {
        page.value--;
    }
};

// --- Watchers ---
watch(page, () => {
    fetchUsers();
});

// --- Lifecycle ---
onMounted(() => {
    fetchUsers();
});
</script>

<template>
    <div class="flex flex-col gap-6">
        <div class="mt-2 flex items-center justify-between">
            <h3 class="text-soft-silk text-lg font-semibold">User Management</h3>
            <div class="text-stone-gray text-sm">Total Users: {{ total }}</div>
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
                Page {{ page }} of {{ Math.ceil(total / limit) }}
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
