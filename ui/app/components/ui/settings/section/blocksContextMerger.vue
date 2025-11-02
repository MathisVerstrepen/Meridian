<script lang="ts" setup>
import { ContextMergerModeEnum } from '@/types/enums';

// --- Stores ---
const settingsStore = useSettingsStore();
const { blockContextMergerSettings } = storeToRefs(settingsStore);

const modes = [
    { value: ContextMergerModeEnum.FULL, icon: 'TablerArrowMerge' },
    { value: ContextMergerModeEnum.SUMMARY, icon: 'MynauiSparklesSolid' },
    { value: ContextMergerModeEnum.LAST_N, icon: 'MingcuteTimeDurationLine' },
];

const positions = {
    [ContextMergerModeEnum.FULL]: 0,
    [ContextMergerModeEnum.SUMMARY]: 1,
    [ContextMergerModeEnum.LAST_N]: 2,
};

// --- Computed properties ---
const currentPosition = computed(
    () => positions[blockContextMergerSettings.value.merger_mode] ?? 0,
);

const sliderStyle = computed(() => {
    const position = currentPosition.value;
    return `transform: translateX(calc(${position} * 100%));`;
});

const formatLabel = (mode: string) => {
    return mode.replace('_', ' ');
};
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Default Merger Mode -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Merger Mode</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Select the default merging strategy for new Context Merger nodes.
                </p>
            </div>
            <div class="ml-6 w-96 shrink-0">
                <div
                    class="border-stone-gray/20 relative flex h-10 overflow-hidden rounded-xl
                        border-2"
                >
                    <div
                        class="bg-ember-glow/80 absolute inset-y-0 w-1/3 rounded-lg
                            transition-transform duration-300 ease-in-out"
                        :style="sliderStyle"
                    />

                    <div
                        v-for="mode in modes"
                        :key="mode.value"
                        class="relative z-10 flex flex-1 cursor-pointer items-center justify-center
                            gap-1.5"
                        @click="blockContextMergerSettings.merger_mode = mode.value"
                    >
                        <UiIcon
                            :name="mode.icon"
                            class="dark:text-soft-silk text-anthracite h-4 w-4"
                            :class="{
                                'font-bold text-white opacity-100':
                                    blockContextMergerSettings.merger_mode === mode.value,
                                'opacity-60': blockContextMergerSettings.merger_mode !== mode.value,
                            }"
                        />
                        <span
                            class="text-stone-gray text-sm font-medium capitalize transition-colors"
                            :class="{
                                'text-white': blockContextMergerSettings.merger_mode === mode.value,
                            }"
                        >
                            {{ formatLabel(mode.value) }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Setting: Default Last N Value -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">"Last N" Value</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Set the default number of recent conversation turns to include when using the
                    "Last N" mode.
                </p>
            </div>
            <div class="ml-6 w-32 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="default-last-n-input"
                    :number="blockContextMergerSettings.last_n"
                    placeholder="Default: 5"
                    :min="1"
                    :step="1"
                    @update:number="
                        (value: number) => {
                            blockContextMergerSettings.last_n = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Default Summarizer Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Summarizer Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose the model used for summarizing branches in "Summary" mode. A powerful,
                    but relatively cheap model is recommended for a cost effective balance between
                    performance and expense.
                </p>
            </div>
            <div class="shrink-0">
                <UiModelsSelect
                    :model="blockContextMergerSettings.summarizer_model"
                    :set-model="
                        (model: string) => {
                            blockContextMergerSettings.summarizer_model = model;
                        }
                    "
                    to="right"
                    from="bottom"
                    :disabled="false"
                    variant="grey"
                />
            </div>
        </div>

        <!-- Setting: Include User Messages -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Include User Messages</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Set whether user messages should be included by default when merging context.
                    Disabling may result in less relevant context. Enabling is generally recommended
                    but may increase token usage.
                </p>
            </div>
            <div class="shrink-0">
                <UiSettingsUtilsSwitch
                    id="include-user-messages"
                    :state="blockContextMergerSettings.include_user_messages"
                    :set-state="
                        (value: boolean) => {
                            blockContextMergerSettings.include_user_messages = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>

<style scoped>
.transition-transform {
    transition-property: transform;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
