import { runMermaidCharts } from '../../shared/mermaid/runtime.mjs';

export const useMermaid = () => {
    const renderMermaidCharts = async () => {
        if (import.meta.server) {
            return;
        }

        await runMermaidCharts('.mermaid');
    };

    return {
        renderMermaidCharts,
    };
};
