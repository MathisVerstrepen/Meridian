<script lang="ts" setup>
defineProps<{
    title: string;
    icon: string;
    items: {
        label: string;
        icon?: string;
        action: () => void;
        isActive?: boolean;
        class?: string;
    }[];
}>();

const isOpen = ref(false);
</script>

<template>
    <div class="relative w-full" @mouseenter="isOpen = true" @mouseleave="isOpen = false">
        <button
            class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full items-center
                justify-between rounded-md py-2 pr-1 pl-4 text-sm font-bold transition-colors
                duration-200 ease-in-out"
            :class="{ 'bg-obsidian/25': isOpen }"
            @click.stop
        >
            <div class="flex items-center">
                <UiIcon :name="icon" class="dark:text-obsidian text-soft-silk mr-2 h-4 w-4" />
                {{ title }}
            </div>
            <UiIcon name="FlowbiteChevronDownOutline" class="h-4 w-4 -rotate-90" />
        </button>

        <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 translate-x-2"
            enter-to-class="transform opacity-100 translate-x-0"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 translate-x-0"
            leave-to-class="transform opacity-0 translate-x-2"
        >
            <div
                v-show="isOpen"
                class="dark:bg-stone-gray bg-anthracite dark:ring-anthracite/50 ring-stone-gray/10
                    hide-scrollbar absolute top-0 right-full z-30 mr-1 max-h-60 w-40
                    origin-top-right rounded-md p-1 shadow-lg ring-2 backdrop-blur-3xl
                    focus:outline-none"
            >
                <!-- Hover Bridge -->
                <div
                    class="absolute top-10 -right-16 h-10 w-20"
                    style="clip-path: polygon(0 0, 100% 0, 0 100%)"
                ></div>
                <div class="absolute top-0 -right-16 h-10 w-20"></div>

                <HeadlessMenuItem v-for="(item, index) in items" :key="index">
                    <button
                        class="hover:bg-obsidian/25 dark:text-obsidian text-soft-silk flex w-full
                            items-center rounded-md px-4 py-2 text-sm font-bold transition-colors
                            duration-200 ease-in-out"
                        :class="item.class"
                        @click.stop="item.action"
                    >
                        <UiIcon
                            v-if="item.icon"
                            :name="item.icon"
                            class="h-5 w-5 -translate-x-2 opacity-70"
                        />

                        <span class="truncate" :class="{ 'opacity-50': item.isActive === false }">
                            {{ item.label }}
                        </span>

                        <UiIcon
                            v-if="item.isActive"
                            name="MaterialSymbolsCheckSmallRounded"
                            class="ml-auto h-3 w-3"
                        />
                    </button>
                </HeadlessMenuItem>
            </div>
        </transition>
    </div>
</template>
