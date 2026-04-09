export const useMermaid = () => {
    const renderMermaidCharts = async () => {
        if (import.meta.server) {
            return;
        }

        const { runMermaidCharts } = await import('~~/shared/mermaid/runtime.mjs');
        await runMermaidCharts('.mermaid');
    };

    return {
        renderMermaidCharts,
    };
};
