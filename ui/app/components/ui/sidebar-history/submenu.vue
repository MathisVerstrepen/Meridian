<script lang="ts" setup>
defineProps<{
    title: string;
    icon: string;
    items: {
        label: string;
        icon?: string;
        action?: () => void;
        class?: string;
        isHeader?: boolean;
    }[];
}>();

const isOpen = ref(false);

const executeAction = (action?: () => void) => {
    if (action) action();
};
</script>

<template>
    <div class="relative w-full" @mouseenter="isOpen = true" @mouseleave="isOpen = false">
        <button
            class="group flex w-full items-center justify-between rounded-md px-2 py-2 text-sm
                font-bold transition-colors duration-200 ease-in-out"
            :class="[
                isOpen
                    ? 'bg-obsidian/25 dark:text-obsidian text-soft-silk'
                    : 'dark:text-obsidian text-soft-silk hover:bg-obsidian/25',
            ]"
            @click.stop
        >
            <div class="flex items-center gap-2">
                <UiIcon :name="icon" class="h-4 w-4 opacity-70" />
                <span>{{ title }}</span>
            </div>
            <UiIcon
                name="FlowbiteChevronDownOutline"
                class="h-4 w-4 -rotate-90 opacity-50 transition-transform duration-200"
                :class="{ '-rotate-180': isOpen }"
            />
        </button>

        <div v-if="isOpen">
            <!-- Hover Bridge -->
            <div
                class="absolute top-10 -left-4 z-40 h-10 w-20"
                style="clip-path: polygon(0 0, 100% 0, 0 100%)"
            ></div>
            <div class="absolute top-0 -left-4 z-40 h-10 w-20"></div>
        </div>

        <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 -translate-x-1"
            enter-to-class="transform opacity-100 translate-x-0"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 translate-x-0"
            leave-to-class="transform opacity-0 -translate-x-1"
        >
            <div
                v-show="isOpen"
                class="dark:bg-stone-gray bg-anthracite dark:ring-anthracite/50 ring-stone-gray/10
                    hide-scrollbar absolute top-0 right-full z-30 mr-1 max-h-96 w-40
                    origin-top-right overflow-y-auto rounded-md p-1 shadow-lg ring-2
                    backdrop-blur-3xl focus:outline-none"
            >
                <template v-for="(item, index) in items" :key="index">
                    <!-- Header Item -->
                    <div v-if="item.isHeader" class="px-2 pt-2 pb-1">
                        <div
                            class="dark:text-obsidian/50 text-soft-silk/50 flex items-center gap-1.5
                                text-[10px] font-bold tracking-wider uppercase"
                        >
                            <UiIcon
                                v-if="item.icon"
                                :name="item.icon"
                                class="h-4 w-4 shrink-0 opacity-70 transition-opacity
                                    group-hover:opacity-100"
                            />
                            {{ item.label }}
                        </div>
                    </div>

                    <!-- Action Item -->
                    <button
                        v-else
                        class="group flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm
                            font-bold transition-colors duration-200 ease-in-out"
                        :class="[
                            item.class,
                            'hover:bg-obsidian/25 dark:text-obsidian text-soft-silk',
                        ]"
                        @click.stop="executeAction(item.action)"
                    >
                        <UiIcon
                            v-if="item.icon"
                            :name="item.icon"
                            class="h-4 w-4 shrink-0 opacity-70 transition-opacity
                                group-hover:opacity-100"
                        />
                        <span class="truncate">{{ item.label }}</span>
                    </button>
                </template>

                <div v-if="items.length === 0" class="p-2">
                    <span class="dark:text-obsidian/50 text-soft-silk/50 text-sm font-bold">
                        No items available.
                    </span>
                </div>
            </div>
        </transition>
    </div>
</template>
