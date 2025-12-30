<script lang="ts" setup>
interface Props {
    modelValue: string;
    label: string;
    id: string;
    placeholder?: string;
    autocomplete?: string;
    disabled?: boolean;
}

withDefaults(defineProps<Props>(), {
    placeholder: '••••••••',
    autocomplete: 'current-password',
    disabled: false,
});

const emit = defineEmits<{
    (e: 'update:modelValue', value: string): void;
}>();

const showPassword = ref(false);

const onInput = (event: Event) => {
    const target = event.target as HTMLInputElement;
    emit('update:modelValue', target.value);
};
</script>

<template>
    <div class="flex flex-col space-y-1.5">
        <label :for="id" class="text-stone-gray text-xs font-medium tracking-wider uppercase">
            {{ label }}
        </label>
        <div class="relative">
            <input
                :id="id"
                :value="modelValue"
                :type="showPassword ? 'text' : 'password'"
                :placeholder="placeholder"
                :autocomplete="autocomplete"
                :disabled="disabled"
                class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50 w-full
                    rounded-xl border border-white/5 bg-[#222222] px-4 py-3 pr-12 text-sm
                    transition-all duration-200 focus:border-transparent focus:ring-2
                    focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                @input="onInput"
            />
            <button
                type="button"
                class="text-stone-gray hover:text-soft-silk absolute inset-y-0 right-4 flex
                    items-center transition-colors"
                :disabled="disabled"
                @click="showPassword = !showPassword"
            >
                <UiIcon
                    :name="
                        showPassword
                            ? 'MaterialSymbolsVisibilityOffOutline'
                            : 'MaterialSymbolsVisibilityOutline'
                    "
                    class="h-5 w-5"
                />
            </button>
        </div>
    </div>
</template>

<style scoped>
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active {
    -webkit-box-shadow: 0 0 0 30px #222222 inset !important;
    -webkit-text-fill-color: #e5e5e5 !important;
    caret-color: white;
    transition: background-color 5000s ease-in-out 0s;
}
</style>
