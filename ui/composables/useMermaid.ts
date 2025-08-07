export const useMermaid = () => {
    const renderMermaidCharts = async () => {
        const { $mermaid } = useNuxtApp();
        if (!$mermaid) {
            console.error('Mermaid is not available. Ensure it is loaded correctly.');
            return;
        }
        await $mermaid.run({
            querySelector: '.mermaid',
        });
    };

    return {
        renderMermaidCharts,
    };
};
