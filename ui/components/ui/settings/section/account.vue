<script lang="ts" setup>
import type { User } from '@/types/user';

const { user, clear } = useUserSession();

const disconnect = async () => {
    try {
        clear().then(() => {
            console.log('User session cleared successfully.');
            window.location.reload();
        });
    } catch (error) {
        console.error('Error disconnecting:', error);
    }
};
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <div
            class="bg-obsidian/75 border-stone-gray/10 col-span-2 flex justify-between gap-4 rounded-2xl border-2 px-5
                py-4 shadow-lg backdrop-blur-md"
        >
            <div class="flex items-center gap-4">
                <img
                    :src="(user as User).avatarUrl"
                    alt="User Avatar"
                    :srcset="(user as User).avatarUrl"
                    class="h-10 w-10 rounded-full object-cover"
                    loading="lazy"
                    :width="40"
                    :height="40"
                />
                <div class="flex flex-col">
                    <div class="relative flex items-center">
                        <span class="text-stone-gray mr-2 font-bold">{{
                            (user as User).name
                        }}</span>
                        <span
                            class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-0.5 text-xs font-bold"
                            >{{ (user as User).provider }}</span
                        >
                    </div>
                    <span class="text-stone-gray/50 text-xs">{{ (user as User).email }}</span>
                </div>
            </div>

            <button
                class="bg-terracotta-clay-dark hover:bg-terracotta-clay-dark/80 focus:shadow-outline text-soft-silk w-fit
                    rounded-lg px-4 py-2 text-sm font-bold duration-200 ease-in-out hover:cursor-pointer
                    focus:outline-none"
                @click="disconnect"
            >
                Disconnect Account
            </button>
        </div>
    </div>
</template>

<style scoped></style>
