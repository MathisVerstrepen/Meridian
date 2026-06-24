<script lang="ts" setup>
import type { CustomThemeColors, ThemeId } from '@/types/settings';

const props = withDefaults(
    defineProps<{
        theme: ThemeId;
        label: string;
        colors: CustomThemeColors;
        accentColor: string;
        isSelected?: boolean;
    }>(),
    { isSelected: false },
);

const emit = defineEmits<{ click: [] }>();

const handleClick = () => emit('click');
</script>

<template>
    <button
        :class="[
            'group/card relative flex w-44 cursor-pointer flex-col overflow-hidden rounded-xl border-2',
            'transition-all duration-200 ease-in-out hover:scale-[1.03]',
            props.isSelected
                ? 'border-ember-glow ring-2 ring-ember-glow/30'
                : 'border-stone-gray/15 hover:border-stone-gray/30',
        ]"
        @click="handleClick"
    >
        <div
            class="flex flex-col gap-2 p-3"
            :style="{ backgroundColor: props.colors.obsidian }"
        >
            <div class="flex items-center justify-between">
                <span
                    class="text-xs font-bold"
                    :style="{ color: props.colors.softSilk }"
                >
                    Aa
                </span>
                <span
                    class="rounded px-1.5 py-0.5 text-[0.6rem] font-semibold"
                    :style="{
                        backgroundColor: props.accentColor,
                        color: props.colors.obsidian,
                    }"
                >
                    Button
                </span>
            </div>

            <div class="flex gap-1.5">
                <span
                    class="h-8 flex-1 rounded-md"
                    :style="{ backgroundColor: props.colors.anthracite }"
                />
                <span
                    class="h-8 w-2/5 rounded-md"
                    :style="{ backgroundColor: props.colors.anthracite }"
                />
            </div>

            <div class="flex items-center gap-1.5">
                <span
                    class="h-1.5 w-1.5 rounded-full"
                    :style="{ backgroundColor: props.accentColor }"
                />
                <span
                    class="h-1.5 flex-1 rounded-full"
                    :style="{ backgroundColor: props.colors.stoneGray }"
                />
            </div>
        </div>

        <div
            class="flex items-center justify-between border-t px-3 py-2"
            :style="{
                backgroundColor: props.colors.anthracite,
                borderColor: props.colors.stoneGray,
            }"
        >
            <span
                class="text-xs font-bold capitalize"
                :style="{ color: props.colors.softSilk }"
            >
                {{ props.label }}
            </span>
            <span
                v-if="props.isSelected"
                class="flex h-4 w-4 items-center justify-center rounded-full"
                :style="{ backgroundColor: props.accentColor }"
            >
                <UiIcon
                    name="MaterialSymbolsCheckSmallRounded"
                    class="h-3 w-3"
                    :style="{ color: props.colors.obsidian }"
                />
            </span>
        </div>
    </button>
</template>

<style scoped></style>
