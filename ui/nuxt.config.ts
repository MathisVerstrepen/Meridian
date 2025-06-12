// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from '@tailwindcss/vite';

export default defineNuxtConfig({
    compatibilityDate: '2024-11-01',
    devtools: { enabled: false },
    css: ['~/assets/css/main.css'],

    head: {
        script: [
            {
                src: 'https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.js',
                type: 'text/javascript',
                async: true,
            },
        ],
    },

    vite: {
        plugins: [tailwindcss()],
    },

    modules: [
        '@pinia/nuxt',
        'pinia-plugin-persistedstate/nuxt',
        'nuxt-headlessui',
        '@tailwindcss/postcss',
        'nuxt-auth-utils',
        '@nuxt/image',
    ],

    runtimeConfig: {
        public: {
            apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
        },
    },
});
