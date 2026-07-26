export const useMermaid = () => {
    const renderMermaidCharts = async (selector = '.mermaid') => {
        if (import.meta.server) {
            return;
        }

        const { runMermaidCharts } = await import('~~/shared/mermaid/runtime.mjs');
        await runMermaidCharts(selector);
    };

    return {
        renderMermaidCharts,
    };
};
