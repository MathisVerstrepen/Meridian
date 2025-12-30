// FILE: MathisVerstrepen/Meridian/ui/app/pages/auth/verify.vue
<script lang="ts" setup>
const route = useRoute();
const email = ref<string>((route.query.email as string) || '');
const code = ref<string>('');
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);
const isResending = ref(false);

useHead({
    title: 'Meridian - Verify Email',
});

const { fetch: fetchUserSession } = useUserSession();

const verify = async () => {
    errorMessage.value = null;
    successMessage.value = null;

    if (code.value.length !== 6) {
        errorMessage.value = 'Please enter a valid 6-digit code.';
        return;
    }

    try {
        await $fetch('/api/auth/verify', {
            method: 'POST',
            body: {
                email: email.value,
                code: code.value,
            },
        });

        await fetchUserSession();
        await navigateTo('/');
    } catch (error: unknown) {
        const err = error as { response?: { status?: number }; data?: { message?: string } };
        errorMessage.value = err.data?.message || 'Verification failed. Please try again.';
    }
};

const resendCode = async () => {
    if (isResending.value) return;
    isResending.value = true;
    errorMessage.value = null;
    successMessage.value = null;

    try {
        await $fetch('/api/auth/resend', {
            method: 'POST',
            body: { email: email.value },
        });
        successMessage.value = 'A new verification code has been sent.';
    } catch {
        errorMessage.value = 'Failed to resend code. Please try again later.';
    } finally {
        isResending.value = false;
    }
};
</script>

<template>
    <div
        class="bg-obsidian relative flex h-screen w-screen items-center justify-center
            overflow-hidden"
    >
        <!-- Background Image -->
        <picture>
            <source srcset="/assets/img/login_bg.webp" type="image/webp" />
            <img
                src="/assets/img/login_bg.png"
                alt="Background Image"
                class="pointer-events-none absolute inset-0 z-0 h-full w-full object-cover
                    brightness-75"
            />
        </picture>

        <!-- Main Card Container -->
        <div
            class="z-10 flex h-full w-full max-w-[500px] flex-col justify-center overflow-hidden
                shadow-2xl ring-1 ring-white/10 md:h-auto md:rounded-[32px]"
        >
            <div class="bg-[#1A1A1A]/70 p-8 backdrop-blur-2xl md:p-12">
                <!-- Header -->
                <div class="mb-8 text-center">
                    <div class="mb-6 flex justify-center">
                        <UiIcon name="logo" class="text-ember-glow h-10 w-10" />
                    </div>
                    <h1 class="text-soft-silk text-2xl font-bold">Verify your email</h1>
                    <p class="text-stone-gray mt-2 text-sm">
                        We've sent a 6-digit code to <span class="text-white">{{ email }}</span>
                    </p>
                </div>

                <!-- Form -->
                <form class="flex flex-col space-y-6" @submit.prevent="verify">
                    <div class="flex justify-center">
                        <input
                            v-model="code"
                            type="text"
                            maxlength="6"
                            placeholder="000000"
                            class="text-soft-silk placeholder-stone-gray/30 focus:ring-ember-glow/50
                                w-48 rounded-xl border border-white/5 bg-[#222222] px-4 py-3
                                text-center text-2xl font-bold tracking-[0.5em] transition-all
                                duration-200 focus:border-transparent focus:ring-2
                                focus:outline-none"
                            autofocus
                        />
                    </div>

                    <!-- Messages -->
                    <p
                        v-if="errorMessage"
                        class="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2
                            text-center text-sm text-red-400"
                    >
                        {{ errorMessage }}
                    </p>
                    <p
                        v-if="successMessage"
                        class="rounded-lg border border-green-500/20 bg-green-500/10 px-4 py-2
                            text-center text-sm text-green-400"
                    >
                        {{ successMessage }}
                    </p>

                    <!-- Submit Button -->
                    <button
                        type="submit"
                        class="bg-soft-silk text-obsidian hover:bg-soft-silk/80 flex w-full
                            items-center justify-center rounded-full py-3.5 text-sm font-bold
                            transition-all duration-200 hover:cursor-pointer focus:ring-2
                            focus:ring-white/50 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]
                            focus:outline-none"
                    >
                        Verify Account
                    </button>
                </form>

                <!-- Resend Link -->
                <div class="mt-6 text-center text-sm">
                    <span class="text-stone-gray">Didn't receive code? </span>
                    <button
                        type="button"
                        class="text-soft-silk hover:text-ember-glow font-medium transition-colors"
                        :disabled="isResending"
                        @click="resendCode"
                    >
                        {{ isResending ? 'Sending...' : 'Resend' }}
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
