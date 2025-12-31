<script lang="ts" setup>
interface Props {
    modelValue: string;
    label: string;
    id: string;
    type?: string;
    placeholder?: string;
    autocomplete?: string;
    autofocus?: boolean;
    disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    type: 'text',
    placeholder: '',
    autocomplete: 'off',
    autofocus: false,
    disabled: false,
});

const emit = defineEmits<{
    (e: 'update:modelValue', value: string): void;
}>();

const value = computed({
    get: () => props.modelValue,
    set: (val) => emit('update:modelValue', val),
});
</script>

<template>
    <div class="flex flex-col space-y-1.5">
        <label :for="id" class="text-stone-gray text-xs font-medium tracking-wider uppercase">
            {{ label }}
        </label>
        <input
            :id="id"
            v-model="value"
            :type="type"
            :placeholder="placeholder"
            :autocomplete="autocomplete"
            :autofocus="autofocus"
            :disabled="disabled"
            class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50 w-full
                rounded-xl border border-white/5 bg-[#222222] px-4 py-3 text-sm transition-all
                duration-200 focus:border-transparent focus:ring-2 focus:outline-none
                disabled:cursor-not-allowed disabled:opacity-50"
        />
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
