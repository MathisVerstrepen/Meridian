// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs';

export default withNuxt([
    {
        ignores: ['**/vue-virtual-scroller.d.ts', '**/useFileIcons.ts', '**/vue-cropperjs.d.ts'],
    },
    {
        rules: {
            'vue/no-multiple-template-root': 'off',
            'vue/no-v-html': 'off',
            'vue/no-mutating-props': 'off',
            'vue/one-component-per-file': 'off',
            'vue/html-self-closing': 'off'
        },
    },
]);
