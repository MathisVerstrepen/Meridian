import { useMarkedWorker } from '~/composables/useMarkedWorker';

export default defineNuxtPlugin(() => {
    // The composable handles the singleton logic, so we just call it here.
    const markedWorker = useMarkedWorker();

    return {
        provide: {
            // Provide it as $markedWorker
            markedWorker,
        },
    };
});
