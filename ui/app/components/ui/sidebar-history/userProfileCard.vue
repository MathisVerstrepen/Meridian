<script lang="ts" setup>
import type { User } from '@/types/user';
import { motion } from 'motion-v';

const { user } = useUserSession();
const isUsageVisible = ref(false);
</script>

<template>
    <div class="relative" @mouseenter="isUsageVisible = true" @mouseleave="isUsageVisible = false">
        <AnimatePresence>
            <motion.div
                v-if="isUsageVisible"
                class="text-soft-silk bg-obsidian/90 border-stone-gray/10 shadow-obsidian/50
                    absolute bottom-8 left-0 z-40 h-[18.5rem] w-full rounded-2xl border shadow-2xl
                    backdrop-blur-xl"
                :initial="{
                    opacity: 0,
                    y: 15,
                    scale: 0.98,
                    transformOrigin: 'bottom',
                }"
                :animate="{
                    opacity: 1,
                    y: 0,
                    scale: 1,
                    transition: {
                        type: 'spring',
                        stiffness: 300,
                        damping: 25,
                        mass: 0.8,
                    },
                }"
                :exit="{
                    opacity: 0,
                    y: 15,
                    scale: 0.98,
                    transition: {
                        duration: 0.15,
                        ease: 'easeInOut',
                    },
                }"
            >
                <UiSidebarHistoryUserUsage />
            </motion.div>
        </AnimatePresence>

        <div
            class="dark:text-stone-gray text-soft-silk bg-anthracite hover:bg-anthracite/80 relative
                z-50 mt-2 flex w-full items-center justify-between gap-2 rounded-2xl border-2
                border-transparent py-1.5 pr-1.5 pl-1 transition-colors duration-300 ease-in-out"
        >
            <NuxtLink
                class="flex min-h-10 w-fit min-w-0 cursor-pointer items-center gap-3 rounded-lg
                    px-2"
                to="/settings?tab=account"
            >
                <UiUtilsUserProfilePicture />
                <div class="flex grow items-center gap-2 overflow-hidden">
                    <span
                        class="min-w-0 overflow-hidden font-bold overflow-ellipsis
                            whitespace-nowrap"
                        >{{ (user as User).name }}</span
                    >
                    <UiUtilsPlanLevelChip :level="(user as User).plan_type" />
                </div>
            </NuxtLink>

            <NuxtLink
                to="/settings"
                class="hover:bg-stone-gray/10 flex h-10 w-10 shrink-0 cursor-pointer items-center
                    justify-center rounded-xl transition-all duration-200"
                aria-label="Settings"
            >
                <UiIcon name="MaterialSymbolsSettingsRounded" class="h-6 w-6" />
            </NuxtLink>
        </div>
    </div>
</template>

<style scoped></style>
