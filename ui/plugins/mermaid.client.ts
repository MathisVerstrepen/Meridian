import mermaid from 'mermaid';

export default defineNuxtPlugin(() => {
    // Initialize mermaid with default configuration
    mermaid.initialize({
        startOnLoad: true,
        securityLevel: 'loose',
        flowchart: {
            htmlLabels: true,
        },
        htmlLabels: true,
        theme: 'dark',
    });

    // Make mermaid available globally
    return {
        provide: {
            mermaid,
        },
    };
});
