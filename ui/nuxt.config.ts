// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from '@tailwindcss/vite';

export default defineNuxtConfig({
    compatibilityDate: '2024-11-01',
    devtools: { enabled: false },
    css: ['~/assets/css/main.css'],

    vite: {
        plugins: [tailwindcss()],
    },

    modules: [
        '@pinia/nuxt',
        'nuxt-headlessui',
        '@tailwindcss/postcss',
    ],
});
