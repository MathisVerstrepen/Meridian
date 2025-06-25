<script setup lang="ts">
const props = defineProps<{
    toast: Toast;
}>();

const toastsStore = useToastsStore();

// Timer logic for auto-dismissal and pause on hover
const timer = ref<number | null>(null);
const startTime = ref<number>(0);
const remainingTime = ref(props.toast.timeout);

const startTimer = () => {
    startTime.value = Date.now();
    timer.value = window.setTimeout(() => {
        toastsStore.remove(props.toast.id);
    }, remainingTime.value);
};

const pauseTimer = () => {
    if (timer.value) {
        clearTimeout(timer.value);
        timer.value = null;
        remainingTime.value -= Date.now() - startTime.value;
    }
};

const resumeTimer = () => {
    if (remainingTime.value > 0) {
        startTimer();
    }
};

onMounted(() => {
    startTimer();
});

// Computed properties for dynamic styling based on toast type
const toastElements = computed(() => {
    switch (props.toast.type) {
        case 'success':
            return {
                icon: 'MaterialSymbolsCheckCircleOutlineRounded',
                accentClass: 'text-[#ddeac9]',
                bgClass: 'bg-olive-grove/25 border-olive-grove-dark',
            };
        case 'error':
            return {
                icon: 'TablerCircleX',
                accentClass: 'text-[#dfbbb4]',
                bgClass: 'bg-terracotta-clay/25 border-terracotta-clay-dark',
            };
        case 'warning':
            return {
                icon: 'UilExclamationTriangle',
                accentClass: 'text-[#fdeac0]',
                bgClass: 'bg-golden-ochre/25 border-golden-ochre-dark',
            };
        case 'info':
        default:
            return {
                icon: 'MajesticonsInformationCircleLine',
                accentClass: 'text-[#c8daec]',
                bgClass: 'bg-slate-blue/25 border-slate-blue-dark',
            };
    }
});
</script>

<template>
    <div
        :class="[
            'flex w-full max-w-[500px] items-start gap-3 rounded-xl border p-4 shadow-lg backdrop-blur-lg',
            toastElements.bgClass,
        ]"
        @mouseenter="pauseTimer"
        @mouseleave="resumeTimer"
        role="alert"
    >
        <UiIcon
            :name="toastElements.icon"
            :class="['mt-0.5 h-5 w-5 flex-shrink-0', toastElements.accentClass]"
            aria-hidden="true"
        />
        <div class="flex-1">
            <p v-if="toast.title" class="font-semibold" :class="toastElements.accentClass">
                {{ toast.title }}
            </p>
            <p class="text-sm" :class="toastElements.accentClass">
                {{ toast.message }}
            </p>
        </div>
        <button
            @click="toastsStore.remove(toast.id)"
            type="button"
            class="hover:bg-stone-gray/10 -m-1 flex h-6 w-6 items-center justify-center rounded-full p-1"
        >
            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
        </button>
    </div>
</template>
