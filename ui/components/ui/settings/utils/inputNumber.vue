<script lang="ts" setup>
const props = defineProps<{
    number: number | null;
    placeholder?: string;
    step?: number;
    min?: number;
    max?: number;
}>();

const emit = defineEmits<{
    (event: 'update:number', number: number): void;
}>();

// --- Local State ---
const inputRef = ref<HTMLInputElement | null>(null);
const numberRef = ref(props.number);

// --- Core Logic Functions ---
const stepUp = () => {
    if (!inputRef.value) return;
    inputRef.value.stepUp();
    inputRef.value.dispatchEvent(new Event('input', { bubbles: true }));
};

const stepDown = () => {
    if (!inputRef.value) return;
    inputRef.value.stepDown();
    inputRef.value.dispatchEvent(new Event('input', { bubbles: true }));
};
</script>

<template>
    <div class="relative">
        <input
            ref="inputRef"
            v-model.number="numberRef"
            type="number"
            :step="step"
            :min="min"
            :max="max"
            class="hide-number-arrows border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow
                h-10 w-full rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none
                focus:border-2"
            :placeholder="placeholder"
            @input="
                (event: Event) => {
                    emit('update:number', Number((event.target as HTMLInputElement).value));
                }
            "
        >
        <div class="absolute top-0 right-2 flex h-full w-6 flex-col items-center justify-center">
            <!-- Up arrow -->
            <button
                class="hover:text-ember-glow/80 hover:bg-stone-gray/10 text-stone-gray flex h-4 items-center justify-center
                    rounded transition-colors duration-200 ease-in-out focus:outline-none"
                @click.stop="stepUp"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-5 w-5 rotate-180" />
            </button>
            <!-- Down arrow -->
            <button
                class="hover:text-ember-glow/80 hover:bg-stone-gray/10 text-stone-gray flex h-4 items-center justify-center
                    rounded transition-colors duration-200 ease-in-out focus:outline-none"
                @click.stop="stepDown"
            >
                <UiIcon name="FlowbiteChevronDownOutline" class="h-5 w-5" />
            </button>
        </div>
    </div>
</template>

<style>
/* Hide default number arrows */
.hide-number-arrows::-webkit-outer-spin-button,
.hide-number-arrows::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
}

.hide-number-arrows {
    appearance: textfield;
    -moz-appearance: textfield;
}
</style>
