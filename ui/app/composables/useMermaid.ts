import mermaid from 'mermaid';

let isMermaidInitialized = false;

export const useMermaid = () => {
    const renderMermaidCharts = async () => {
        if (import.meta.server) {
            return;
        }

        if (!isMermaidInitialized) {
            mermaid.initialize({
                startOnLoad: true,
                securityLevel: 'loose',
                flowchart: {
                    htmlLabels: true,
                },
                htmlLabels: true,
                theme: 'dark',
            });
            isMermaidInitialized = true;
        }

        await mermaid.run({
            querySelector: '.mermaid',
        });
    };

    return {
        renderMermaidCharts,
    };
};
