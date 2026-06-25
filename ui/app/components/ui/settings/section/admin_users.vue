<script lang="ts" setup>
import UsageDashboard from './admin_users/usageDashboard.vue';
import UserManagement from './admin_users/userManagement.vue';

type AdminSectionTab = 'users' | 'dashboard';

const activeAdminTab = ref<AdminSectionTab>('users');
</script>

<template>
    <div class="flex flex-col gap-6">
        <div
            class="mt-4 border-stone-gray/10 bg-stone-gray/5 flex w-fit rounded-lg border p-1"
            role="tablist"
            aria-label="Admin section tabs"
        >
            <button
                type="button"
                role="tab"
                :aria-selected="activeAdminTab === 'users'"
                class="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
                :class="
                    activeAdminTab === 'users'
                        ? 'bg-ember-glow/15 text-ember-glow'
                        : 'text-stone-gray hover:text-soft-silk'
                "
                @click="activeAdminTab = 'users'"
            >
                User Management
            </button>
            <button
                type="button"
                role="tab"
                :aria-selected="activeAdminTab === 'dashboard'"
                class="rounded-md px-3 py-1.5 text-sm font-medium transition-colors"
                :class="
                    activeAdminTab === 'dashboard'
                        ? 'bg-ember-glow/15 text-ember-glow'
                        : 'text-stone-gray hover:text-soft-silk'
                "
                @click="activeAdminTab = 'dashboard'"
            >
                Usage Dashboard
            </button>
        </div>

        <UserManagement v-show="activeAdminTab === 'users'" />
        <UsageDashboard v-show="activeAdminTab === 'dashboard'" />
    </div>
</template>
