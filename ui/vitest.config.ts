import { fileURLToPath, URL } from 'node:url';
import { defineVitestProject } from '@nuxt/test-utils/config';
import { defineConfig } from 'vitest/config';

const appDirectory = fileURLToPath(new URL('./app', import.meta.url));

export default defineConfig({
    test: {
        projects: [
            {
                resolve: {
                    alias: {
                        '@': appDirectory,
                        '~': appDirectory,
                    },
                },
                test: {
                    name: 'unit',
                    environment: 'node',
                    include: ['tests/unit/**/*.spec.ts'],
                    clearMocks: true,
                    restoreMocks: true,
                    isolate: true,
                },
            },
            await defineVitestProject({
                test: {
                    name: 'nuxt',
                    environment: 'nuxt',
                    environmentOptions: {
                        nuxt: {
                            domEnvironment: 'happy-dom',
                        },
                    },
                    include: ['tests/nuxt/**/*.spec.ts'],
                    setupFiles: ['./tests/nuxt/setup.ts'],
                    clearMocks: true,
                    restoreMocks: true,
                    isolate: true,
                },
            }),
        ],
    },
});
