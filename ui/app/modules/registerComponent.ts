import { defineNuxtModule, addComponent } from 'nuxt/kit';

export default defineNuxtModule({
    setup() {
        addComponent({
            name: 'VueFlow',
            export: 'VueFlow',
            filePath: '@vue-flow/core',
        });
    },
});
