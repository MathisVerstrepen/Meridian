<script lang="ts" setup>
const isResetPassPopupOpen = ref(false);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <UiSettingsSectionResetPassPopup
            v-if="isResetPassPopupOpen"
            @close-fullscreen="isResetPassPopupOpen = false"
        />

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Change Password</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Use this option to change your password for local accounts.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <button
                    class="hover:bg-stone-gray/10 focus:shadow-outline text-soft-silk
                        border-stone-gray/20 w-fit rounded-lg border-2 px-4 py-2 text-sm font-bold
                        duration-200 ease-in-out hover:cursor-pointer focus:outline-none"
                    @click="isResetPassPopupOpen = true"
                >
                    Change Password
                </button>
            </div>
        </div>
    </div>
</template>
